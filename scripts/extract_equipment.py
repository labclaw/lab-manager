#!/usr/bin/env python3
"""Extract lab equipment info from device photos using VLM.

Usage:
    uv run python scripts/extract_equipment.py [--dry-run] [--photo-dir shenlab-devices/]

Workflow:
    1. Scan photo directory for device images
    2. Send each to Gemini VLM for structured extraction
    3. Group photos that belong to the same device
    4. Insert/update equipment records in DB with full traceability

Traceability: every equipment record stores in extracted_data:
    - source_model: which VLM model was used
    - extraction_timestamp: when extraction happened
    - source_photos: list of photo paths that were analyzed
    - raw_response: the raw VLM response
    - confidence: extraction confidence score
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# VLM model for extraction (API-available)
EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "gemini-2.5-flash")

EXTRACTION_PROMPT = """Analyze this lab equipment photo. Extract structured information about the device.

Return a JSON object with these fields (use null for unknown):
{
  "name": "Full device name (e.g., 'Eppendorf 5702R Centrifuge')",
  "manufacturer": "Manufacturer name",
  "model": "Model number/name",
  "serial_number": "Serial number if visible",
  "system_id": "Asset tag or system ID if visible",
  "category": "One of: microscope, centrifuge, pcr, imaging, freezer, ultrasound, laser, two-photon, electrophoresis, surgery, printer, fax, pipette, incubator, other",
  "description": "Brief description of what you see",
  "room": "Room number if visible",
  "estimated_value_usd": null,
  "is_api_controllable": false,
  "confidence": 0.0 to 1.0
}

