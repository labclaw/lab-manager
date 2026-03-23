#!/usr/bin/env python3
"""Populate empty database tables (products, staff, locations, inventory)
from existing order_items, orders, and documents data.

Idempotent: checks for existing rows before inserting.
Usage: uv run python scripts/populate_db.py
"""

from __future__ import annotations

import logging
import sys
from collections import Counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from lab_manager.database import get_engine
from lab_manager.models.product import Product
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.staff import Staff
from lab_manager.models.location import StorageLocation
from lab_manager.models.order import Order, OrderItem

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Products — deduplicate from order_items
# ---------------------------------------------------------------------------


def populate_products(db: Session) -> dict[str, int]:
    """Create products from distinct catalog_numbers in order_items.

    Returns mapping of catalog_number -> product.id.
    """
    log.info("=== Populating products ===")

    existing = db.query(Product).all()
    existing_map: dict[str, int] = {p.catalog_number: p.id for p in existing}
    if existing_map:
        log.info("Found %d existing products, will skip duplicates", len(existing_map))

    # Fetch all order_items with their order's vendor_id
    rows = (
        db.query(
            OrderItem.catalog_number,
            OrderItem.description,
            OrderItem.unit,
            Order.vendor_id,
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(OrderItem.catalog_number.isnot(None))
        .filter(OrderItem.catalog_number != "")
        .all()
    )

    # Group by catalog_number
    groups: dict[str, list] = {}
    for cat_num, desc, unit, vendor_id in rows:
        groups.setdefault(cat_num, []).append((desc, unit, vendor_id))

    created = 0
    skipped = 0
    catalog_map: dict[str, int] = dict(existing_map)

    for cat_num, entries in sorted(groups.items()):
        if cat_num in catalog_map:
            skipped += 1
            continue

        # Most common description
        descriptions = [e[0] for e in entries if e[0]]
        desc_counts = Counter(descriptions).most_common(1)
        name = desc_counts[0][0] if desc_counts else cat_num

        # Most common unit
        units = [e[1] for e in entries if e[1]]
        unit_counts = Counter(units).most_common(1)
        unit = unit_counts[0][0] if unit_counts else None

        # Most common vendor_id
        vendor_ids = [e[2] for e in entries if e[2] is not None]
        vid_counts = Counter(vendor_ids).most_common(1)
        vendor_id = vid_counts[0][0] if vid_counts else None

        product = Product(
            catalog_number=cat_num,
            name=name,
            vendor_id=vendor_id,
            unit=unit,
            created_by="populate_db",
        )
        db.add(product)
        db.flush()  # get id
        catalog_map[cat_num] = product.id
        created += 1

    db.commit()
    log.info("Products: %d created, %d skipped (already existed)", created, skipped)
    return catalog_map


# ---------------------------------------------------------------------------
# 2. Staff — extract unique names from orders.received_by + documents extracted_data
# ---------------------------------------------------------------------------


def populate_staff(db: Session) -> int:
    """Create staff records from unique received_by names."""
    log.info("=== Populating staff ===")

    existing_names = {s.name.lower() for s in db.query(Staff).all()}
    if existing_names:
        log.info("Found %d existing staff, will skip duplicates", len(existing_names))

    names: set[str] = set()

    # From orders.received_by
    order_names = (
        db.query(Order.received_by)
        .filter(Order.received_by.isnot(None))
        .filter(Order.received_by != "")
        .distinct()
        .all()
    )
    for (name,) in order_names:
        names.add(name.strip())

    # From documents.extracted_data -> received_by
    doc_rows = db.execute(
        text(
            "SELECT DISTINCT extracted_data->>'received_by' "
            "FROM documents "
            "WHERE extracted_data->>'received_by' IS NOT NULL "
            "AND extracted_data->>'received_by' <> '' "
            "AND extracted_data->>'received_by' <> 'null'"
        )
    ).all()
    for (name,) in doc_rows:
        if name and name.strip():
            names.add(name.strip())

    # Normalize: title-case, deduplicate case-insensitively
    normalized: dict[str, str] = {}
    for name in names:
        key = name.lower().strip()
        if key and key not in normalized:
            # Prefer title-cased version
            normalized[key] = name.title() if name.isupper() or name.islower() else name

    created = 0
    for key, display_name in sorted(normalized.items()):
        if key in existing_names:
            continue
        staff = Staff(
            name=display_name,
            role="member",
            is_active=True,
            created_by="populate_db",
        )
        db.add(staff)
        created += 1

    db.commit()
    log.info("Staff: %d created", created)
    return created


# ---------------------------------------------------------------------------
# 3. Locations — seed common lab storage locations
# ---------------------------------------------------------------------------

LOCATIONS = [
    {
        "name": "-80\u00b0C Freezer",
        "room": "Room 123",
        "building": "CNY 149",
        "temperature": -80,
        "description": "Ultra-low temperature storage for long-term samples and reagents",
    },
    {
        "name": "-20\u00b0C Freezer",
        "room": "Room 123",
        "building": "CNY 149",
        "temperature": -20,
        "description": "Standard freezer for enzymes, antibodies, and kits",
    },
    {
        "name": "4\u00b0C Refrigerator",
        "room": "Room 123",
        "building": "CNY 149",
        "temperature": 4,
        "description": "Cold storage for buffers, media, and temperature-sensitive reagents",
    },
    {
        "name": "Room Temperature Shelf",
        "room": "Room 123",
        "building": "CNY 149",
        "temperature": 22,
        "description": "Ambient storage for stable chemicals and consumables",
    },
    {
        "name": "Chemical Storage Cabinet",
        "room": "Room 123",
        "building": "CNY 149",
        "temperature": 22,
        "description": "Ventilated cabinet for hazardous chemicals and solvents",
    },
    {
        "name": "Tissue Culture Hood",
        "room": "Room 124",
        "building": "CNY 149",
        "temperature": 22,
        "description": "Sterile workspace for cell culture and tissue processing",
    },
    {
        "name": "Bench Area",
        "room": "Room 124",
        "building": "CNY 149",
        "temperature": 22,
        "description": "General lab bench for experiments and sample preparation",
    },
]


def populate_locations(db: Session) -> dict[str, int]:
    """Seed storage locations. Returns name -> id mapping."""
    log.info("=== Populating locations ===")

    existing = {loc.name: loc.id for loc in db.query(StorageLocation).all()}
    if existing:
        log.info("Found %d existing locations, will skip duplicates", len(existing))

    created = 0
    loc_map = dict(existing)

    for loc_data in LOCATIONS:
        if loc_data["name"] in loc_map:
            continue
        loc = StorageLocation(
            name=loc_data["name"],
            room=loc_data["room"],
            building=loc_data["building"],
            temperature=loc_data["temperature"],
            description=loc_data["description"],
            created_by="populate_db",
        )
        db.add(loc)
        db.flush()
        loc_map[loc.name] = loc.id
        created += 1

    db.commit()
    log.info("Locations: %d created", created)
    return loc_map


# ---------------------------------------------------------------------------
# 4. Inventory — from received order_items
# ---------------------------------------------------------------------------


def populate_inventory(
    db: Session, catalog_map: dict[str, int], loc_map: dict[str, int]
) -> int:
    """Create inventory records from order_items of received orders."""
    log.info("=== Populating inventory ===")

    # Check existing inventory by order_item_id to avoid duplicates
    existing_oi_ids = {
        row[0]
        for row in db.query(InventoryItem.order_item_id)
        .filter(InventoryItem.order_item_id.isnot(None))
        .all()
    }
    if existing_oi_ids:
        log.info(
            "Found %d existing inventory records, will skip duplicates",
            len(existing_oi_ids),
        )

    # Default location: Room Temperature Shelf
    default_location_id = loc_map.get("Room Temperature Shelf")

    # Fetch order_items from received orders
    items = (
        db.query(OrderItem, Order.received_by)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.status == "received")
        .all()
    )

    created = 0
    for oi, received_by in items:
        if oi.id in existing_oi_ids:
            continue

        product_id = catalog_map.get(oi.catalog_number) if oi.catalog_number else None

        inv = InventoryItem(
            product_id=product_id,
            location_id=default_location_id,
            lot_number=oi.lot_number,
            quantity_on_hand=oi.quantity,
            unit=oi.unit,
            status="available",
            received_by=received_by,
            order_item_id=oi.id,
            created_by="populate_db",
        )
        db.add(inv)
        created += 1

    db.commit()
    log.info("Inventory: %d created", created)
    return created


