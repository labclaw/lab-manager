"""Round 2: Fix remaining staff duplicates that need punctuation-aware matching.

Handles:
- "Shen, Shiqian" / "Shiqian Shen" (comma-separated Last, First)
- "Wang Pei!" (trailing punctuation)
- "Pei W" / "Pei Wang" (truncated name)
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from lab_manager.config import Settings


def main() -> None:
    s = Settings()
    engine = create_engine(s.database_url)

    # Manual merge map for remaining duplicates
    # Format: { variant: canonical }
    manual_renames = {
        # "Shen, Shiqian" is "Last, First" format -> "Shiqian Shen"
        "Shen, Shiqian": "Shiqian Shen",
        # "Wang Pei!" has trailing punctuation -> already merged to "Pei Wang"
        "Wang Pei!": "Pei Wang",
        # "Pei W" is truncated "Pei Wang"
        "Pei W": "Pei Wang",
        # "Pei wang" already handled in round 1, but check "Pei Wang" in orders
        # came from step 2: 'Pei Wang' count=11 was NOT IN STAFF before round 1
    }

    # Staff records to delete (merge into canonical)
    # id=12 "Shen, Shiqian" -> merge into id=13 "Shiqian Shen"
    # id=16 "Wang Pei!" -> merge into id=9 "Pei Wang"

    with engine.connect() as conn:
        print("=" * 70)
        print("BEFORE: Current staff with potential remaining duplicates")
        print("=" * 70)

        staff = conn.execute(
            text("""
            SELECT s.id, s.name,
                   (SELECT COUNT(*) FROM orders o WHERE o.received_by = s.name) as order_count
            FROM staff s
            WHERE s.name IN ('Shen, Shiqian', 'Shiqian Shen', 'Wang Pei!', 'Pei Wang', 'Pei W')
            ORDER BY s.name
        """)
        ).fetchall()

        for row in staff:
            print(f"  id={row[0]:>3}  name={row[1]!r:<25}  orders={row[2]}")

        # Check orders for these variants
        print()
        print("Orders with these variants:")
        for name in manual_renames:
            cnt = conn.execute(text("SELECT COUNT(*) FROM orders WHERE received_by = :n"), {"n": name}).scalar()
            inv_cnt = conn.execute(
                text("SELECT COUNT(*) FROM inventory WHERE received_by = :n"),
                {"n": name},
            ).scalar()
            print(f"  {name!r}: orders={cnt}, inventory={inv_cnt}")

        # ── Apply renames ──
        print()
        print("=" * 70)
        print("Applying renames")
        print("=" * 70)

        _SAFE_TABLES_COLS = {
            ("orders", "received_by"),
            ("inventory", "received_by"),
            ("consumption_log", "consumed_by"),
            ("audit_log", "changed_by"),
        }
        tables_cols = list(_SAFE_TABLES_COLS)

        for old_name, new_name in manual_renames.items():
            for tbl, col in tables_cols:
                assert (tbl, col) in _SAFE_TABLES_COLS, f"unexpected table/col: {tbl}.{col}"
                result = conn.execute(
                    text(f"UPDATE {tbl} SET {col} = :new WHERE {col} = :old"),
                    {"new": new_name, "old": old_name},
                )
                if result.rowcount > 0:
                    print(f"  {tbl}.{col}: {old_name!r} -> {new_name!r}  ({result.rowcount} rows)")

        # ── Merge staff records ──
        print()
        print("=" * 70)
        print("Merging staff records")
        print("=" * 70)

        # Delete "Shen, Shiqian" (id=12), keep "Shiqian Shen" (id=13)
        r = conn.execute(text("SELECT id FROM staff WHERE name = 'Shen, Shiqian'")).fetchone()
        if r:
            print(f"  Deleting staff id={r[0]} 'Shen, Shiqian' (keeping 'Shiqian Shen')")
            conn.execute(text("DELETE FROM staff WHERE id = :sid"), {"sid": r[0]})

        # Delete "Wang Pei!" (id=16), keep "Pei Wang" (id=9)
        r = conn.execute(text("SELECT id FROM staff WHERE name = 'Wang Pei!'")).fetchone()
        if r:
            print(f"  Deleting staff id={r[0]} 'Wang Pei!' (keeping 'Pei Wang')")
            conn.execute(text("DELETE FROM staff WHERE id = :sid"), {"sid": r[0]})

        # "Pei W" is only in orders/inventory, not in staff table, already handled above

        conn.commit()

        # ── After summary ──
        print()
        print("=" * 70)
        print("AFTER: Full staff table")
        print("=" * 70)

        staff_after = conn.execute(
            text("""
            SELECT s.id, s.name,
                   (SELECT COUNT(*) FROM orders o WHERE o.received_by = s.name) as order_count,
                   (SELECT COUNT(*) FROM inventory i WHERE i.received_by = s.name) as inv_count
            FROM staff s
            ORDER BY s.name
        """)
        ).fetchall()

        for row in staff_after:
            print(f"  id={row[0]:>3}  name={row[1]!r:<25}  orders={row[2]}  inventory={row[3]}")

        print()
        print("=" * 70)
        print("AFTER: All distinct orders.received_by values")
        print("=" * 70)

        order_after = conn.execute(
            text("""
            SELECT received_by, COUNT(*) as cnt
            FROM orders
            WHERE received_by IS NOT NULL AND received_by != ''
            GROUP BY received_by
            ORDER BY received_by
        """)
        ).fetchall()

        for row in order_after:
            print(f"  {row[0]!r:<30}  count={row[1]}")

        print()
        print("=" * 70)
        print("AFTER: All distinct inventory.received_by values")
        print("=" * 70)

        inv_after = conn.execute(
            text("""
            SELECT received_by, COUNT(*) as cnt
            FROM inventory
            WHERE received_by IS NOT NULL AND received_by != ''
            GROUP BY received_by
            ORDER BY received_by
        """)
        ).fetchall()

        for row in inv_after:
            print(f"  {row[0]!r:<30}  count={row[1]}")

        # Summary
        print()
        print("=" * 70)
        print(f"SUMMARY: {len(staff_after)} staff records remaining")
        print(f"         {len(order_after)} distinct received_by in orders")
        print(f"         {len(inv_after)} distinct received_by in inventory")
        print("=" * 70)


if __name__ == "__main__":
    main()
