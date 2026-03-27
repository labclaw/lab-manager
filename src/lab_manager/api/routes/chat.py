"""WebSocket chat endpoint and REST API for Lab IM."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.document import Document
from lab_manager.services.reasoning import (
    ReasoningChainConfig,
    ReasoningRunRequest,
    get_reasoning_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory chat state
# ---------------------------------------------------------------------------

_MAX_HISTORY = 100

_chat_history: list[dict] = []
_connected_clients: list[WebSocket] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _add_message(msg: dict) -> dict:
    """Append message to history, trim to max size, return the stored dict."""
    _chat_history.append(msg)
    if len(_chat_history) > _MAX_HISTORY:
        del _chat_history[: len(_chat_history) - _MAX_HISTORY]
    return msg


async def _broadcast_async(msg: dict) -> None:
    """Send a JSON message to every connected WebSocket client (async-safe)."""
    data = json.dumps(msg, default=str)
    stale: list[WebSocket] = []
    for ws in _connected_clients:
        try:
            await ws.send_text(data)
        except Exception:
            stale.append(ws)
    for ws in stale:
        if ws in _connected_clients:
            _connected_clients.remove(ws)


def _broadcast_sync(msg: dict) -> None:
    """Fire-and-forget broadcast from sync context (REST handlers).

    Schedules sends on the running event loop. Best-effort: if no loop is
    available (e.g. test context), messages are only stored in history.
    """
    data = json.dumps(msg, default=str)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    stale: list[WebSocket] = []
    for ws in _connected_clients:
        try:
            loop.create_task(ws.send_text(data))
        except Exception:
            stale.append(ws)
    for ws in stale:
        if ws in _connected_clients:
            _connected_clients.remove(ws)


# ---------------------------------------------------------------------------
# Digital staff registry
# ---------------------------------------------------------------------------

_STAFF_HANDLERS: dict[str, Callable] = {}


def _register_staff(name: str, handler: Callable) -> None:
    _STAFF_HANDLERS[name.lower()] = handler


def get_digital_staff_names() -> list[str]:
    """Return display names of all registered digital staff."""
    return [k.title().replace("-", " ") for k in sorted(_STAFF_HANDLERS.keys())]


# --- AI handler: Inventory Manager (delegates to RAG service) ---


def _handle_inventory_manager(query: str, db: Session | None = None) -> str:
    """Hit the RAG endpoint internally and return the answer."""
    if not db:
        return "Error: no database session available."
    try:
        from lab_manager.services.rag import ask

        result = ask(query, db)
        answer = result.get("answer", "")
        rows = result.get("row_count")
        if rows is not None:
            answer += f" ({rows} rows)"
        return answer or "No answer available."
    except Exception as e:
        logger.error("RAG error in chat: %s", e)
        return "Sorry, I couldn't process that query. Please try again."


# --- AI handler: Document Processor (returns document stats) ---


def _handle_document_processor(query: str, db: Session | None = None) -> str:
    """Return document processing statistics."""
    if not db:
        return "Error: no database session available."
    try:
        total = db.execute(select(func.count(Document.id))).scalar() or 0
        by_status = dict(
            db.execute(
                select(Document.status, func.count(Document.id)).group_by(
                    Document.status
                )
            ).all()
        )
        lines = [f"Total documents: {total}"]
        for status, count in sorted(by_status.items()):
            lines.append(f"  {status}: {count}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("Document stats error in chat: %s", e)
        return "Sorry, I couldn't retrieve document stats. Please try again."


_register_staff("inventory-manager", _handle_inventory_manager)
_register_staff("document-processor", _handle_document_processor)


# ---------------------------------------------------------------------------
# @-mention parsing
# ---------------------------------------------------------------------------

_MENTION_RE = re.compile(r"@([\w-]+)\s*(.*)", re.DOTALL)


def _parse_mention(content: str) -> tuple[Optional[str], str]:
    """Return (staff_key, query) if content starts with @mention, else (None, content)."""
    m = _MENTION_RE.match(content.strip())
    if m:
        return m.group(1).lower(), m.group(2).strip()
    return None, content


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    from_: str = Field(..., alias="from", max_length=100)
    content: str = Field(..., max_length=5000)


class ChatMessageOut(BaseModel):
    type: str
    from_: str = Field(alias="from")
    content: str
    timestamp: str


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get("/history")
def chat_history(limit: int = Query(100, ge=1, le=100)):
    """Return the last N chat messages."""
    return _chat_history[-limit:]


@router.post("/message")
def send_message(body: ChatMessage, db: Session = Depends(get_db)):
    """Send a message via REST API (for non-WebSocket clients)."""
    msg: dict = {
        "type": "message",
        "from": body.from_,
        "content": body.content,
        "timestamp": _now_iso(),
    }
    _add_message(msg)
    _broadcast_sync(msg)

    # Check for @mention
    staff_key, query = _parse_mention(body.content)
    if staff_key and staff_key in _STAFF_HANDLERS and query:
        handler = _STAFF_HANDLERS[staff_key]
        try:
            answer = handler(query, db)
        except Exception as e:
            logger.error("Staff handler error: %s", e)
            answer = "Error processing request. Please try again."
        ai_msg: dict = {
            "type": "ai_response",
            "from": staff_key.title().replace("-", " "),
            "content": answer,
            "timestamp": _now_iso(),
        }
        _add_message(ai_msg)
        _broadcast_sync(ai_msg)

    return {"status": "ok"}


@router.get("/staff")
def list_staff():
    """Return available digital staff members."""
    staff_list = []
    for key in sorted(_STAFF_HANDLERS.keys()):
        staff_list.append(
            {
                "name": key.title().replace("-", " "),
                "status": "online",
            }
        )
    return {"staff": staff_list}


# ---------------------------------------------------------------------------
# Feed endpoint (for polling)
# ---------------------------------------------------------------------------


@router.get("/feed")
def get_feed(
    since: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent feed items (chat messages + AI alerts) for polling."""
    messages = list(_chat_history[-limit:])

    if since:
        messages = [m for m in messages if m.get("timestamp", "") > since]

    return {
        "messages": messages,
        "total": len(messages),
        "online_count": len(_connected_clients),
    }


