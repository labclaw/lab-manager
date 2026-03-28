"""Equipment reservation API endpoint tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from lab_manager.models.staff import Staff


def _make_equipment(client, name="Centrifuge A"):
    r = client.post(
        "/api/v1/equipment/",
        json={"name": name, "category": "centrifuge"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def _make_staff(db_session, name="Alice", email="alice@example.com"):
    staff = Staff(name=name, email=email, role="grad_student", role_level=3)
    db_session.add(staff)
    db_session.flush()
    return staff.id


def _base_time():
    """Return a fixed future datetime for consistent tests."""
    return datetime(2030, 6, 1, 10, 0, 0)


def test_create_reservation(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    start = _base_time().isoformat()
    end = (_base_time() + timedelta(hours=2)).isoformat()
    r = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": start,
            "end_time": end,
            "purpose": "DNA extraction",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["equipment_id"] == eid
    assert data["staff_id"] == sid
    assert data["status"] == "confirmed"
    assert data["purpose"] == "DNA extraction"
    assert data["id"] is not None


def test_conflict_detection_overlapping_rejected(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()

    # First reservation: 10:00 - 12:00
    r1 = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    assert r1.status_code == 201

    # Overlapping: 11:00 - 13:00 (overlaps with 10:00 - 12:00)
    r2 = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": (base + timedelta(hours=1)).isoformat(),
            "end_time": (base + timedelta(hours=3)).isoformat(),
        },
    )
    assert r2.status_code == 409
    assert "already reserved" in r2.json()["detail"]


def test_no_conflict_different_equipment(client, db_session):
    eid1 = _make_equipment(client, "Centrifuge A")
    eid2 = _make_equipment(client, "Centrifuge B")
    sid = _make_staff(db_session)
    base = _base_time()

    for eid in [eid1, eid2]:
        r = client.post(
            "/api/v1/reservations/",
            json={
                "equipment_id": eid,
                "staff_id": sid,
                "start_time": base.isoformat(),
                "end_time": (base + timedelta(hours=2)).isoformat(),
            },
        )
        assert r.status_code == 201


def test_no_conflict_adjacent_times(client, db_session):
    """Reservations that end exactly when the next starts should not conflict."""
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()

    # 10:00 - 12:00
    r1 = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    assert r1.status_code == 201

    # 12:00 - 14:00 (starts exactly when first ends, no overlap)
    r2 = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": (base + timedelta(hours=2)).isoformat(),
            "end_time": (base + timedelta(hours=4)).isoformat(),
        },
    )
    assert r2.status_code == 201


def test_cancel_reservation(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()

    r = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    rid = r.json()["id"]

    # Cancel
    r2 = client.delete(f"/api/v1/reservations/{rid}")
    assert r2.status_code == 200
    assert r2.json()["status"] == "cancelled"


def test_cancel_already_cancelled_rejected(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()

    r = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    rid = r.json()["id"]
    client.delete(f"/api/v1/reservations/{rid}")

    # Try cancelling again
    r2 = client.delete(f"/api/v1/reservations/{rid}")
    assert r2.status_code == 409


def test_list_reservations(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()

    client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=1)).isoformat(),
        },
    )
    client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": (base + timedelta(hours=2)).isoformat(),
            "end_time": (base + timedelta(hours=3)).isoformat(),
        },
    )

    r = client.get("/api/v1/reservations/")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2


def test_list_by_equipment(client, db_session):
    eid1 = _make_equipment(client, "Eq A")
    eid2 = _make_equipment(client, "Eq B")
    sid = _make_staff(db_session)
    base = _base_time()

    client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid1,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=1)).isoformat(),
        },
    )
    client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid2,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=1)).isoformat(),
        },
    )

    r = client.get(f"/api/v1/reservations/?equipment_id={eid1}")
    assert r.json()["total"] == 1


def test_check_availability_free(client, db_session):
    eid = _make_equipment(client)
    base = _base_time()

    r = client.get(
        f"/api/v1/reservations/equipment/{eid}/availability"
        f"?start_time={base.isoformat()}"
        f"&end_time={(base + timedelta(hours=2)).isoformat()}"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert len(data["conflicting_reservations"]) == 0


def test_check_availability_booked(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()

    client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )

    r = client.get(
        f"/api/v1/reservations/equipment/{eid}/availability"
        f"?start_time={(base + timedelta(hours=1)).isoformat()}"
        f"&end_time={(base + timedelta(hours=3)).isoformat()}"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["available"] is False
    assert len(data["conflicting_reservations"]) == 1


def test_create_reservation_invalid_equipment(client, db_session):
    sid = _make_staff(db_session)
    base = _base_time()
    r = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": 99999,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 404


def test_create_reservation_end_before_start(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()
    r = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base - timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 422


def test_cancelled_slot_can_be_rebooked(client, db_session):
    eid = _make_equipment(client)
    sid = _make_staff(db_session)
    base = _base_time()

    r1 = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    rid = r1.json()["id"]
    client.delete(f"/api/v1/reservations/{rid}")

    # Rebook the same slot
    r2 = client.post(
        "/api/v1/reservations/",
        json={
            "equipment_id": eid,
            "staff_id": sid,
            "start_time": base.isoformat(),
            "end_time": (base + timedelta(hours=2)).isoformat(),
        },
    )
    assert r2.status_code == 201