# ---------------------------------------------------------------------------
# 5. Update order_items.product_id
# ---------------------------------------------------------------------------


def update_order_items_product_id(db: Session, catalog_map: dict[str, int]) -> int:
    """Set product_id on order_items based on catalog_number."""
    log.info("=== Updating order_items.product_id ===")

    items = (
        db.query(OrderItem)
        .filter(OrderItem.product_id.is_(None))
        .filter(OrderItem.catalog_number.isnot(None))
        .filter(OrderItem.catalog_number != "")
        .all()
    )

    updated = 0
    for oi in items:
        pid = catalog_map.get(oi.catalog_number)
        if pid:
            oi.product_id = pid
            updated += 1

    db.commit()
    log.info("OrderItems: %d updated with product_id", updated)
    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    log.info("Starting database population script")
    engine = get_engine()

    with Session(engine) as db:
        # 1. Products
        catalog_map = populate_products(db)

        # 2. Staff
        populate_staff(db)

        # 3. Locations
        loc_map = populate_locations(db)

        # 4. Inventory
        populate_inventory(db, catalog_map, loc_map)

        # 5. Update order_items
        update_order_items_product_id(db, catalog_map)

    # Summary
    log.info("=== Final Summary ===")
    with Session(engine) as db:
        tables = [
            "vendors",
            "orders",
            "order_items",
            "products",
            "inventory",
            "staff",
            "locations",
        ]
        for table in tables:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            log.info("  %-15s %d rows", table, count)

    log.info("Done.")


if __name__ == "__main__":
    main()
