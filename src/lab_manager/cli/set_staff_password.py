#!/usr/bin/env python3
"""Set or update a staff member's password.

Usage:
    uv run python scripts/set_staff_password.py <email> <password>
    uv run python scripts/set_staff_password.py admin@example.com mysecretpassword
"""

from __future__ import annotations

import getpass
import sys

import bcrypt


def main() -> None:
    if len(sys.argv) == 3:
        email, password = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        email = sys.argv[1]
        password = getpass.getpass("Password: ")
    else:
        print(f"Usage: {sys.argv[0]} <email> [password]", file=sys.stderr)
        sys.exit(1)

    if len(password) < 8:
        print("Error: password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    from lab_manager.database import get_db_session
    from lab_manager.models.staff import Staff

    with get_db_session() as db:
        staff = db.query(Staff).filter(Staff.email == email).first()
        if not staff:
            print(f"Error: no staff found with email '{email}'", file=sys.stderr)
            sys.exit(1)

        staff.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        db.commit()
        print(f"Password set for {staff.name} ({email})")


if __name__ == "__main__":
    main()
