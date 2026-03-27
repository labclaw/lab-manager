"""Test proactive feed API endpoint."""

from datetime import date, timedelta

from lab_manager.models.alert import Alert
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor


def _seed_vendor(db):
    v = Vendor(name="FeedTestVendor")
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


REQUIRED_FIELDS = {
    "id",
    "type",
    "priority",
    "title",
    "description",
    "timestamp",
    "action_url",
    "is_read",
}


def test_feed_returns_list(client):
    """GET /api/v1/feed returns a valid response with items list."""
    r = client.get("/api/v1/feed/")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] == len(data["items"])


def test_feed_items_have_required_fields(client, db_session):
    """Every feed item must have all required fields."""
    v = _seed_vendor(db_session)
    p = Product(catalog_number="FT1", name="FeedTest Product", vendor_id=v.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    item = InventoryItem(
        product_id=p.id,
        quantity_on_hand=5,
        expiry_date=date.today() - timedelta(days=1),
        status="available",
    )
    db_session.add(item)
    db_session.commit()

    alert = Alert(
        alert_type="expired",
        severity="critical",
        message=f"Inventory item {item.id} expired",
        entity_type="inventory",
        entity_id=item.id,
    )
    db_session.add(alert)
    db_session.commit()

    r = client.get("/api/v1/feed/")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    for feed_item in data["items"]:
        missing = REQUIRED_FIELDS - set(feed_item.keys())
        assert not missing, f"Feed item missing fields: {missing}"


def test_feed_includes_alerts(client, db_session):
    """Feed should include items from the alerts table."""
    v = _seed_vendor(db_session)
    p = Product(catalog_number="FT2", name="FeedTest Low Stock", vendor_id=v.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    alert = Alert(
        alert_type="low_stock",
        severity="warning",
        message="Product is low on stock",
        entity_type="product",
        entity_id=p.id,
    )
    db_session.add(alert)
    db_session.commit()

    r = client.get("/api/v1/feed/")
    data = r.json()
    alert_items = [i for i in data["items"] if i["type"] == "alert"]
    assert len(alert_items) >= 1
    assert alert_items[0]["priority"] in ("high", "medium", "low")


def test_feed_filter_by_type(client, db_session):
    """Filtering by type returns only matching items."""
    v = _seed_vendor(db_session)
    p = Product(catalog_number="FT3", name="FeedTest Filter", vendor_id=v.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    alert = Alert(
        alert_type="expiring_soon",
        severity="warning",
        message="Item expiring soon",
        entity_type="inventory",
        entity_id=p.id,
    )
    db_session.add(alert)
    db_session.commit()

    r = client.get("/api/v1/feed/", params={"item_type": "alert"})
    assert r.status_code == 200
    data = r.json()
    for item in data["items"]:
        assert item["type"] == "alert"


def test_feed_filter_by_priority(client):
    """Filtering by priority returns only matching items."""
    r = client.get("/api/v1/feed/", params={"priority": "high"})
    assert r.status_code == 200
    data = r.json()
    for item in data["items"]:
        assert item["priority"] == "high"


def test_mark_feed_item_read(client, db_session):
    """POST /api/v1/feed/{id}/read marks alert as acknowledged."""
    v = _seed_vendor(db_session)
    p = Product(catalog_number="FT4", name="FeedTest Read", vendor_id=v.id)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    alert = Alert(
        alert_type="low_stock",
        severity="warning",
        message="Low stock product",
        entity_type="product",
        entity_id=p.id,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    r = client.post(f"/api/v1/feed/alert-{alert.id}/read")
    assert r.status_code == 200

    db_session.refresh(alert)
    assert alert.is_acknowledged is True


def test_feed_includes_suggestions(client, db_session):
    """Feed should include AI-suggested actions based on alert conditions."""
    v = _seed_vendor(db_session)
    p = Product(
        catalog_number="FT5",
        name="FeedTest Suggestion",
        vendor_id=v.id,
        min_stock_level=10,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    item = InventoryItem(
        product_id=p.id,
        quantity_on_hand=0,
        status="available",
    )
    db_session.add(item)
    db_session.commit()

    r = client.get("/api/v1/feed/")
    data = r.json()
    suggestions = [i for i in data["items"] if i["type"] == "suggestion"]
    assert len(suggestions) >= 1
    assert suggestions[0]["title"]  # has a title
    assert suggestions[0]["action_url"]  # has a navigation link


def test_feed_priority_values(client):
    """All feed items have valid priority values."""
    r = client.get("/api/v1/feed/")
    assert r.status_code == 200
    data = r.json()
    valid_priorities = {"high", "medium", "low"}
    for item in data["items"]:
        assert item["priority"] in valid_priorities
