"""Tests for Lab IM chat REST API endpoints."""

from __future__ import annotations


def test_chat_history_empty(client):
    """History endpoint returns empty list when no messages sent."""
    resp = client.get("/api/v1/chat/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_send_message(client):
    """POST /message stores and returns the message."""
    # Import here to reset state between tests
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()

    resp = client.post(
        "/api/v1/chat/message",
        json={"from": "Alice", "content": "Hello team!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

    # Check history now has the message
    hist = client.get("/api/v1/chat/history").json()
    assert len(hist) >= 1
    msg = hist[-1]
    assert msg["type"] == "message"
    assert msg["from"] == "Alice"
    assert msg["content"] == "Hello team!"
    assert "timestamp" in msg


def test_send_message_with_ai_mention(client):
    """POST /message with @document-processor returns AI response."""
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()

    resp = client.post(
        "/api/v1/chat/message",
        json={"from": "Bob", "content": "@document-processor show me stats"},
    )
    assert resp.status_code == 200

    hist = client.get("/api/v1/chat/history").json()
    # Should have user message + AI response
    assert len(hist) >= 2

    # User message
    user_msg = hist[-2]
    assert user_msg["type"] == "message"
    assert user_msg["from"] == "Bob"

    # AI response
    ai_msg = hist[-1]
    assert ai_msg["type"] == "ai_response"
    assert "Document Processor" in ai_msg["from"]
    assert "Total documents" in ai_msg["content"] or "Error" in ai_msg["content"]


def test_send_message_with_unknown_mention(client):
    """POST /message with unknown @mention does not trigger AI response."""
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()

    resp = client.post(
        "/api/v1/chat/message",
        json={"from": "Carol", "content": "@unknown-staff hello"},
    )
    assert resp.status_code == 200

    hist = client.get("/api/v1/chat/history").json()
    # Only the user message, no AI response
    assert len(hist) == 1
    assert hist[0]["type"] == "message"


def test_send_message_with_mention_no_query(client):
    """@mention without a query after it does not trigger AI response."""
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()

    resp = client.post(
        "/api/v1/chat/message",
        json={"from": "Dave", "content": "@inventory-manager"},
    )
    assert resp.status_code == 200

    hist = client.get("/api/v1/chat/history").json()
    assert len(hist) == 1
    assert hist[0]["type"] == "message"


def test_chat_history_limit(client):
    """History endpoint respects limit parameter."""
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()

    # Send 5 messages
    for i in range(5):
        client.post(
            "/api/v1/chat/message",
            json={"from": "User", "content": f"Message {i}"},
        )

    # Request only last 2
    resp = client.get("/api/v1/chat/history?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["content"] == "Message 3"
    assert data[1]["content"] == "Message 4"


def test_list_staff(client):
    """Staff endpoint returns registered digital staff."""
    resp = client.get("/api/v1/chat/staff")
    assert resp.status_code == 200
    data = resp.json()
    assert "staff" in data
    staff_names = data["staff"]
    assert "Document Processor" in staff_names
    assert "Inventory Manager" in staff_names


def test_message_max_content_length(client):
    """Messages longer than 5000 chars are rejected by Pydantic validation."""
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()

    long_content = "A" * 6000
    resp = client.post(
        "/api/v1/chat/message",
        json={"from": "User", "content": long_content},
    )
    assert resp.status_code == 422


def test_history_max_100_messages(client):
    """Chat history trims to 100 messages max."""
    from lab_manager.api.routes import chat as chat_mod

    chat_mod._chat_history.clear()

    # Send 105 messages
    for i in range(105):
        client.post(
            "/api/v1/chat/message",
            json={"from": "User", "content": f"Msg {i}"},
        )

    hist = client.get("/api/v1/chat/history").json()
    assert len(hist) == 100


def test_parse_mention():
    """Unit test for @mention parsing."""
    from lab_manager.api.routes.chat import _parse_mention

    staff, query = _parse_mention("@inventory-manager how many antibodies?")
    assert staff == "inventory-manager"
    assert query == "how many antibodies?"

    staff, query = _parse_mention("just a regular message")
    assert staff is None
    assert query == "just a regular message"

    staff, query = _parse_mention("@Document-Processor stats")
    assert staff == "document-processor"
    assert query == "stats"

    staff, query = _parse_mention("  @inventory-manager  query  ")
    assert staff == "inventory-manager"
    assert query == "query"


def test_digital_staff_registry():
    """Unit test for staff registry."""
    from lab_manager.api.routes.chat import get_digital_staff_names

    names = get_digital_staff_names()
    assert "Document Processor" in names
    assert "Inventory Manager" in names
    assert len(names) >= 2
