"""Tests for consumption_forecast service — depletion prediction and reorder."""

from datetime import timedelta

from lab_manager.models.consumption import ConsumptionLog
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services.consumption_forecast import (
    get_reorder_recommendations,
    predict_batch,
    predict_depletion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_counter = 0


def _seed_vendor_and_product(db, min_stock=None, reorder_qty=None):
    """Create a vendor + product pair and return (vendor, product)."""
    global _counter
    _counter += 1
    tag = _counter
    v = Vendor(name=f"TestVendor-{tag}")
    db.add(v)
    db.commit()
    db.refresh(v)

    p = Product(
        catalog_number=f"FC-{tag:03d}",
        name=f"Test Reagent {tag}",
        vendor_id=v.id,
        min_stock_level=min_stock,
        reorder_quantity=reorder_qty,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return v, p


def _add_inventory(db, product_id, qty, status="available"):
    """Add an inventory item and return it."""
    item = InventoryItem(
        product_id=product_id,
        quantity_on_hand=qty,
        status=status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _add_consume_log(db, product_id, inventory_id, qty_used, days_ago):
    """Add a consume-action log entry N days ago."""
    from datetime import datetime, timezone

    entry = ConsumptionLog(
        inventory_id=inventory_id,
        product_id=product_id,
        quantity_used=qty_used,
        quantity_remaining=0,
        consumed_by="tester",
        action="consume",
    )
    entry.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    db.add(entry)
    db.commit()
    return entry


# ---------------------------------------------------------------------------
# predict_depletion tests
# ---------------------------------------------------------------------------


def test_predict_depletion_with_consumption_data(db_session):
    """Prediction should return daily_rate and days_until_empty."""
    _, p = _seed_vendor_and_product(db_session)
    inv = _add_inventory(db_session, p.id, qty=100)

    # 30 days of consumption, 2 units/day.
    for days_ago in range(1, 31):
        _add_consume_log(db_session, p.id, inv.id, qty_used=2.0, days_ago=days_ago)

    result = predict_depletion(p.id, db_session)

    assert result["product_id"] == p.id
    assert result["current_qty"] == 100.0
    assert result["daily_rate"] > 0
    assert result["days_until_empty"] is not None
    assert result["days_until_empty"] > 0
    assert result["predicted_empty_date"] is not None
    # 30 distinct days of data => high confidence.
    assert result["confidence"] == "high"


def test_predict_depletion_no_data(db_session):
    """No consumption logs should return no_data confidence."""
    _, p = _seed_vendor_and_product(db_session)
    _add_inventory(db_session, p.id, qty=50)

    result = predict_depletion(p.id, db_session)

    assert result["product_id"] == p.id
    assert result["current_qty"] == 50.0
    assert result["daily_rate"] == 0.0
    assert result["days_until_empty"] is None
    assert result["predicted_empty_date"] is None
    assert result["confidence"] == "no_data"


def test_predict_depletion_zero_consumption(db_session):
    """Consumption logs with zero total should return zero_consumption confidence."""
    _, p = _seed_vendor_and_product(db_session)
    inv = _add_inventory(db_session, p.id, qty=50)

    # Log exists but quantity_used is 0.
    _add_consume_log(db_session, p.id, inv.id, qty_used=0.0, days_ago=1)

    result = predict_depletion(p.id, db_session)

    assert result["confidence"] == "zero_consumption"
    assert result["days_until_empty"] is None


def test_predict_depletion_medium_confidence(db_session):
    """14-29 days of data should give medium confidence."""
    _, p = _seed_vendor_and_product(db_session)
    inv = _add_inventory(db_session, p.id, qty=100)

    for days_ago in range(1, 20):
        _add_consume_log(db_session, p.id, inv.id, qty_used=1.0, days_ago=days_ago)

    result = predict_depletion(p.id, db_session)
    assert result["confidence"] == "medium"


def test_predict_depletion_low_confidence(db_session):
    """Less than 14 days of data should give low confidence."""
    _, p = _seed_vendor_and_product(db_session)
    inv = _add_inventory(db_session, p.id, qty=100)

    for days_ago in range(1, 10):
        _add_consume_log(db_session, p.id, inv.id, qty_used=1.0, days_ago=days_ago)

    result = predict_depletion(p.id, db_session)
    assert result["confidence"] == "low"


def test_predict_depletion_single_day_data(db_session):
    """Single day of data should still produce a prediction (low confidence)."""
    _, p = _seed_vendor_and_product(db_session)
    inv = _add_inventory(db_session, p.id, qty=10)

    _add_consume_log(db_session, p.id, inv.id, qty_used=5.0, days_ago=1)

    result = predict_depletion(p.id, db_session)
    assert result["daily_rate"] == 5.0
    assert result["days_until_empty"] == 2.0
    assert result["confidence"] == "low"


def test_predict_depletion_no_inventory(db_session):
    """Product with zero inventory should predict 0 days_until_empty."""
    _, p = _seed_vendor_and_product(db_session)
    inv = _add_inventory(db_session, p.id, qty=0, status="depleted")

    _add_consume_log(db_session, p.id, inv.id, qty_used=1.0, days_ago=1)

    result = predict_depletion(p.id, db_session)
    assert result["current_qty"] == 0.0
    assert result["days_until_empty"] == 0.0


# ---------------------------------------------------------------------------
# predict_batch tests
# ---------------------------------------------------------------------------


def test_predict_batch_sorted_by_urgency(db_session):
    """Batch results should be sorted by days_until_empty ascending."""
    _, p1 = _seed_vendor_and_product(db_session)
    inv1 = _add_inventory(db_session, p1.id, qty=100)
    for d in range(1, 31):
        _add_consume_log(db_session, p1.id, inv1.id, qty_used=1.0, days_ago=d)

    _, p2 = _seed_vendor_and_product(db_session)
    # Different catalog number to avoid unique constraint.
    p2.catalog_number = "FC-002"
    db_session.commit()
    inv2 = _add_inventory(db_session, p2.id, qty=10)
    for d in range(1, 31):
        _add_consume_log(db_session, p2.id, inv2.id, qty_used=5.0, days_ago=d)

    results = predict_batch([p1.id, p2.id], db_session)

    assert len(results) == 2
    # p2 has higher daily rate (5 vs 1) and lower stock (10 vs 100).
    assert results[0]["product_id"] == p2.id
    assert results[1]["product_id"] == p1.id


def test_predict_batch_nulls_last(db_session):
    """Products with no data (null days_until_empty) should sort last."""
    _, p1 = _seed_vendor_and_product(db_session)
    inv1 = _add_inventory(db_session, p1.id, qty=100)
    for d in range(1, 31):
        _add_consume_log(db_session, p1.id, inv1.id, qty_used=1.0, days_ago=d)

    _, p_no_data = _seed_vendor_and_product(db_session)
    p_no_data.catalog_number = "FC-ND"
    db_session.commit()
    _add_inventory(db_session, p_no_data.id, qty=50)

    results = predict_batch([p_no_data.id, p1.id], db_session)

    assert results[0]["product_id"] == p1.id
    assert results[0]["days_until_empty"] is not None
    assert results[1]["product_id"] == p_no_data.id
    assert results[1]["days_until_empty"] is None


# ---------------------------------------------------------------------------
# get_reorder_recommendations tests
# ---------------------------------------------------------------------------


def test_reorder_below_min_stock(db_session):
    """Product below min_stock_level should appear in recommendations."""
    _, p = _seed_vendor_and_product(db_session, min_stock=10.0, reorder_qty=50.0)
    inv = _add_inventory(db_session, p.id, qty=3.0)

    for d in range(1, 31):
        _add_consume_log(db_session, p.id, inv.id, qty_used=1.0, days_ago=d)

    recs = get_reorder_recommendations(db_session)

    matching = [r for r in recs if r["product_id"] == p.id]
    assert len(matching) == 1
    assert matching[0]["reason"] == "below_min_stock"
    assert matching[0]["suggested_order_quantity"] == 50.0
    assert "Test Reagent" in matching[0]["product_name"]


def test_reorder_depleting_soon(db_session):
    """Product with stock above min but depleting within lead time should appear."""
    _, p = _seed_vendor_and_product(db_session, min_stock=5.0, reorder_qty=20.0)
    inv = _add_inventory(db_session, p.id, qty=8.0)

    # High consumption rate: 2 units/day => depletes in 4 days (< 7 day lead time).
    for d in range(1, 31):
        _add_consume_log(db_session, p.id, inv.id, qty_used=2.0, days_ago=d)

    recs = get_reorder_recommendations(db_session)

    matching = [r for r in recs if r["product_id"] == p.id]
    assert len(matching) == 1
    assert matching[0]["reason"] == "depleting_soon"


def test_reorder_healthy_product_not_listed(db_session):
    """Product with adequate stock should NOT appear in recommendations."""
    _, p = _seed_vendor_and_product(db_session, min_stock=5.0, reorder_qty=20.0)
    inv = _add_inventory(db_session, p.id, qty=1000.0)

    # Very low consumption rate.
    for d in range(1, 31):
        _add_consume_log(db_session, p.id, inv.id, qty_used=0.01, days_ago=d)

    recs = get_reorder_recommendations(db_session)

    matching = [r for r in recs if r["product_id"] == p.id]
    assert len(matching) == 0


def test_reorder_no_min_stock_not_listed(db_session):
    """Product without min_stock_level should never appear."""
    _, p = _seed_vendor_and_product(db_session, min_stock=None, reorder_qty=20.0)
    _add_inventory(db_session, p.id, qty=0.5)

    recs = get_reorder_recommendations(db_session)
    matching = [r for r in recs if r["product_id"] == p.id]
    assert len(matching) == 0


def test_reorder_empty_products(db_session):
    """No products with min_stock_level => empty list."""
    recs = get_reorder_recommendations(db_session)
    assert recs == []


# ---------------------------------------------------------------------------
# Reasoning service integration
# ---------------------------------------------------------------------------


def test_run_usage_chain_with_data(db_session):
    """_run_usage_chain should use real forecast when DB is available."""
    from lab_manager.services.reasoning import ReasoningService

    svc = ReasoningService()
    _, p = _seed_vendor_and_product(db_session, min_stock=10.0)
    inv = _add_inventory(db_session, p.id, qty=2.0)
    for d in range(1, 31):
        _add_consume_log(db_session, p.id, inv.id, qty_used=1.0, days_ago=d)

    steps, summary, recommendation, confidence = svc._run_usage_chain(
        "usage patterns", db_session
    )

    assert len(steps) == 3
    assert "reorder" in summary.lower() or "stock" in summary.lower()
    assert confidence > 0.0


def test_run_usage_chain_no_db(db_session):
    """_run_usage_chain should handle None DB gracefully."""
    from lab_manager.services.reasoning import ReasoningService

    svc = ReasoningService()
    steps, summary, recommendation, confidence = svc._run_usage_chain(
        "usage patterns", None
    )

    assert len(steps) == 3
    assert confidence == 0.0
    assert "no DB" in summary
