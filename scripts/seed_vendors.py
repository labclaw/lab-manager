#!/usr/bin/env python3
"""Seed the database with known vendors from our scan data."""

from sqlalchemy.orm import Session

from lab_manager.database import get_engine
from lab_manager.models.vendor import Vendor

VENDORS = [
    {
        "name": "EMD Millipore Corporation",
        "aliases": ["MilliporeSigma", "Merck", "Sigma-Aldrich"],
    },
    {"name": "Sigma-Aldrich", "aliases": ["Merck"]},
    {"name": "Targetmol Chemicals Inc.", "aliases": ["TargetMol"]},
    {"name": "Biohippo Inc.", "aliases": ["biohippo"]},
    {
        "name": "Thermo Fisher Scientific",
        "aliases": ["Invitrogen", "Life Technologies", "Pierce"],
    },
    {"name": "BioLegend Inc", "aliases": ["BioLegend"]},
    {"name": "VWR International", "aliases": ["Avantor", "VWR"]},
    {"name": "Genesee Scientific", "aliases": []},
    {"name": "ALSTEM Inc.", "aliases": ["ALSTEM"]},
    {"name": "Westnet Inc.", "aliases": ["Westnet"]},
    {"name": "Staples Inc.", "aliases": ["Staples"]},
]


def main():
    engine = get_engine()
    with Session(engine) as db:
        for v in VENDORS:
            existing = db.query(Vendor).filter(Vendor.name == v["name"]).first()
            if not existing:
                db.add(Vendor(name=v["name"], aliases=v["aliases"]))
                print(f"  Added: {v['name']}")
            else:
                print(f"  Exists: {v['name']}")
        db.commit()
    print("Done.")


if __name__ == "__main__":
    main()
