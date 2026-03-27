"""Unit tests for Invitation, UsageEvent, OrderRequest, Notification, and NotificationPreference models."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.invitation import Invitation
from lab_manager.models.notification import Notification, NotificationPreference
from lab_manager.models.order_request import OrderRequest, RequestStatus, RequestUrgency
from lab_manager.models.staff import Staff
from lab_manager.models.usage_event import UsageEvent


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def mock_staff(session: Session) -> Staff:
    staff = Staff(name="Test User", email="test@example.com", role="admin")
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


# ============================================================
# Invitation
# ============================================================


class TestInvitation:
    def test_create_with_required_fields(self, session, mock_staff):
        inv = Invitation(
            email="newuser@example.com",
            name="New User",
            role="member",
            token="tok_abc123xyz",
            invited_by=mock_staff.id,
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)

        assert inv.id is not None
        assert inv.email == "newuser@example.com"
        assert inv.name == "New User"
        assert inv.role == "member"
        assert inv.token == "tok_abc123xyz"
        assert inv.invited_by == mock_staff.id

    def test_default_status_is_pending(self, session):
        inv = Invitation(
            email="pending@example.com",
            name="Pending",
            role="member",
            token="tok_pending",
        )
        assert inv.status == "pending"

    def test_optional_timestamps_default_none(self, session):
        inv = Invitation(
            email="ts@example.com",
            name="TS",
            role="member",
            token="tok_ts",
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)

        assert inv.accepted_at is None
        assert inv.expires_at is None
        assert inv.access_expires_at is None

    def test_set_all_timestamps(self, session):
        now = datetime(2026, 3, 27, 10, 0, 0)
        inv = Invitation(
            email="full@example.com",
            name="Full",
            role="member",
            token="tok_full",
            accepted_at=now,
            expires_at=datetime(2026, 4, 27, 10, 0, 0),
            access_expires_at=datetime(2026, 5, 27, 10, 0, 0),
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)

        assert inv.accepted_at == now
        assert inv.expires_at.year == 2026
        assert inv.access_expires_at.month == 5

    def test_status_values(self, session):
        for status in ["pending", "accepted", "cancelled", "expired"]:
            inv = Invitation(
                email=f"{status}@example.com",
                name=status,
                role="member",
                token=f"tok_{status}",
                status=status,
            )
            session.add(inv)
        session.commit()

        from sqlmodel import select

        invs = session.exec(select(Invitation)).all()
        statuses = {i.status for i in invs}
        assert statuses == {"pending", "accepted", "cancelled", "expired"}

    def test_audit_mixin_fields_present(self):
        fields = {f for f in Invitation.model_fields}
        assert "created_at" in fields
        assert "updated_at" in fields
        assert "created_by" in fields

    def test_invited_by_is_optional(self, session):
        inv = Invitation(
            email="noinviter@example.com",
            name="No Inviter",
            role="member",
            token="tok_noinviter",
        )
        session.add(inv)
        session.commit()
        session.refresh(inv)

        assert inv.invited_by is None


# ============================================================
# UsageEvent
# ============================================================


class TestUsageEvent:
    def test_create_with_required_fields(self, session):
        event = UsageEvent(
            user_email="user@example.com",
            event_type="page_view",
            page="/inventory",
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        assert event.id is not None
        assert event.user_email == "user@example.com"
        assert event.event_type == "page_view"
        assert event.page == "/inventory"

    def test_optional_page_and_metadata(self, session):
        event = UsageEvent(
            user_email="bare@example.com",
            event_type="login",
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        assert event.page is None
        assert event.metadata_ is None

    def test_metadata_json(self, session):
        event = UsageEvent(
            user_email="meta@example.com",
            event_type="click",
            page="/orders",
            metadata_={"button": "export", "format": "csv"},
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        assert event.metadata_["button"] == "export"
        assert event.metadata_["format"] == "csv"

    def test_event_type_varieties(self, session):
        for i, etype in enumerate(["page_view", "login", "logout", "click", "search"]):
            event = UsageEvent(
                user_email=f"etype{i}@example.com",
                event_type=etype,
            )
            session.add(event)
        session.commit()

        from sqlmodel import select

        events = session.exec(select(UsageEvent)).all()
        types = {e.event_type for e in events}
        assert types == {"page_view", "login", "logout", "click", "search"}

    def test_audit_mixin_fields_present(self):
        fields = {f for f in UsageEvent.model_fields}
        assert "created_at" in fields
        assert "updated_at" in fields


# ============================================================
# OrderRequest + enums
# ============================================================


class TestRequestStatusEnum:
    def test_enum_members(self):
        assert RequestStatus.pending.value == "pending"
        assert RequestStatus.approved.value == "approved"
        assert RequestStatus.rejected.value == "rejected"
        assert RequestStatus.cancelled.value == "cancelled"

    def test_enum_is_string(self):
        for member in RequestStatus:
            assert isinstance(member, str)

    def test_member_count(self):
        assert len(RequestStatus) == 4


class TestRequestUrgencyEnum:
    def test_enum_members(self):
        assert RequestUrgency.normal.value == "normal"
        assert RequestUrgency.urgent.value == "urgent"

    def test_enum_is_string(self):
        for member in RequestUrgency:
            assert isinstance(member, str)

    def test_member_count(self):
        assert len(RequestUrgency) == 2


class TestOrderRequest:
    def test_create_with_required_fields(self, session, mock_staff):
        req = OrderRequest(
            requested_by=mock_staff.id,
            description="Need 10x PBS buffer",
            quantity=Decimal("5.0000"),
        )
        session.add(req)
        session.commit()
        session.refresh(req)

        assert req.id is not None
        assert req.requested_by == mock_staff.id
        assert req.description == "Need 10x PBS buffer"

    def test_default_status_is_pending(self, session, mock_staff):
        req = OrderRequest(requested_by=mock_staff.id)
        session.add(req)
        session.commit()
        session.refresh(req)

        assert req.status == "pending"

    def test_default_urgency_is_normal(self, session, mock_staff):
        req = OrderRequest(requested_by=mock_staff.id)
        assert req.urgency == "normal"

    def test_default_quantity_is_one(self, session, mock_staff):
        req = OrderRequest(requested_by=mock_staff.id)
        session.add(req)
        session.commit()
        session.refresh(req)

        assert req.quantity == 1

    def test_optional_fields_default_none(self, session, mock_staff):
        req = OrderRequest(requested_by=mock_staff.id)
        session.add(req)
        session.commit()
        session.refresh(req)

        assert req.product_id is None
        assert req.vendor_id is None
        assert req.catalog_number is None
        assert req.unit is None
        assert req.estimated_price is None
        assert req.justification is None
        assert req.reviewed_by is None
        assert req.review_note is None
        assert req.order_id is None
        assert req.reviewed_at is None

    def test_full_request_with_all_fields(self, session, mock_staff):
        now = datetime(2026, 3, 27, 14, 0, 0)
        req = OrderRequest(
            requested_by=mock_staff.id,
            product_id=1,
            vendor_id=2,
            catalog_number="AB-1031",
            description="Antibody for IHC",
            quantity=Decimal("3.0000"),
            unit="each",
            estimated_price=Decimal("150.0000"),
            justification="Running low on stock",
            urgency="urgent",
            status="approved",
            reviewed_by=mock_staff.id,
            review_note="Approved for purchase",
            reviewed_at=now,
        )
        session.add(req)
        session.commit()
        session.refresh(req)

        assert req.catalog_number == "AB-1031"
        assert req.unit == "each"
        assert req.estimated_price == Decimal("150.0000")
        assert req.urgency == "urgent"
        assert req.status == "approved"
        assert req.review_note == "Approved for purchase"

    def test_audit_mixin_fields_present(self):
        fields = {f for f in OrderRequest.model_fields}
        assert "created_at" in fields
        assert "updated_at" in fields
        assert "created_by" in fields


# ============================================================
# Notification
# ============================================================


class TestNotification:
    def test_create_with_required_fields(self, session, mock_staff):
        notif = Notification(
            staff_id=mock_staff.id,
            type="order_request",
            title="New order request",
            message="A new order request needs your approval",
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)

        assert notif.id is not None
        assert notif.staff_id == mock_staff.id
        assert notif.type == "order_request"
        assert notif.title == "New order request"

    def test_default_is_read_false(self, session, mock_staff):
        notif = Notification(
            staff_id=mock_staff.id,
            type="info",
            title="Test",
            message="Test message",
        )
        assert notif.is_read is False

    def test_optional_fields_default_none(self, session, mock_staff):
        notif = Notification(
            staff_id=mock_staff.id,
            type="info",
            title="T",
            message="M",
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)

        assert notif.link is None
        assert notif.read_at is None

    def test_mark_as_read(self, session, mock_staff):
        now = datetime(2026, 3, 27, 15, 0, 0)
        notif = Notification(
            staff_id=mock_staff.id,
            type="alert",
            title="Low stock",
            message="Item X is below threshold",
            is_read=True,
            read_at=now,
            link="/inventory/1",
        )
        session.add(notif)
        session.commit()
        session.refresh(notif)

        assert notif.is_read is True
        assert notif.read_at == now
        assert notif.link == "/inventory/1"

    def test_notification_type_varieties(self, session, mock_staff):
        for i, ntype in enumerate(
            ["order_request", "document_review", "inventory_alert", "team_change"]
        ):
            notif = Notification(
                staff_id=mock_staff.id,
                type=ntype,
                title=f"Title {i}",
                message=f"Message {i}",
            )
            session.add(notif)
        session.commit()

        from sqlmodel import select

        notifs = session.exec(select(Notification)).all()
        types = {n.type for n in notifs}
        assert types == {
            "order_request",
            "document_review",
            "inventory_alert",
            "team_change",
        }

    def test_audit_mixin_fields_present(self):
        fields = {f for f in Notification.model_fields}
        assert "created_at" in fields
        assert "updated_at" in fields


# ============================================================
# NotificationPreference
# ============================================================


class TestNotificationPreference:
    def test_create_with_staff_id(self, session, mock_staff):
        pref = NotificationPreference(staff_id=mock_staff.id)
        session.add(pref)
        session.commit()
        session.refresh(pref)

        assert pref.id is not None
        assert pref.staff_id == mock_staff.id

    def test_default_booleans(self, session, mock_staff):
        pref = NotificationPreference(staff_id=mock_staff.id)
        session.add(pref)
        session.commit()
        session.refresh(pref)

        assert pref.in_app is True
        assert pref.email_weekly is False
        assert pref.order_requests is True
        assert pref.document_reviews is True
        assert pref.inventory_alerts is True
        assert pref.team_changes is True

    def test_override_all_preferences(self, session, mock_staff):
        pref = NotificationPreference(
            staff_id=mock_staff.id,
            in_app=False,
            email_weekly=True,
            order_requests=False,
            document_reviews=False,
            inventory_alerts=False,
            team_changes=False,
        )
        session.add(pref)
        session.commit()
        session.refresh(pref)

        assert pref.in_app is False
        assert pref.email_weekly is True
        assert pref.order_requests is False
        assert pref.document_reviews is False
        assert pref.inventory_alerts is False
        assert pref.team_changes is False

    def test_audit_mixin_fields_present(self):
        fields = {f for f in NotificationPreference.model_fields}
        assert "created_at" in fields
        assert "updated_at" in fields
        assert "created_by" in fields
