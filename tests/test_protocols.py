"""Protocol navigator API endpoint tests."""

from __future__ import annotations


# --- Protocol CRUD ---


def test_create_protocol(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "Western Blot Protocol",
            "description": "Standard western blot procedure",
            "category": "molecular_biology",
            "steps": [
                {
                    "step_num": 1,
                    "title": "Prepare samples",
                    "description": "Lyse cells and quantify protein",
                    "duration_min": 30,
                    "warning": "Keep samples on ice",
                },
                {
                    "step_num": 2,
                    "title": "Run gel",
                    "description": "Load samples onto SDS-PAGE gel",
                    "duration_min": 60,
                },
            ],
            "estimated_duration_min": 240,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Western Blot Protocol"
    assert data["category"] == "molecular_biology"
    assert data["status"] == "draft"
    assert len(data["steps"]) == 2
    assert data["steps"][0]["title"] == "Prepare samples"
    assert data["steps"][0]["warning"] == "Keep samples on ice"
    assert data["estimated_duration_min"] == 240
    assert data["id"] is not None


def test_create_protocol_minimal(client):
    r = client.post(
        "/api/v1/protocols/",
        json={"title": "Simple Protocol"},
    )
    assert r.status_code == 201
    assert r.json()["title"] == "Simple Protocol"
    assert r.json()["steps"] == []
    assert r.json()["status"] == "draft"


def test_get_protocol(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "PCR Protocol",
            "steps": [{"step_num": 1, "title": "Mix reagents"}],
        },
    )
    pid = r.json()["id"]
    r = client.get(f"/api/v1/protocols/{pid}")
    assert r.status_code == 200
    assert r.json()["title"] == "PCR Protocol"
    assert len(r.json()["steps"]) == 1


def test_get_protocol_404(client):
    r = client.get("/api/v1/protocols/99999")
    assert r.status_code == 404


def test_update_protocol(client):
    r = client.post(
        "/api/v1/protocols/",
        json={"title": "Old Title", "category": "biochemistry"},
    )
    pid = r.json()["id"]
    r = client.patch(
        f"/api/v1/protocols/{pid}",
        json={"title": "New Title", "category": "molecular_biology"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "New Title"
    assert r.json()["category"] == "molecular_biology"


def test_update_protocol_steps(client):
    r = client.post(
        "/api/v1/protocols/",
        json={"title": "Protocol", "steps": [{"step_num": 1, "title": "Step 1"}]},
    )
    pid = r.json()["id"]
    r = client.patch(
        f"/api/v1/protocols/{pid}",
        json={
            "steps": [
                {"step_num": 1, "title": "Revised Step 1"},
                {"step_num": 2, "title": "New Step 2"},
            ]
        },
    )
    assert r.status_code == 200
    assert len(r.json()["steps"]) == 2
    assert r.json()["steps"][0]["title"] == "Revised Step 1"


def test_list_protocols(client):
    client.post("/api/v1/protocols/", json={"title": "A", "category": "mb"})
    client.post("/api/v1/protocols/", json={"title": "B", "category": "biochem"})
    r = client.get("/api/v1/protocols/")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


def test_filter_by_category(client):
    client.post("/api/v1/protocols/", json={"title": "A", "category": "pcr"})
    client.post("/api/v1/protocols/", json={"title": "B", "category": "pcr"})
    client.post("/api/v1/protocols/", json={"title": "C", "category": "wb"})
    r = client.get("/api/v1/protocols/?category=pcr")
    assert len(r.json()["items"]) == 2


def test_filter_by_status(client):
    client.post("/api/v1/protocols/", json={"title": "Draft"})
    r2 = client.post(
        "/api/v1/protocols/",
        json={"title": "Published", "status": "published"},
    )
    r = client.get("/api/v1/protocols/?status=published")
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["title"] == "Published"


def test_search_protocols(client):
    client.post("/api/v1/protocols/", json={"title": "Western Blot"})
    client.post("/api/v1/protocols/", json={"title": "PCR"})
    r = client.get("/api/v1/protocols/?search=blot")
    assert len(r.json()["items"]) == 1


# --- Execution tracking ---


def test_start_execution(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "Test Protocol",
            "steps": [
                {"step_num": 1, "title": "Step 1"},
                {"step_num": 2, "title": "Step 2"},
                {"step_num": 3, "title": "Step 3"},
            ],
        },
    )
    pid = r.json()["id"]
    r = client.post(f"/api/v1/protocols/{pid}/start")
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "in_progress"
    assert data["current_step"] == 0
    assert data["protocol_id"] == pid


def test_start_execution_no_steps(client):
    r = client.post(
        "/api/v1/protocols/",
        json={"title": "Empty Protocol"},
    )
    pid = r.json()["id"]
    r = client.post(f"/api/v1/protocols/{pid}/start")
    assert r.status_code == 422


def test_advance_execution(client):
    # Create protocol with 3 steps
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "3-Step Protocol",
            "steps": [
                {"step_num": 1, "title": "Step 1"},
                {"step_num": 2, "title": "Step 2"},
                {"step_num": 3, "title": "Step 3"},
            ],
        },
    )
    pid = r.json()["id"]
    # Start execution
    r = client.post(f"/api/v1/protocols/{pid}/start")
    exec_id = r.json()["id"]
    assert r.json()["current_step"] == 0
    # Advance to step 1
    r = client.post(f"/api/v1/protocols/executions/{exec_id}/advance")
    assert r.status_code == 200
    assert r.json()["current_step"] == 1
    # Advance to step 2
    r = client.post(f"/api/v1/protocols/executions/{exec_id}/advance")
    assert r.json()["current_step"] == 2


