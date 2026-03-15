"""Fix vendor name duplicates in the lab-manager PostgreSQL database.

Merges duplicate vendors by:
1. Reassigning orders and products to the canonical vendor
2. Deleting duplicate vendor records
3. Cleaning up ALL-CAPS names to title case
4. Storing old names as aliases on the canonical vendor
"""

from __future__ import annotations


from lab_manager.config import Settings
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Explicit merge rules: {canonical_name: [duplicate_names_to_merge]}
# ---------------------------------------------------------------------------
MERGE_RULES: dict[str, list[str]] = {
    "Genesee Scientific": ["Genesee Scientific, LLC"],
    "Jackson ImmunoResearch": ["Jackson ImmunoResearch LABORATORIES, INC."],
    "MedChemExpress": [
        "MedChemExpress LLC",
        "MedChem Express LLC",
        "MedChem Express",
        "MEDCHENEXPRESS LLC",
    ],
    "McMaster-Carr": ["MCMASTER-CARR"],
    "Thermo Fisher Scientific": [
        "THERMO FISHER SCIENTIFIC CHEMICALS INC.",
        "invitrogen by life technologies",
    ],
    "CDW": ["CDW LOGISTICS LLC", "CDW·G"],
    "GoldBio": ["GOLDBIO", "GOLDBIO®"],
    "Boster Biological Technology": ["BOSTER BIOLOGICAL TECHNOLOGICA"],
    "THORLABS, Inc.": ["THORLABS Inc."],
    "Nikon Instruments": ["Nikon"],
    "Patterson Dental Supply, Inc.": ["PATTERSON DENTAL"],
    "WESTNET": ["WESTNET inc."],
    "Digi-Key": ["DigiKey"],
    "Alta Biotech": ["Alta Biotech, LLC"],
}

# Vendor names to rename (ALL CAPS -> clean form), applied AFTER merges
# Only rename if the vendor still exists and name matches
RENAME_RULES: dict[str, str] = {
    "ALDON": "Aldon",
    "ATCC": "ATCC",  # keep as-is, it's an acronym
    "AVANTIK": "Avantik",
    "A-M SYSTEMS": "A-M Systems",
    "AZAR INTL., INC.": "Azar International, Inc.",
    "B&H PHOTO & VIDEO": "B&H Photo & Video",
    "CENTRE DE RECHERCHE/UNIV. LAVAL": "Centre de Recherche/Univ. Laval",
    "DRUMMOND SCIENTIFIC COMPANY": "Drummond Scientific Company",
    "GRAINGER": "Grainger",
    "LAMDA BIOTECH": "Lambda Biotech",
    "MEDLINE": "Medline",
    "QIAGEN": "QIAGEN",  # keep as-is, brand name
    "SUPPLY CLINIC": "Supply Clinic",
    "TED PELLA, INC.": "Ted Pella, Inc.",
    "UNIVERSITÉ LAVAL": "Universite Laval",
    "WESCS": "WESCS",  # keep as-is, acronym
}


