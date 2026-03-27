"""Seed script for default AI staff members.

Usage:
    uv run python scripts/seed_digital_staff.py
"""

import sys
from pathlib import Path

# Ensure src is on path when running from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlmodel import Session, select

from lab_manager.config import get_settings
from lab_manager.models.staff import Staff


DIGITAL_STAFF = [
    {
        "name": "Lab Assistant",
        "email": "lab-assistant@labclaw.local",
        "role": "ai_agent",
        "role_level": 1,
        "staff_type": "ai_agent",
        "avatar_emoji": "\U0001f916",
        "agent_config": {
            "role": "lab_assistant",
            "capabilities": ["inventory", "documents", "search"],
        },
    },
    {
        "name": "Safety Officer",
        "email": "safety-officer@labclaw.local",
        "role": "ai_agent",
        "role_level": 1,
        "staff_type": "ai_agent",
        "avatar_emoji": "\U0001f52c",
        "agent_config": {
            "role": "safety_officer",
            "capabilities": ["safety", "compliance", "msds"],
        },
    },
]


def seed() -> None:
    from sqlalchemy import create_engine

    settings = get_settings()
    engine = create_engine(settings.database_url)

    with Session(engine) as session:
        for data in DIGITAL_STAFF:
            existing = session.exec(
                select(Staff).where(Staff.email == data["email"])
            ).first()
            if existing:
                print(f"  [skip] {data['name']} ({data['email']}) already exists")
                continue
            staff = Staff(**data)
            session.add(staff)
            print(f"  [add]  {data['name']} ({data['email']})")
        session.commit()


if __name__ == "__main__":
    print("Seeding digital staff members ...")
    seed()
    print("Done.")