def test_advance_with_notes(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "Protocol",
            "steps": [
                {"step_num": 1, "title": "Step 1"},
                {"step_num": 2, "title": "Step 2"},
            ],
        },
    )
    pid = r.json()["id"]
    r = client.post(f"/api/v1/protocols/{pid}/start")
    exec_id = r.json()["id"]
    r = client.post(
        f"/api/v1/protocols/executions/{exec_id}/advance",
        json={"notes": "Step 0 completed successfully"},
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "Step 0 completed successfully"


def test_advance_past_last_step(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "2-Step",
            "steps": [
                {"step_num": 1, "title": "Step 1"},
                {"step_num": 2, "title": "Step 2"},
            ],
        },
    )
    pid = r.json()["id"]
    r = client.post(f"/api/v1/protocols/{pid}/start")
    exec_id = r.json()["id"]
    # Advance once (to step 1)
    client.post(f"/api/v1/protocols/executions/{exec_id}/advance")
    # Try advance again (at last step, index 1 of 2)
    r = client.post(f"/api/v1/protocols/executions/{exec_id}/advance")
    assert r.status_code == 400


def test_complete_execution(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "Protocol",
            "steps": [{"step_num": 1, "title": "Only step"}],
        },
    )
    pid = r.json()["id"]
    r = client.post(f"/api/v1/protocols/{pid}/start")
    exec_id = r.json()["id"]
    r = client.post(
        f"/api/v1/protocols/executions/{exec_id}/complete",
        json={"notes": "All done"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None
    assert data["notes"] == "All done"


def test_cannot_advance_completed(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "Protocol",
            "steps": [
                {"step_num": 1, "title": "Step 1"},
                {"step_num": 2, "title": "Step 2"},
            ],
        },
    )
    pid = r.json()["id"]
    r = client.post(f"/api/v1/protocols/{pid}/start")
    exec_id = r.json()["id"]
    # Complete it
    client.post(f"/api/v1/protocols/executions/{exec_id}/complete")
    # Try to advance a completed execution
    r = client.post(f"/api/v1/protocols/executions/{exec_id}/advance")
    assert r.status_code == 400


def test_cannot_complete_twice(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "Protocol",
            "steps": [{"step_num": 1, "title": "Step 1"}],
        },
    )
    pid = r.json()["id"]
    r = client.post(f"/api/v1/protocols/{pid}/start")
    exec_id = r.json()["id"]
    # Complete once
    client.post(f"/api/v1/protocols/executions/{exec_id}/complete")
    # Complete again
    r = client.post(f"/api/v1/protocols/executions/{exec_id}/complete")
    assert r.status_code == 400


def test_list_executions(client):
    # Create protocol
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "Protocol",
            "steps": [{"step_num": 1, "title": "Step 1"}],
        },
    )
    pid = r.json()["id"]
    # Start two executions
    client.post(f"/api/v1/protocols/{pid}/start")
    client.post(f"/api/v1/protocols/{pid}/start")
    r = client.get("/api/v1/protocols/executions/")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


def test_list_executions_filter_by_protocol(client):
    r1 = client.post(
        "/api/v1/protocols/",
        json={
            "title": "P1",
            "steps": [{"step_num": 1, "title": "S1"}],
        },
    )
    pid1 = r1.json()["id"]
    r2 = client.post(
        "/api/v1/protocols/",
        json={
            "title": "P2",
            "steps": [{"step_num": 1, "title": "S1"}],
        },
    )
    pid2 = r2.json()["id"]
    client.post(f"/api/v1/protocols/{pid1}/start")
    client.post(f"/api/v1/protocols/{pid2}/start")
    client.post(f"/api/v1/protocols/{pid2}/start")
    r = client.get(f"/api/v1/protocols/executions/?protocol_id={pid2}")
    assert len(r.json()["items"]) == 2


def test_list_executions_filter_by_status(client):
    r = client.post(
        "/api/v1/protocols/",
        json={
            "title": "P",
            "steps": [{"step_num": 1, "title": "S1"}],
        },
    )
    pid = r.json()["id"]
    r1 = client.post(f"/api/v1/protocols/{pid}/start")
    client.post(f"/api/v1/protocols/{pid}/start")
    # Complete one
    client.post(f"/api/v1/protocols/executions/{r1.json()['id']}/complete")
    r = client.get("/api/v1/protocols/executions/?status=completed")
    assert len(r.json()["items"]) == 1
    r = client.get("/api/v1/protocols/executions/?status=in_progress")
    assert len(r.json()["items"]) == 1


def test_execution_404(client):
    r = client.post("/api/v1/protocols/executions/99999/advance")
    assert r.status_code == 404


def test_advance_execution_404(client):
    r = client.post("/api/v1/protocols/executions/99999/complete")
    assert r.status_code == 404


def test_list_protocols_pagination(client):
    for i in range(5):
        client.post("/api/v1/protocols/", json={"title": f"Protocol {i}"})
    r = client.get("/api/v1/protocols/?page=1&page_size=2")
    data = r.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["pages"] == 3
