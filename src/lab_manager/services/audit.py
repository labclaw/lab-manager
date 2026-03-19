"""Automatic audit trail via SQLAlchemy session events."""

from __future__ import annotations

import contextvars

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from lab_manager.models.audit import AuditLog
from lab_manager.models.base import AuditMixin, utcnow
from lab_manager.services.serialization import serialize_value as _serialize_value

# Context variable to track the current user per-request.
_current_user: contextvars.ContextVar[str | None] = contextvars.ContextVar("_current_user", default=None)


def set_current_user(user: str | None) -> None:
    _current_user.set(user)


def get_current_user() -> str | None:
    return _current_user.get()


def _is_auditable(obj: object) -> bool:
    """Return True if the object's class extends AuditMixin (table model)."""
    # AuditLog itself should not be audited to avoid infinite recursion.
    if isinstance(obj, AuditLog):
        return False
    return isinstance(obj, AuditMixin)


# Fields that are managed by AuditMixin and should not show up as user-changes.
_SKIP_FIELDS = {"created_at", "updated_at"}


def _get_table_name(obj: object) -> str:
    mapper = inspect(type(obj))
    return mapper.persist_selectable.name  # type: ignore[union-attr]


def _get_record_id(obj: object) -> int | None:
    mapper = inspect(type(obj))
    pk_cols = mapper.primary_key
    if pk_cols:
        return getattr(obj, pk_cols[0].name, None)
    return None


def _snapshot(obj: object) -> dict:
    """Return all column values as a dict (for create / delete)."""
    mapper = inspect(type(obj))
    result = {}
    for col in mapper.columns:
        if col.key in _SKIP_FIELDS:
            continue
        result[col.key] = _serialize_value(getattr(obj, col.key, None))
    return result


def _diff(session: Session, obj: object) -> dict | None:
    """Return changed fields with old->new values.  None if no changes.

    Accepts *session* so we can query committed values when attributes were
    expired before modification (expired attrs have NO_VALUE in committed_state).
    """
    from sqlalchemy.orm.attributes import instance_state
    from sqlalchemy.orm.base import LoaderCallableStatus

    state = instance_state(obj)
    mapper = inspect(type(obj))

    # Detect which column keys have pending changes (added != empty).
    changed_keys: list[str] = []
    for prop in mapper.column_attrs:
        key = prop.key
        if key in _SKIP_FIELDS:
            continue
        hist = state.get_history(key, 0)  # passive — no DB hit
        if hist.added:
            changed_keys.append(key)

    if not changed_keys:
        return None

    # For old values we check committed_state; if NO_VALUE, fetch from DB.
    committed = state.committed_state
    need_db_load = any(isinstance(committed.get(k), LoaderCallableStatus) or k not in committed for k in changed_keys)

    old_values: dict = {}
    if need_db_load:
        # Query the current DB row for the committed values.
        pk_col = mapper.primary_key[0]
        pk_val = getattr(obj, pk_col.name)
        from sqlalchemy import select

        row = session.execute(
            select(*[mapper.columns[k] for k in changed_keys]).where(mapper.columns[pk_col.name] == pk_val)
        ).first()
        if row:
            old_values = dict(zip(changed_keys, row, strict=False))
    else:
        for k in changed_keys:
            old_values[k] = committed.get(k)

    changes: dict = {}
    for key in changed_keys:
        hist = state.get_history(key, 0)
        new = hist.added[0] if hist.added else None
        old = old_values.get(key)
        changes[key] = {
            "old": _serialize_value(old),
            "new": _serialize_value(new),
        }
    return changes


# We collect audit data in before_flush (while history is still available)
# and write the entries in after_flush (when PKs have been assigned).
_PENDING_KEY = "_audit_pending"


@event.listens_for(Session, "before_flush")
def _before_flush(session: Session, flush_context: object, instances: object) -> None:
    """Capture change data before SQLAlchemy consumes attribute history."""
    user = get_current_user()
    pending: list[dict] = []

    # --- UPDATES (history only available before flush) ---
    for obj in list(session.dirty):
        if not _is_auditable(obj):
            continue
        if not session.is_modified(obj, include_collections=False):
            continue
        changes = _diff(session, obj)
        if not changes:
            continue
        pending.append(
            {
                "obj": obj,
                "action": "update",
                "user": user,
                "changes": changes,
            }
        )

    # --- DELETES (snapshot before the object is gone) ---
    for obj in list(session.deleted):
        if not _is_auditable(obj):
            continue
        pending.append(
            {
                "obj": obj,
                "action": "delete",
                "user": user,
                "changes": _snapshot(obj),
            }
        )

    # Store on session info dict so after_flush can retrieve it.
    session.info[_PENDING_KEY] = pending


@event.listens_for(Session, "after_flush")
def _after_flush(session: Session, flush_context: object) -> None:
    """Create AuditLog entries after flush when PKs are assigned."""
    user = get_current_user()
    entries: list[AuditLog] = []

    # --- CREATES (PKs now available after flush) ---
    for obj in list(session.new):
        if not _is_auditable(obj):
            continue
        record_id = _get_record_id(obj)
        if record_id is None:
            continue
        entries.append(
            AuditLog(
                table_name=_get_table_name(obj),
                record_id=record_id,
                action="create",
                changed_by=user,
                changes=_snapshot(obj),
                timestamp=utcnow(),
            )
        )

    # --- UPDATES & DELETES (from before_flush) ---
    pending: list[dict] = session.info.pop(_PENDING_KEY, [])
    for item in pending:
        obj = item["obj"]
        record_id = _get_record_id(obj)
        if record_id is None:
            continue
        entries.append(
            AuditLog(
                table_name=_get_table_name(obj),
                record_id=record_id,
                action=item["action"],
                changed_by=item["user"],
                changes=item["changes"],
                timestamp=utcnow(),
            )
        )

    for entry in entries:
        session.add(entry)