# ---------------------------------------------------------------------------
# Reasoning chain endpoints
# ---------------------------------------------------------------------------


@router.get("/reasoning")
def list_reasoning_chains():
    """List all configured reasoning chains."""
    svc = get_reasoning_service()
    return {"chains": svc.list_chains()}


@router.post("/reasoning")
def create_reasoning_chain(body: ReasoningChainConfig):
    """Create a new reasoning chain configuration. Admin only."""
    svc = get_reasoning_service()
    chain = svc.create_chain(body)
    return chain


@router.post("/reasoning/run")
def run_reasoning_chain(
    body: ReasoningRunRequest,
    db: Session = Depends(get_db),
):
    """Execute a reasoning chain and return the result."""
    svc = get_reasoning_service()
    result = svc.run_chain(body.query, body.chain_id, db)

    # Post result to chat history
    ai_msg = {
        "type": "ai_response",
        "from": "AI-Inventory-Manager",
        "content": result.get("summary", "Reasoning chain completed."),
        "timestamp": _now_iso(),
        "badge": "Auto-approved",
        "badge_color": "green",
        "reasoning": result,
    }
    _add_message(ai_msg)

    return {"message": ai_msg, "chain_result": result}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await ws.accept()
    _connected_clients.append(ws)

    try:
        await ws.send_text(json.dumps({"type": "history", "messages": _chat_history}))
    except Exception:
        _connected_clients.remove(ws)
        return

    join_msg = {
        "type": "system",
        "from": "system",
        "content": "A user joined the chat.",
        "timestamp": _now_iso(),
    }
    _add_message(join_msg)
    await _broadcast_async(join_msg)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "system",
                            "from": "system",
                            "content": "Invalid message format. Send JSON.",
                            "timestamp": _now_iso(),
                        }
                    )
                )
                continue

            sender = str(data.get("from", "user"))[:100]
            content = str(data.get("content", ""))[:5000]

            if not content.strip():
                continue

            msg = {
                "type": "message",
                "from": sender,
                "content": content,
                "timestamp": _now_iso(),
            }
            _add_message(msg)
            await _broadcast_async(msg)

            # Handle @mention for AI staff
            staff_key, query = _parse_mention(content)
            if staff_key and staff_key in _STAFF_HANDLERS and query:
                typing_msg = {
                    "type": "system",
                    "from": staff_key.title().replace("-", " "),
                    "content": "is typing...",
                    "timestamp": _now_iso(),
                }
                await _broadcast_async(typing_msg)

                # Run handler in thread pool to avoid blocking event loop
                loop = asyncio.get_running_loop()
                handler = _STAFF_HANDLERS[staff_key]
                try:
                    from lab_manager.database import get_db_session

                    with get_db_session() as db:
                        answer = await loop.run_in_executor(None, handler, query, db)
                except Exception as e:
                    logger.error("WS staff handler error: %s", e)
                    answer = "Error processing request. Please try again."

                ai_msg = {
                    "type": "ai_response",
                    "from": staff_key.title().replace("-", " "),
                    "content": answer,
                    "timestamp": _now_iso(),
                }
                _add_message(ai_msg)
                await _broadcast_async(ai_msg)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        if ws in _connected_clients:
            _connected_clients.remove(ws)
        leave_msg = {
            "type": "system",
            "from": "system",
            "content": "A user left the chat.",
            "timestamp": _now_iso(),
        }
        _add_message(leave_msg)
        await _broadcast_async(leave_msg)
