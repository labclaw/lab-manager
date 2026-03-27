"""Comprehensive unit tests for chat (Lab IM) and ask (RAG) API routes.

Covers:
- Chat: REST history, send message, staff listing, @mention routing,
  history trimming, WebSocket join/leave/message flow
- Ask: POST and GET endpoints, auth dependency, response shape validation,
  error propagation, input validation, edge cases
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_chat_history():
    """Reset in-memory chat state before every test."""
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()
    chat_mod._connected_clients.clear()
    yield
    chat_mod._chat_history.clear()
    chat_mod._connected_clients.clear()


@pytest.fixture()
def _clear_rag_cache():
    """Reset the RAG result cache before each test."""
    from lab_manager.services.rag import _CACHE

    _CACHE.clear()
    yield
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Chat: helper functions
# ---------------------------------------------------------------------------


class TestNowIso:
    """Tests for _now_iso()."""

    def test_returns_string(self):
        from lab_manager.api.routes.chat import _now_iso

        result = _now_iso()
        assert isinstance(result, str)

    def test_contains_tz_info(self):
        from lab_manager.api.routes.chat import _now_iso

        result = _now_iso()
        # ISO format should contain a date and time separator
        assert "T" in result or " " in result


class TestAddMessage:
    """Tests for _add_message()."""

    def test_appends_to_history(self):
        from lab_manager.api.routes import chat as chat_mod

        msg = {"type": "message", "content": "hello"}
        chat_mod._add_message(msg)
        assert len(chat_mod._chat_history) == 1
        assert chat_mod._chat_history[0]["content"] == "hello"

    def test_returns_the_message(self):
        from lab_manager.api.routes.chat import _add_message

        msg = {"type": "message", "content": "test"}
        result = _add_message(msg)
        assert result is msg

    def test_trims_at_max_history(self):
        from lab_manager.api.routes import chat as chat_mod

        for i in range(110):
            chat_mod._add_message({"idx": i})
        assert len(chat_mod._chat_history) == 100

    def test_trimming_keeps_latest(self):
        from lab_manager.api.routes import chat as chat_mod

        for i in range(110):
            chat_mod._add_message({"idx": i})
        assert chat_mod._chat_history[0]["idx"] == 10
        assert chat_mod._chat_history[-1]["idx"] == 109


class TestParseMention:
    """Tests for _parse_mention()."""

    def test_standard_mention(self):
        from lab_manager.api.routes.chat import _parse_mention

        staff, query = _parse_mention("@inventory-manager list antibodies")
        assert staff == "inventory-manager"
        assert query == "list antibodies"

    def test_case_insensitive_staff_key(self):
        from lab_manager.api.routes.chat import _parse_mention

        staff, query = _parse_mention("@Inventory-Manager list")
        assert staff == "inventory-manager"

    def test_no_mention_returns_none(self):
        from lab_manager.api.routes.chat import _parse_mention

        staff, query = _parse_mention("just a message")
        assert staff is None
        assert query == "just a message"

    def test_leading_whitespace_stripped(self):
        from lab_manager.api.routes.chat import _parse_mention

        staff, query = _parse_mention("   @document-processor stats")
        assert staff == "document-processor"
        assert query == "stats"

    def test_mention_without_query(self):
        from lab_manager.api.routes.chat import _parse_mention

        staff, query = _parse_mention("@inventory-manager")
        assert staff == "inventory-manager"
        assert query == ""

    def test_special_chars_in_query(self):
        from lab_manager.api.routes.chat import _parse_mention

        staff, query = _parse_mention("@inventory-manager what's > 5mg?")
        assert staff == "inventory-manager"
        assert "what's > 5mg?" in query


class TestDigitalStaffRegistry:
    """Tests for staff registry functions."""

    def test_get_digital_staff_names_returns_list(self):
        from lab_manager.api.routes.chat import get_digital_staff_names

        names = get_digital_staff_names()
        assert isinstance(names, list)
        assert len(names) >= 2

    def test_built_in_staff_registered(self):
        from lab_manager.api.routes.chat import get_digital_staff_names

        names = get_digital_staff_names()
        assert "Document Processor" in names
        assert "Inventory Manager" in names

    def test_names_are_title_cased(self):
        from lab_manager.api.routes.chat import get_digital_staff_names

        names = get_digital_staff_names()
        for name in names:
            assert name == name.title().replace("-", " ")

    def test_register_staff_adds_handler(self):
        from lab_manager.api.routes import chat as chat_mod

        custom_handler = MagicMock(return_value="custom response")
        chat_mod._register_staff("test-bot", custom_handler)
        assert "test-bot" in chat_mod._STAFF_HANDLERS
        assert chat_mod._STAFF_HANDLERS["test-bot"] is custom_handler
        # Cleanup
        del chat_mod._STAFF_HANDLERS["test-bot"]


# ---------------------------------------------------------------------------
# Chat: staff handlers
# ---------------------------------------------------------------------------


class TestHandleInventoryManager:
    """Tests for _handle_inventory_manager()."""

    def test_no_db_returns_error(self):
        from lab_manager.api.routes.chat import _handle_inventory_manager

        result = _handle_inventory_manager("query", db=None)
        assert "Error" in result
        assert "no database" in result.lower()

    @patch("lab_manager.services.rag.ask")
    def test_returns_answer_from_rag(self, mock_ask):
        from lab_manager.api.routes.chat import _handle_inventory_manager

        mock_ask.return_value = {"answer": "5 vendors", "row_count": 5}
        db = MagicMock()
        result = _handle_inventory_manager("how many vendors?", db)
        assert "5 vendors" in result
        assert "(5 rows)" in result

    @patch("lab_manager.services.rag.ask")
    def test_answer_without_row_count(self, mock_ask):
        from lab_manager.api.routes.chat import _handle_inventory_manager

        mock_ask.return_value = {"answer": "some answer"}
        db = MagicMock()
        result = _handle_inventory_manager("question", db)
        assert result == "some answer"

    @patch("lab_manager.services.rag.ask")
    def test_empty_answer_returns_fallback(self, mock_ask):
        from lab_manager.api.routes.chat import _handle_inventory_manager

        mock_ask.return_value = {"answer": ""}
        db = MagicMock()
        result = _handle_inventory_manager("question", db)
        assert "No answer available" in result

    @patch("lab_manager.services.rag.ask", side_effect=Exception("RAG down"))
    def test_rag_exception_returns_error_message(self, mock_ask):
        from lab_manager.api.routes.chat import _handle_inventory_manager

        db = MagicMock()
        result = _handle_inventory_manager("question", db)
        assert "Sorry" in result
        assert "RAG down" in result


class TestHandleDocumentProcessor:
    """Tests for _handle_document_processor()."""

    def test_no_db_returns_error(self):
        from lab_manager.api.routes.chat import _handle_document_processor

        result = _handle_document_processor("query", db=None)
        assert "Error" in result

    def test_returns_document_stats(self):
        from lab_manager.api.routes.chat import _handle_document_processor

        db = MagicMock()
        # Mock total count query
        total_result = MagicMock()
        total_result.scalar.return_value = 10
        # Mock status breakdown query
        status_result = MagicMock()
        status_result.all.return_value = [("pending", 5), ("reviewed", 5)]

        db.execute.side_effect = [total_result, status_result]
        result = _handle_document_processor("stats", db)
        assert "Total documents: 10" in result
        assert "pending: 5" in result
        assert "reviewed: 5" in result

    def test_zero_documents(self):
        from lab_manager.api.routes.chat import _handle_document_processor

        db = MagicMock()
        total_result = MagicMock()
        total_result.scalar.return_value = 0
        status_result = MagicMock()
        status_result.all.return_value = []

        db.execute.side_effect = [total_result, status_result]
        result = _handle_document_processor("stats", db)
        assert "Total documents: 0" in result

    def test_db_error_returns_error_message(self):
        from lab_manager.api.routes.chat import _handle_document_processor

        db = MagicMock()
        db.execute.side_effect = Exception("connection lost")
        result = _handle_document_processor("stats", db)
        assert "Sorry" in result
        assert "connection lost" in result


# ---------------------------------------------------------------------------
# Chat: REST endpoints (via TestClient)
# ---------------------------------------------------------------------------


class TestChatHistoryEndpoint:
    """Tests for GET /api/v1/chat/history."""

    def test_empty_history(self, client):
        resp = client.get("/api/v1/chat/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_history_after_messages(self, client):
        client.post("/api/v1/chat/message", json={"from": "A", "content": "hi"})
        client.post("/api/v1/chat/message", json={"from": "B", "content": "hello"})
        resp = client.get("/api/v1/chat/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["from"] == "A"
        assert data[1]["from"] == "B"

    def test_history_limit_parameter(self, client):
        for i in range(10):
            client.post(
                "/api/v1/chat/message", json={"from": "U", "content": f"msg {i}"}
            )
        resp = client.get("/api/v1/chat/history?limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Should be last 3
        assert data[0]["content"] == "msg 7"
        assert data[2]["content"] == "msg 9"

    def test_history_limit_minimum_1(self, client):
        for i in range(5):
            client.post("/api/v1/chat/message", json={"from": "U", "content": f"m{i}"})
        resp = client.get("/api/v1/chat/history?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_history_limit_default_100(self, client):
        for i in range(150):
            client.post(
                "/api/v1/chat/message",
                json={"from": "U", "content": f"m{i}"},
            )
        resp = client.get("/api/v1/chat/history")
        assert resp.status_code == 200
        assert len(resp.json()) == 100

    def test_history_limit_exceeds_max_capped(self, client):
        for i in range(5):
            client.post("/api/v1/chat/message", json={"from": "U", "content": f"m{i}"})
        # limit > 100 should be capped by Query(le=100)
        resp = client.get("/api/v1/chat/history?limit=200")
        assert resp.status_code == 422


class TestSendMessageEndpoint:
    """Tests for POST /api/v1/chat/message."""

    def test_send_basic_message(self, client):
        resp = client.post(
            "/api/v1/chat/message", json={"from": "Alice", "content": "Hello"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_message_appears_in_history(self, client):
        client.post("/api/v1/chat/message", json={"from": "Bob", "content": "Test msg"})
        hist = client.get("/api/v1/chat/history").json()
        assert len(hist) == 1
        assert hist[0]["type"] == "message"
        assert hist[0]["from"] == "Bob"
        assert hist[0]["content"] == "Test msg"
        assert "timestamp" in hist[0]

    def test_message_missing_from_field(self, client):
        resp = client.post("/api/v1/chat/message", json={"content": "hello"})
        assert resp.status_code == 422

    def test_message_missing_content_field(self, client):
        resp = client.post("/api/v1/chat/message", json={"from": "Alice"})
        assert resp.status_code == 422

    def test_message_content_exceeds_max_length(self, client):
        resp = client.post(
            "/api/v1/chat/message",
            json={"from": "Alice", "content": "A" * 6000},
        )
        assert resp.status_code == 422

    def test_message_from_exceeds_max_length(self, client):
        resp = client.post(
            "/api/v1/chat/message",
            json={"from": "A" * 200, "content": "hi"},
        )
        assert resp.status_code == 422

    def test_mention_triggers_ai_response(self, client):
        resp = client.post(
            "/api/v1/chat/message",
            json={"from": "User", "content": "@document-processor show stats"},
        )
        assert resp.status_code == 200
        hist = client.get("/api/v1/chat/history").json()
        assert len(hist) == 2
        assert hist[1]["type"] == "ai_response"

    def test_unknown_mention_no_ai_response(self, client):
        client.post(
            "/api/v1/chat/message",
            json={"from": "U", "content": "@nonexistent-staff query"},
        )
        hist = client.get("/api/v1/chat/history").json()
        assert len(hist) == 1
        assert hist[0]["type"] == "message"

    def test_mention_without_query_no_ai_response(self, client):
        client.post(
            "/api/v1/chat/message",
            json={"from": "U", "content": "@inventory-manager"},
        )
        hist = client.get("/api/v1/chat/history").json()
        assert len(hist) == 1

    def test_handler_exception_returns_error_in_response(self, client):
        from lab_manager.api.routes import chat as chat_mod

        original = chat_mod._STAFF_HANDLERS.get("inventory-manager")
        chat_mod._STAFF_HANDLERS["inventory-manager"] = MagicMock(
            side_effect=RuntimeError("boom")
        )
        try:
            client.post(
                "/api/v1/chat/message",
                json={"from": "U", "content": "@inventory-manager test"},
            )
            hist = client.get("/api/v1/chat/history").json()
            assert len(hist) == 2
            assert hist[1]["type"] == "ai_response"
            assert "Error" in hist[1]["content"]
        finally:
            chat_mod._STAFF_HANDLERS["inventory-manager"] = original


class TestListStaffEndpoint:
    """Tests for GET /api/v1/chat/staff."""

    def test_returns_staff_list(self, client):
        resp = client.get("/api/v1/chat/staff")
        assert resp.status_code == 200
        data = resp.json()
        assert "staff" in data
        assert isinstance(data["staff"], list)
        assert "Document Processor" in data["staff"]
        assert "Inventory Manager" in data["staff"]


# ---------------------------------------------------------------------------
# Chat: WebSocket endpoint
# ---------------------------------------------------------------------------


class TestWebSocketChat:
    """Tests for the WebSocket /api/v1/chat/ws endpoint."""

    def test_ws_connect_receives_history(self, client):
        # Send a message first via REST
        client.post("/api/v1/chat/message", json={"from": "A", "content": "pre-ws"})
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "history"
            assert len(data["messages"]) >= 1

    def test_ws_send_message_broadcasts(self, client):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            # Receive history + join system message
            ws.receive_json()
            ws.receive_json()
            # Send a message
            ws.send_json({"from": "WSUser", "content": "ws hello"})
            # Should receive broadcast back
            data = ws.receive_json()
            assert data["type"] == "message"
            assert data["from"] == "WSUser"
            assert data["content"] == "ws hello"

    def test_ws_empty_content_ignored(self, client):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()  # history
            ws.receive_json()  # system join
            ws.send_json({"from": "U", "content": ""})
            ws.send_json({"from": "U", "content": "   "})
            # No broadcast should come for empty messages
            # Send a real one to verify state
            ws.send_json({"from": "U", "content": "real"})
            data = ws.receive_json()
            assert data["content"] == "real"

    def test_ws_invalid_json_returns_system_error(self, client):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()  # history
            ws.receive_json()  # system join
            ws.send_text("not json")
            data = ws.receive_json()
            assert data["type"] == "system"
            assert "Invalid message format" in data["content"]

    def test_ws_default_sender_is_user(self, client):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()  # history
            ws.receive_json()  # system join
            ws.send_json({"content": "test"})
            data = ws.receive_json()
            assert data["from"] == "user"

    def test_ws_content_truncated_to_5000(self, client):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()
            ws.receive_json()
            long_content = "A" * 10000
            ws.send_json({"from": "U", "content": long_content})
            data = ws.receive_json()
            assert len(data["content"]) == 5000

    def test_ws_sender_truncated_to_100(self, client):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()
            ws.receive_json()
            ws.send_json({"from": "B" * 200, "content": "hi"})
            data = ws.receive_json()
            assert len(data["from"]) == 100

    def test_ws_disconnect_adds_leave_message(self, client):
        from lab_manager.api.routes import chat as chat_mod

        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.receive_json()
            ws.receive_json()
        # After disconnect, a "left" system message should be in history
        hist = chat_mod._chat_history
        leave_msgs = [m for m in hist if m.get("content") == "A user left the chat."]
        assert len(leave_msgs) >= 1


# ---------------------------------------------------------------------------
# Ask: REST endpoints
# ---------------------------------------------------------------------------


class TestAskPostEndpoint:
    """Tests for POST /api/v1/ask."""

    @patch("lab_manager.api.routes.ask.ask")
    def test_happy_path(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "how many vendors?",
            "answer": "There are 5 vendors.",
            "sql": "SELECT COUNT(*) FROM vendors",
            "raw_results": [{"count": 5}],
            "row_count": 1,
            "source": "sql",
        }
        resp = client.post("/api/v1/ask", json={"question": "how many vendors?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "how many vendors?"
        assert data["answer"] == "There are 5 vendors."
        assert data["sql"] == "SELECT COUNT(*) FROM vendors"
        assert data["row_count"] == 1
        assert data["source"] == "sql"

    @patch("lab_manager.api.routes.ask.ask")
    def test_search_fallback_response(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "bad query",
            "answer": "Found 0 results via text search.",
            "raw_results": [],
            "row_count": None,
            "source": "search",
        }
        resp = client.post("/api/v1/ask", json={"question": "bad query"})
        assert resp.status_code == 200
        assert resp.json()["source"] == "search"

    def test_missing_question_field(self, client):
        resp = client.post("/api/v1/ask", json={})
        assert resp.status_code == 422

    def test_question_exceeds_max_length(self, client):
        resp = client.post("/api/v1/ask", json={"question": "Q" * 3000})
        assert resp.status_code == 422

    @patch("lab_manager.api.routes.ask.ask")
    def test_question_with_special_characters(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "what's < 5mg & > 2mg?",
            "answer": "3 items",
            "sql": None,
            "raw_results": [],
            "row_count": None,
            "source": "sql",
        }
        resp = client.post(
            "/api/v1/ask",
            json={"question": "what's < 5mg & > 2mg?"},
        )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "3 items"

    @patch("lab_manager.api.routes.ask.ask")
    def test_chinese_question(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "有多少供应商？",
            "answer": "有5个供应商。",
            "sql": "SELECT COUNT(*) FROM vendors",
            "raw_results": [{"count": 5}],
            "row_count": 1,
            "source": "sql",
        }
        resp = client.post("/api/v1/ask", json={"question": "有多少供应商？"})
        assert resp.status_code == 200
        assert "5" in resp.json()["answer"]

    @patch("lab_manager.api.routes.ask.ask")
    def test_empty_question_handled_by_service(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "",
            "answer": "Please provide a question.",
            "raw_results": [],
            "source": "sql",
        }
        resp = client.post("/api/v1/ask", json={"question": ""})
        assert resp.status_code == 200
        assert "Please provide" in resp.json()["answer"]

    @patch("lab_manager.api.routes.ask.ask")
    def test_response_includes_sql_field(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "q",
            "answer": "a",
            "sql": "SELECT 1 FROM vendors",
            "raw_results": [],
            "row_count": 0,
            "source": "sql",
        }
        resp = client.post("/api/v1/ask", json={"question": "q"})
        assert "sql" in resp.json()

    @patch("lab_manager.api.routes.ask.ask")
    def test_response_sql_can_be_null_for_search(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "q",
            "answer": "search result",
            "sql": None,
            "raw_results": [{"name": "X"}],
            "row_count": None,
            "source": "search",
        }
        resp = client.post("/api/v1/ask", json={"question": "q"})
        assert resp.json()["sql"] is None
        assert resp.json()["source"] == "search"

    @patch("lab_manager.api.routes.ask.ask", side_effect=Exception("DB exploded"))
    def test_service_exception_propagates(self, mock_ask, client):
        """Unhandled service exceptions propagate to the global error handler."""
        with pytest.raises(Exception, match="DB exploded"):
            client.post("/api/v1/ask", json={"question": "boom"})

    @patch("lab_manager.api.routes.ask.ask")
    def test_post_with_trailing_slash(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "q",
            "answer": "a",
            "sql": None,
            "raw_results": [],
            "source": "sql",
        }
        resp = client.post("/api/v1/ask/", json={"question": "q"})
        assert resp.status_code == 200


class TestAskGetEndpoint:
    """Tests for GET /api/v1/ask."""

    @patch("lab_manager.api.routes.ask.ask")
    def test_happy_path(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "how many?",
            "answer": "42",
            "sql": "SELECT COUNT(*) FROM vendors",
            "raw_results": [{"count": 42}],
            "row_count": 1,
            "source": "sql",
        }
        resp = client.get("/api/v1/ask?q=how+many?")
        assert resp.status_code == 200
        assert resp.json()["answer"] == "42"

    def test_missing_q_parameter(self, client):
        resp = client.get("/api/v1/ask")
        assert resp.status_code == 422

    @patch("lab_manager.api.routes.ask.ask")
    def test_get_with_trailing_slash(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "q",
            "answer": "a",
            "sql": None,
            "raw_results": [],
            "source": "sql",
        }
        resp = client.get("/api/v1/ask/?q=q")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.ask.ask")
    def test_url_encoded_question(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "what is this?",
            "answer": "something",
            "sql": None,
            "raw_results": [],
            "source": "sql",
        }
        resp = client.get("/api/v1/ask?q=what%20is%20this%3F")
        assert resp.status_code == 200
        assert resp.json()["answer"] == "something"


# ---------------------------------------------------------------------------
# Ask: auth dependency
# ---------------------------------------------------------------------------


class TestAskAuthDependency:
    """Tests verifying the ask route requires ask_ai permission."""

    def test_ask_route_has_auth_dependency(self):
        """Verify the ask router includes require_permission('ask_ai')."""
        from lab_manager.api.routes.ask import router

        # The router is created with dependencies=[Depends(require_permission("ask_ai"))]
        assert len(router.dependencies) >= 1

    def test_ask_permission_in_all_permissions(self):
        """Verify ask_ai is a recognized permission."""
        from lab_manager.api.auth import ALL_PERMISSIONS

        assert "ask_ai" in ALL_PERMISSIONS

    def test_postdoc_has_ask_ai(self):
        """Postdoc role should have ask_ai permission."""
        from lab_manager.api.auth import ROLE_PERMISSIONS

        assert "ask_ai" in ROLE_PERMISSIONS["postdoc"]

    def test_grad_student_has_ask_ai(self):
        from lab_manager.api.auth import ROLE_PERMISSIONS

        assert "ask_ai" in ROLE_PERMISSIONS["grad_student"]

    def test_visitor_no_ask_ai(self):
        from lab_manager.api.auth import ROLE_PERMISSIONS

        assert "ask_ai" not in ROLE_PERMISSIONS["visitor"]


# ---------------------------------------------------------------------------
# Chat: Pydantic models
# ---------------------------------------------------------------------------


class TestChatMessageModel:
    """Tests for ChatMessage and ChatMessageOut Pydantic models."""

    def test_chat_message_from_alias(self):
        from lab_manager.api.routes.chat import ChatMessage

        msg = ChatMessage.model_validate({"from": "Alice", "content": "hi"})
        assert msg.from_ == "Alice"
        assert msg.content == "hi"

    def test_chat_message_rejects_no_from(self):
        from pydantic import ValidationError

        from lab_manager.api.routes.chat import ChatMessage

        with pytest.raises(ValidationError):
            ChatMessage.model_validate({"content": "hi"})

    def test_chat_message_rejects_no_content(self):
        from pydantic import ValidationError

        from lab_manager.api.routes.chat import ChatMessage

        with pytest.raises(ValidationError):
            ChatMessage.model_validate({"from": "Alice"})

    def test_chat_message_out_from_alias(self):
        from lab_manager.api.routes.chat import ChatMessageOut

        msg = ChatMessageOut.model_validate(
            {
                "type": "message",
                "from": "Bob",
                "content": "hey",
                "timestamp": "2026-01-01",
            }
        )
        dumped = msg.model_dump(by_alias=True)
        assert "from" in dumped
        assert dumped["from"] == "Bob"


class TestAskRequestModel:
    """Tests for AskRequest Pydantic model."""

    def test_valid_request(self):
        from lab_manager.api.routes.ask import AskRequest

        req = AskRequest(question="how many vendors?")
        assert req.question == "how many vendors?"

    def test_missing_question(self):
        from pydantic import ValidationError

        from lab_manager.api.routes.ask import AskRequest

        with pytest.raises(ValidationError):
            AskRequest()

    def test_question_max_length_enforced(self):
        from pydantic import ValidationError

        from lab_manager.api.routes.ask import AskRequest

        with pytest.raises(ValidationError):
            AskRequest(question="Q" * 3000)

    def test_question_at_max_length_accepted(self):
        from lab_manager.api.routes.ask import AskRequest

        req = AskRequest(question="Q" * 2000)
        assert len(req.question) == 2000


class TestAskResponseModel:
    """Tests for AskResponse Pydantic model."""

    def test_full_response(self):
        from lab_manager.api.routes.ask import AskResponse

        resp = AskResponse(
            question="q",
            answer="a",
            sql="SELECT 1",
            raw_results=[{"x": 1}],
            row_count=1,
            source="sql",
        )
        assert resp.sql == "SELECT 1"
        assert resp.row_count == 1

    def test_minimal_response(self):
        from lab_manager.api.routes.ask import AskResponse

        resp = AskResponse(question="q", answer="a")
        assert resp.sql is None
        assert resp.raw_results == []
        assert resp.row_count is None
        assert resp.source == "sql"

    def test_search_source(self):
        from lab_manager.api.routes.ask import AskResponse

        resp = AskResponse(question="q", answer="a", source="search")
        assert resp.source == "search"


# ---------------------------------------------------------------------------
# Broadcast function
# ---------------------------------------------------------------------------


class TestBroadcast:
    """Tests for _broadcast()."""

    def test_broadcast_sends_to_all_clients(self):
        from lab_manager.api.routes import chat as chat_mod

        ws1 = MagicMock()
        ws2 = MagicMock()
        chat_mod._connected_clients.extend([ws1, ws2])

        with patch("asyncio.get_event_loop") as mock_loop:
            loop = MagicMock()
            mock_loop.return_value = loop
            chat_mod._broadcast({"type": "test", "content": "hello"})
            assert loop.create_task.call_count == 2

    def test_broadcast_empty_clients_list(self):
        from lab_manager.api.routes import chat as chat_mod

        chat_mod._connected_clients.clear()
        # Should not raise
        chat_mod._broadcast({"type": "test"})
