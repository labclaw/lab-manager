"""Barcode and QR code generation endpoints."""

from __future__ import annotations

import hashlib
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.location import StorageLocation
from lab_manager.models.product import Product

router = APIRouter()


def _generate_qr_png(data: str, box_size: int = 10) -> bytes:
    """Generate a QR code as PNG bytes."""
    import qrcode

    qr = qrcode.QRCode(version=1, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _generate_barcode_png(data: str) -> bytes:
    """Generate a Code128 barcode as PNG bytes."""
    import barcode
    from barcode.writer import ImageWriter

    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    bc = code128(data, writer=writer)
    buf = io.BytesIO()
    bc.write(buf, options={"module_width": 0.3, "module_height": 10, "quiet_zone": 2})
    buf.seek(0)
    return buf.getvalue()


def _inventory_label(item: InventoryItem) -> str:
    """Build a compact label string for an inventory item."""
    parts = [f"INV-{item.id}"]
    if item.lot_number:
        parts.append(f"LOT:{item.lot_number}")
    if item.product:
        parts.append(item.product.name[:40])
    return "|".join(parts)


def _location_label(loc: StorageLocation) -> str:
    """Build a compact label string for a location."""
    parts = [f"LOC-{loc.id}", loc.name]
    return "|".join(parts)


# ── Inventory barcodes ──────────────────────────────────────────────


@router.get("/inventory/{item_id}/qr")
def inventory_qr(
    item_id: int,
    db: Session = Depends(get_db),
    size: int = Query(10, ge=4, le=30),
):
    """Generate a QR code for an inventory item."""
    item = get_or_404(db, InventoryItem, item_id, "InventoryItem")
    data = _inventory_label(item)
    png = _generate_qr_png(data, box_size=size)
    etag = hashlib.md5(data.encode()).hexdigest()
    return Response(
        content=png,
        media_type="image/png",
        headers={"ETag": etag, "Cache-Control": "max-age=3600"},
    )


@router.get("/inventory/{item_id}/barcode")
def inventory_barcode(
    item_id: int,
    db: Session = Depends(get_db),
):
    """Generate a Code128 barcode for an inventory item."""
    item = get_or_404(db, InventoryItem, item_id, "InventoryItem")
    data = f"INV-{item.id}"
    if item.lot_number:
        data += f"-{item.lot_number[:20]}"
    png = _generate_barcode_png(data)
    etag = hashlib.md5(data.encode()).hexdigest()
    return Response(
        content=png,
        media_type="image/png",
        headers={"ETag": etag, "Cache-Control": "max-age=3600"},
    )


# ── Location barcodes ───────────────────────────────────────────────


@router.get("/location/{location_id}/qr")
def location_qr(
    location_id: int,
    db: Session = Depends(get_db),
    size: int = Query(10, ge=4, le=30),
):
    """Generate a QR code for a storage location."""
    loc = get_or_404(db, StorageLocation, location_id, "StorageLocation")
    data = _location_label(loc)
    png = _generate_qr_png(data, box_size=size)
    return Response(content=png, media_type="image/png")


@router.get("/location/{location_id}/barcode")
def location_barcode(
    location_id: int,
    db: Session = Depends(get_db),
):
    """Generate a Code128 barcode for a storage location."""
    loc = get_or_404(db, StorageLocation, location_id, "StorageLocation")
    data = f"LOC-{loc.id}"
    png = _generate_barcode_png(data)
    return Response(content=png, media_type="image/png")


# ── Product barcodes ────────────────────────────────────────────────


@router.get("/product/{product_id}/qr")
def product_qr(
    product_id: int,
    db: Session = Depends(get_db),
    size: int = Query(10, ge=4, le=30),
):
    """Generate a QR code for a product."""
    prod = get_or_404(db, Product, product_id, "Product")
    data = f"PROD-{prod.id}|{prod.catalog_number}|{prod.name[:40]}"
    png = _generate_qr_png(data, box_size=size)
    return Response(content=png, media_type="image/png")


# ── Bulk label generation ───────────────────────────────────────────


@router.post("/bulk-qr")
def bulk_qr(
    body: dict,
    db: Session = Depends(get_db),
):
    """Generate QR codes for multiple items. Returns a list of base64-encoded PNGs.

    Body: {"inventory_ids": [1,2,3]} or {"location_ids": [1,2]}
    """
    import base64

    results = []

    for inv_id in body.get("inventory_ids", []):
        item = db.get(InventoryItem, inv_id)
        if item:
            data = _inventory_label(item)
            png = _generate_qr_png(data, box_size=8)
            results.append(
                {
                    "type": "inventory",
                    "id": inv_id,
                    "label": data,
                    "qr_base64": base64.b64encode(png).decode(),
                }
            )

    for loc_id in body.get("location_ids", []):
        loc = db.get(StorageLocation, loc_id)
        if loc:
            data = _location_label(loc)
            png = _generate_qr_png(data, box_size=8)
            results.append(
                {
                    "type": "location",
                    "id": loc_id,
                    "label": data,
                    "qr_base64": base64.b64encode(png).decode(),
                }
            )

    return {"items": results, "total": len(results)}