def main() -> None:
    s = Settings()
    engine = create_engine(s.database_url)

    with engine.begin() as conn:
        # ---- Snapshot BEFORE ----
        before = conn.execute(
            text("SELECT id, name FROM vendors ORDER BY name")
        ).fetchall()
        before_count = len(before)
        print(f"=== BEFORE: {before_count} vendors ===")
        for vid, vname in before:
            print(f"  {vid:4d}  {vname}")
        print()

        # Build name -> id lookup
        name_to_id: dict[str, int] = {}
        for vid, vname in before:
            name_to_id[vname] = vid

        # ---- Process merges ----
        total_orders_moved = 0
        total_products_moved = 0
        total_deleted = 0

        for canonical_name, dupes in MERGE_RULES.items():
            # Find canonical vendor id
            canonical_id = name_to_id.get(canonical_name)
            if canonical_id is None:
                # Canonical name doesn't exist yet - pick the first dupe that exists
                for d in dupes:
                    if d in name_to_id:
                        canonical_id = name_to_id[d]
                        # Rename it to canonical
                        conn.execute(
                            text("UPDATE vendors SET name = :new WHERE id = :id"),
                            {"new": canonical_name, "id": canonical_id},
                        )
                        print(
                            f"  Renamed vendor {canonical_id} '{d}' -> '{canonical_name}'"
                        )
                        name_to_id[canonical_name] = canonical_id
                        del name_to_id[d]
                        dupes = [x for x in dupes if x != d]
                        break
                else:
                    print(
                        f"  SKIP: No vendors found for merge group '{canonical_name}'"
                    )
                    continue

            # Collect aliases from old names
            all_old_names = []

            for dupe_name in dupes:
                dupe_id = name_to_id.get(dupe_name)
                if dupe_id is None:
                    print(f"  SKIP dupe: '{dupe_name}' not found")
                    continue

                all_old_names.append(dupe_name)

                # Move orders
                r = conn.execute(
                    text(
                        "UPDATE orders SET vendor_id = :canon WHERE vendor_id = :dupe"
                    ),
                    {"canon": canonical_id, "dupe": dupe_id},
                )
                orders_moved = r.rowcount
                total_orders_moved += orders_moved

                # Move products
                r = conn.execute(
                    text(
                        "UPDATE products SET vendor_id = :canon WHERE vendor_id = :dupe"
                    ),
                    {"canon": canonical_id, "dupe": dupe_id},
                )
                products_moved = r.rowcount
                total_products_moved += products_moved

                # Delete duplicate vendor
                conn.execute(
                    text("DELETE FROM vendors WHERE id = :id"),
                    {"id": dupe_id},
                )
                total_deleted += 1
                del name_to_id[dupe_name]

                print(
                    f"  Merged '{dupe_name}' (id={dupe_id}) -> '{canonical_name}' (id={canonical_id}): "
                    f"{orders_moved} orders, {products_moved} products moved"
                )

            # Append old names as aliases on canonical vendor
            if all_old_names:
                existing_aliases = conn.execute(
                    text("SELECT aliases FROM vendors WHERE id = :id"),
                    {"id": canonical_id},
                ).scalar()
                if existing_aliases is None:
                    existing_aliases = []
                merged_aliases = list(set(existing_aliases + all_old_names))
                import json

                conn.execute(
                    text(
                        "UPDATE vendors SET aliases = CAST(:aliases AS jsonb) WHERE id = :id"
                    ),
                    {"aliases": json.dumps(merged_aliases), "id": canonical_id},
                )

            # Rename canonical vendor to clean form if needed
            current_name = conn.execute(
                text("SELECT name FROM vendors WHERE id = :id"),
                {"id": canonical_id},
            ).scalar()
            if current_name != canonical_name:
                conn.execute(
                    text("UPDATE vendors SET name = :new WHERE id = :id"),
                    {"new": canonical_name, "id": canonical_id},
                )
                print(
                    f"  Renamed vendor {canonical_id} '{current_name}' -> '{canonical_name}'"
                )

        print()
        print(
            f"Merges complete: {total_deleted} duplicates deleted, "
            f"{total_orders_moved} orders moved, {total_products_moved} products moved"
        )
        print()

        # ---- Apply rename rules (ALL CAPS cleanup) ----
        renames_done = 0
        for old_name, new_name in RENAME_RULES.items():
            if old_name == new_name:
                continue
            vid = name_to_id.get(old_name)
            if vid is None:
                continue
            conn.execute(
                text("UPDATE vendors SET name = :new WHERE id = :id"),
                {"new": new_name, "id": vid},
            )
            # Update aliases to include old name
            existing_aliases = conn.execute(
                text("SELECT aliases FROM vendors WHERE id = :id"),
                {"id": vid},
            ).scalar()
            if existing_aliases is None:
                existing_aliases = []
            if old_name not in existing_aliases:
                merged = existing_aliases + [old_name]
                import json

                conn.execute(
                    text(
                        "UPDATE vendors SET aliases = CAST(:aliases AS jsonb) WHERE id = :id"
                    ),
                    {"aliases": json.dumps(merged), "id": vid},
                )
            name_to_id[new_name] = vid
            del name_to_id[old_name]
            renames_done += 1
            print(f"  Renamed: '{old_name}' -> '{new_name}' (id={vid})")

        print(f"\nRenames complete: {renames_done} vendors renamed")
        print()

        # ---- Snapshot AFTER ----
        after = conn.execute(
            text("SELECT id, name FROM vendors ORDER BY name")
        ).fetchall()
        after_count = len(after)
        print(
            f"=== AFTER: {after_count} vendors ({before_count - after_count} removed) ==="
        )
        for vid, vname in after:
            print(f"  {vid:4d}  {vname}")

        # ---- Check for remaining case-insensitive duplicates ----
        print("\n=== Checking for remaining case-insensitive duplicates ===")
        ci_dupes = conn.execute(
            text("""
                SELECT LOWER(name), array_agg(id), array_agg(name)
                FROM vendors
                GROUP BY LOWER(name)
                HAVING COUNT(*) > 1
                ORDER BY LOWER(name)
            """)
        ).fetchall()
        if ci_dupes:
            print("WARNING: Remaining duplicates found:")
            for lower_name, ids, names in ci_dupes:
                print(f"  '{lower_name}': {list(zip(ids, names))}")
        else:
            print("  None found - all clean!")


if __name__ == "__main__":
    main()
