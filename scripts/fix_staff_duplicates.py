"""Fix staff name duplicates caused by OCR extraction variants.

Finds duplicates via case-insensitive, reversed word order, and no-space matching.
Merges into canonical Title Case "First Last" records.
Updates all referencing tables: orders.received_by, inventory.received_by,
consumption_log.consumed_by, audit_log.changed_by.
"""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations

from sqlalchemy import create_engine, text

from lab_manager.config import Settings


def normalize_key(name: str) -> str:
    """Create a canonical comparison key: lowercase, sorted words, no extra spaces."""
    parts = re.split(r"\s+", name.strip().lower())
    # Also handle no-space variants like "wangpei" -> split won't help,
    # so we also produce a no-space key
    return " ".join(sorted(parts))


def no_space_key(name: str) -> str:
    """Key with all spaces removed, lowercase."""
    return re.sub(r"\s+", "", name.strip().lower())


def to_canonical(names: list[str]) -> str:
    """Pick canonical form: Title Case, First Last order.

    Heuristic: prefer the variant that already has a space and is Title Case.
    If multiple, prefer the one most frequently used.
    """
    # Find variants with spaces (proper two-word names)
    spaced = [n for n in names if " " in n.strip()]
    if not spaced:
        # All are single-word (e.g., "Wangpei") — we can't know the split
        # Return the most common as-is in Title Case
        return names[0].strip().title()

    # Among spaced variants, prefer Title Case "First Last" (not "Last First")
    # We'll just pick the first spaced variant and title-case it
    # But first, check if any is already clean Title Case
    for n in spaced:
        stripped = n.strip()
        if stripped == stripped.title() and len(stripped.split()) == 2:
            return stripped

    # Default: title-case the first spaced variant
    return spaced[0].strip().title()