Be precise. Only include information you can actually see in the image. Do not guess serial numbers or model numbers if not clearly visible."""


def extract_from_photo(photo_path: Path) -> dict | None:
    """Send a photo to Gemini VLM and extract equipment info."""
    try:
        import google.generativeai as genai
    except ImportError:
        log.error(
            "google-generativeai not installed. Run: uv pip install google-generativeai"
        )
        return None

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        log.error("No GEMINI_API_KEY or GOOGLE_API_KEY found")
        return None

    genai.configure(api_key=api_key)

    # Read and encode image
    image_data = photo_path.read_bytes()
    image_b64 = base64.b64encode(image_data).decode()

    model = genai.GenerativeModel(EXTRACTION_MODEL)
    response = model.generate_content(
        [
            {"mime_type": "image/jpeg", "data": image_b64},
            EXTRACTION_PROMPT,
        ],
        generation_config={"response_mime_type": "application/json"},
    )

    try:
        result = json.loads(response.text)
        # Handle case where VLM returns a list (e.g., multiple devices in one photo)
        if isinstance(result, list):
            if len(result) == 1:
                result = result[0]
            elif len(result) > 1:
                # Return first item but note there are multiple
                log.info("  VLM found %d devices in photo, using first", len(result))
                result = result[0]
            else:
                return None
        return result
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("Failed to parse VLM response for %s: %s", photo_path.name, e)
        log.debug("Raw response: %s", response.text)
        return None


def group_photos_by_device(extractions: list[dict]) -> list[dict]:
    """Group photos that likely belong to the same device based on extracted info."""
    devices = []
    seen = set()

    for ext in extractions:
        data = ext["data"]
        if not data:
            continue

        # Create a grouping key from name + manufacturer + model
        key = (
            (data.get("name") or "").lower().strip(),
            (data.get("manufacturer") or "").lower().strip(),
        )

        if key in seen and key != ("", ""):
            # Merge photo into existing device
            for dev in devices:
                dev_key = (
                    (dev["data"].get("name") or "").lower().strip(),
                    (dev["data"].get("manufacturer") or "").lower().strip(),
                )
                if dev_key == key:
                    dev["photos"].append(ext["photo"])
                    # Merge any new data (prefer higher confidence)
                    if (data.get("confidence") or 0) > (
                        dev["data"].get("confidence") or 0
                    ):
                        for field in ["serial_number", "system_id", "model", "room"]:
                            if data.get(field) and not dev["data"].get(field):
                                dev["data"][field] = data[field]
                    break
        else:
            seen.add(key)
            devices.append(
                {
                    "photos": [ext["photo"]],
                    "data": data,
                }
            )

    return devices


def insert_equipment(devices: list[dict], dry_run: bool = False):
    """Insert equipment records into the database."""
    if dry_run:
        log.info("=== DRY RUN — would insert %d equipment records ===", len(devices))
        for i, dev in enumerate(devices, 1):
            data = dev["data"]
            log.info(
                "  [%d] %s | %s | %s | photos: %s",
                i,
                data.get("name", "?"),
                data.get("manufacturer", "?"),
                data.get("category", "?"),
                [p.name for p in dev["photos"]],
            )
        return

    # Import DB dependencies
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager",
    )

    from sqlalchemy.orm import Session
    from sqlmodel import create_engine

    from lab_manager.models.equipment import Equipment

    engine = create_engine(os.environ["DATABASE_URL"])
    timestamp = datetime.now(timezone.utc).isoformat()

    with Session(engine) as session:
        for dev in devices:
            data = dev["data"]
            photo_paths = [f"/shenlab-devices/{p.name}" for p in dev["photos"]]

            equip = Equipment(
                name=data.get("name") or "Unknown Device",
                manufacturer=data.get("manufacturer"),
                model=data.get("model"),
                serial_number=data.get("serial_number"),
                system_id=data.get("system_id"),
                category=data.get("category", "other"),
                description=data.get("description"),
                room=data.get("room"),
                photos=photo_paths,
                extracted_data={
                    "source_model": EXTRACTION_MODEL,
                    "extraction_timestamp": timestamp,
                    "source_photos": photo_paths,
                    "raw_fields": data,
                    "confidence": data.get("confidence", 0),
                },
            )
            session.add(equip)
            log.info(
                "Inserted: %s (%s) — %d photos",
                equip.name,
                equip.manufacturer,
                len(photo_paths),
            )

        session.commit()
        log.info("Committed %d equipment records to database", len(devices))


def main():
    parser = argparse.ArgumentParser(
        description="Extract equipment from device photos using VLM"
    )
    parser.add_argument(
        "--photo-dir", default="shenlab-devices/", help="Directory with device photos"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing to DB",
    )
    parser.add_argument(
        "--output", default=None, help="Save raw extractions to JSON file"
    )
    args = parser.parse_args()

    photo_dir = Path(args.photo_dir)
    if not photo_dir.exists():
        log.error("Photo directory not found: %s", photo_dir)
        sys.exit(1)

    photos = sorted(photo_dir.glob("*.jpg"))
    if not photos:
        log.error("No .jpg files found in %s", photo_dir)
        sys.exit(1)

    log.info("Found %d photos in %s", len(photos), photo_dir)

    # Extract from each photo
    extractions = []
    for i, photo in enumerate(photos, 1):
        log.info("[%d/%d] Extracting from %s ...", i, len(photos), photo.name)
        data = extract_from_photo(photo)
        extractions.append({"photo": photo, "data": data})
        if data:
            log.info(
                "  → %s | %s | %s (confidence: %.2f)",
                data.get("name", "?"),
                data.get("manufacturer", "?"),
                data.get("category", "?"),
                data.get("confidence", 0),
            )
        else:
            log.warning("  → extraction failed")

    # Save raw extractions if requested
    if args.output:
        output_data = []
        for ext in extractions:
            output_data.append(
                {
                    "photo": ext["photo"].name,
                    "data": ext["data"],
                }
            )
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        log.info("Saved raw extractions to %s", args.output)

    # Group and insert
    devices = group_photos_by_device(extractions)
    log.info("Grouped into %d unique devices", len(devices))

    insert_equipment(devices, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