def find_duplicate_groups(all_names: list[str]) -> list[list[str]]:
    """Group names that are duplicates by normalized key or no-space key."""
    # Build groups by normalized key (sorted words, lowercase)
    norm_groups: dict[str, list[str]] = defaultdict(list)
    for name in all_names:
        norm_groups[normalize_key(name)].append(name)

    # Build groups by no-space key
    nospace_groups: dict[str, list[str]] = defaultdict(list)
    for name in all_names:
        nospace_groups[no_space_key(name)].append(name)

    # Union-find to merge groups
    parent: dict[str, str] = {n: n for n in all_names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Merge by normalized key
    for group in norm_groups.values():
        for a, b in combinations(group, 2):
            union(a, b)

    # Merge by no-space key
    for group in nospace_groups.values():
        for a, b in combinations(group, 2):
            union(a, b)

    # Also check: if removing spaces from name A equals removing spaces from name B
    # (already handled by nospace_groups above)

    # Collect final groups
    final_groups: dict[str, list[str]] = defaultdict(list)
    for name in all_names:
        final_groups[find(name)].append(name)

    # Only return groups with more than 1 member
    return [g for g in final_groups.values() if len(g) > 1]


def main() -> None:
    s = Settings()
    engine = create_engine(s.database_url)

    with engine.begin() as conn:
        # ── Step 1: List all staff names and usage counts ──
        print("=" * 70)
        print("STEP 1: Staff table — all names and usage counts")
        print("=" * 70)

        staff_rows = conn.execute(
            text("""
            SELECT s.id, s.name, s.email, s.role, s.is_active,
                   (SELECT COUNT(*) FROM orders o
                    WHERE LOWER(o.received_by)
                      = LOWER(s.name))
                    as order_count
            FROM staff s
            ORDER BY s.name
        """)
        ).fetchall()

        staff_names = []
        staff_by_name: dict[str, list] = defaultdict(list)
        for row in staff_rows:
            print(
                f"  id={row[0]:>3}  name={row[1]!r:<25}"
                f"  email={row[2]}  role={row[3]}"
                f"  active={row[4]}  orders={row[5]}"
            )
            staff_names.append(row[1])
            staff_by_name[row[1]].append(row)

        # ── Step 2: Check orders.received_by for names not in staff table ──
        print()
        print("=" * 70)
        print("STEP 2: orders.received_by — all distinct values with counts")
        print("=" * 70)

        order_names = conn.execute(
            text("""
            SELECT received_by, COUNT(*) as cnt
            FROM orders
            WHERE received_by IS NOT NULL AND received_by != ''
            GROUP BY received_by
            ORDER BY received_by
        """)
        ).fetchall()

        all_order_names = []
        for row in order_names:
            in_staff = "  [IN STAFF]" if row[0] in staff_names else "  [NOT IN STAFF]"
            print(f"  {row[0]!r:<30}  count={row[1]}{in_staff}")
            all_order_names.append(row[0])

        # Also check inventory.received_by
        print()
        print("=" * 70)
        print("STEP 2b: inventory.received_by — distinct values")
        print("=" * 70)

        inv_names = conn.execute(
            text("""
            SELECT received_by, COUNT(*) as cnt
            FROM inventory
            WHERE received_by IS NOT NULL AND received_by != ''
            GROUP BY received_by
            ORDER BY received_by
        """)
        ).fetchall()

        all_inv_names = []
        for row in inv_names:
            print(f"  {row[0]!r:<30}  count={row[1]}")
            all_inv_names.append(row[0])

        # Check consumption_log.consumed_by
        print()
        print("=" * 70)
        print("STEP 2c: consumption_log.consumed_by — distinct values")
        print("=" * 70)

        cons_names = conn.execute(
            text("""
            SELECT consumed_by, COUNT(*) as cnt
            FROM consumption_log
            WHERE consumed_by IS NOT NULL AND consumed_by != ''
            GROUP BY consumed_by
            ORDER BY consumed_by
        """)
        ).fetchall()

        for row in cons_names:
            print(f"  {row[0]!r:<30}  count={row[1]}")

        # ── Step 3: Find duplicate groups ──
        print()
        print("=" * 70)
        print("STEP 3: Duplicate groups detected")
        print("=" * 70)

        # Combine all unique names from all sources
        all_names_set: set[str] = set()
        all_names_set.update(staff_names)
        all_names_set.update(all_order_names)
        all_names_set.update(all_inv_names)
        all_names_set.update(r[0] for r in cons_names)

        all_unique = sorted(all_names_set)
        groups = find_duplicate_groups(all_unique)

        if not groups:
            print("  No duplicates found!")
            return

        # Map: variant -> canonical
        rename_map: dict[str, str] = {}
        for group in groups:
            canonical = to_canonical(group)
            print(f"  Group: {group}")
            print(f"    -> canonical: {canonical!r}")
            for variant in group:
                if variant != canonical:
                    rename_map[variant] = canonical

        print()
        print(f"  Rename map ({len(rename_map)} renames):")
        for old, new in sorted(rename_map.items()):
            print(f"    {old!r} -> {new!r}")

        # ── Step 4 & 5: Merge staff table duplicates ──
        print()
        print("=" * 70)
        print("STEP 4: Merging staff table duplicates")
        print("=" * 70)

        for group in groups:
            canonical = to_canonical(group)
            # Find staff records in this group
            group_staff = []
            for name in group:
                if name in staff_by_name:
                    group_staff.extend(staff_by_name[name])

            if len(group_staff) <= 1:
                # Only one (or zero) staff record — just rename if needed
                for row in group_staff:
                    if row[1] != canonical:
                        print(f"  Renaming staff id={row[0]} from {row[1]!r} to {canonical!r}")
                        conn.execute(
                            text("UPDATE staff SET name = :new_name WHERE id = :sid"),
                            {"new_name": canonical, "sid": row[0]},
                        )
                continue

            # Multiple staff records — pick the canonical one (or the one with most orders)
            # Keep the one with the canonical name, or first one
            keep = None
            remove = []
            for row in group_staff:
                if row[1] == canonical and keep is None:
                    keep = row
                else:
                    remove.append(row)

            if keep is None:
                # No exact canonical match — keep the first, rename it
                keep = group_staff[0]
                remove = group_staff[1:]

            keep_id = keep[0]
            print(f"  Keeping staff id={keep_id} name={keep[1]!r} -> {canonical!r}")

            # Rename the keep record to canonical if needed
            if keep[1] != canonical:
                conn.execute(
                    text("UPDATE staff SET name = :new_name WHERE id = :sid"),
                    {"new_name": canonical, "sid": keep_id},
                )

            # Delete duplicates (handle FK constraints — staff table has no FK refs,
            # names are stored as strings not FK ids)
            for row in remove:
                print(f"  Deleting duplicate staff id={row[0]} name={row[1]!r}")
                conn.execute(text("DELETE FROM staff WHERE id = :sid"), {"sid": row[0]})

        # ── Step 6: Update orders.received_by ──
        print()
        print("=" * 70)
        print("STEP 5: Updating orders.received_by")
        print("=" * 70)

        for old_name, new_name in rename_map.items():
            result = conn.execute(
                text("UPDATE orders SET received_by = :new WHERE received_by = :old"),
                {"new": new_name, "old": old_name},
            )
            if result.rowcount > 0:
                print(f"  orders.received_by: {old_name!r} -> {new_name!r}  ({result.rowcount} rows)")

        # ── Step 7: Update inventory.received_by ──
        print()
        print("=" * 70)
        print("STEP 6: Updating inventory.received_by")
        print("=" * 70)

        for old_name, new_name in rename_map.items():
            result = conn.execute(
                text("UPDATE inventory SET received_by = :new WHERE received_by = :old"),
                {"new": new_name, "old": old_name},
            )
            if result.rowcount > 0:
                print(f"  inventory.received_by: {old_name!r} -> {new_name!r}  ({result.rowcount} rows)")

        # ── Update consumption_log.consumed_by ──
        print()
        print("=" * 70)
        print("STEP 7: Updating consumption_log.consumed_by")
        print("=" * 70)

        for old_name, new_name in rename_map.items():
            result = conn.execute(
                text("UPDATE consumption_log SET consumed_by = :new WHERE consumed_by = :old"),
                {"new": new_name, "old": old_name},
            )
            if result.rowcount > 0:
                print(f"  consumption_log.consumed_by: {old_name!r} -> {new_name!r}  ({result.rowcount} rows)")

        # ── Update audit_log.changed_by ──
        print()
        print("=" * 70)
        print("STEP 8: Updating audit_log.changed_by")
        print("=" * 70)

        for old_name, new_name in rename_map.items():
            result = conn.execute(
                text("UPDATE audit_log SET changed_by = :new WHERE changed_by = :old"),
                {"new": new_name, "old": old_name},
            )
            if result.rowcount > 0:
                print(f"  audit_log.changed_by: {old_name!r} -> {new_name!r}  ({result.rowcount} rows)")

        # ── After summary ──
        print()
        print("=" * 70)
        print("AFTER: Staff table summary")
        print("=" * 70)

        staff_after = conn.execute(
            text("""
            SELECT s.id, s.name,
                   (SELECT COUNT(*) FROM orders o WHERE o.received_by = s.name) as order_count
            FROM staff s
            ORDER BY s.name
        """)
        ).fetchall()

        for row in staff_after:
            print(f"  id={row[0]:>3}  name={row[1]!r:<25}  orders={row[2]}")

        print()
        print("=" * 70)
        print("AFTER: orders.received_by distinct values")
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
        print("DONE. All duplicates merged.")


if __name__ == "__main__":
    main()
