"""Safety service — PPE requirements and waste disposal based on GHS hazard codes."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.models.product import Product


# ---------------------------------------------------------------------------
# GHS Hazard Statement → PPE / disposal mapping
# ---------------------------------------------------------------------------

GHS_HAZARD_MAP: dict[str, dict[str, str]] = {
    "H200": {
        "category": "explosive",
        "ppe": "Use in fume hood, no open flames, fire-resistant lab coat",
        "disposal": "Collect explosive waste separately. Contact EHS for pickup.",
    },
    "H220": {
        "category": "flammable_gas",
        "ppe": "Use in fume hood, no open flames, fire-resistant lab coat",
        "disposal": "Ventilate area. Do not dispose in sealed containers.",
    },
    "H225": {
        "category": "highly_flammable",
        "ppe": "Use in fume hood, no open flames, fire-resistant lab coat, safety goggles",
        "disposal": "Collect in approved flammable waste container. Keep away from ignition.",
    },
    "H226": {
        "category": "flammable",
        "ppe": "Use in fume hood, no open flames, fire-resistant lab coat",
        "disposal": "Collect in approved flammable waste container.",
    },
    "H228": {
        "category": "flammable_solid",
        "ppe": "No open flames, fire-resistant lab coat, safety goggles",
        "disposal": "Collect in non-combustible waste container.",
    },
    "H240": {
        "category": "explosive_self_reacting",
        "ppe": "Use blast shield, face shield, fire-resistant lab coat",
        "disposal": "Contact EHS immediately. Do not accumulate.",
    },
    "H241": {
        "category": "self_reacting_explosive",
        "ppe": "Use blast shield, face shield, fire-resistant lab coat",
        "disposal": "Contact EHS immediately. Do not accumulate.",
    },
    "H250": {
        "category": "pyrophoric",
        "ppe": "Use under inert atmosphere, fire-resistant lab coat, face shield",
        "disposal": "Quench under controlled conditions. Collect in inert waste.",
    },
    "H260": {
        "category": "water_reactive",
        "ppe": "Keep away from water, use in dry environment, face shield",
        "disposal": "Quench slowly with appropriate reagent. Contact EHS.",
    },
    "H270": {
        "category": "oxidizing_gas",
        "ppe": "No flammable materials nearby, use in well-ventilated area",
        "disposal": "Ventilate to atmosphere if safe. Follow institutional gas disposal.",
    },
    "H271": {
        "category": "oxidizer",
        "ppe": "No flammable materials nearby, safety goggles, lab coat",
        "disposal": "Collect separately from flammable waste.",
    },
    "H272": {
        "category": "oxidizing_solid",
        "ppe": "No flammable materials nearby, safety goggles, lab coat",
        "disposal": "Collect separately from flammable waste.",
    },
    "H280": {
        "category": "compressed_gas",
        "ppe": "Secure cylinder, use pressure regulator, safety goggles",
        "disposal": "Return to supplier or vent per institutional protocol.",
    },
    "H290": {
        "category": "corrosive_to_metals",
        "ppe": "Corrosion-resistant gloves, safety goggles, lab coat",
        "disposal": "Neutralize before disposal. Collect in compatible container.",
    },
    "H300": {
        "category": "fatal_if_swallowed",
        "ppe": "Use in fume hood, double gloves, face shield required, chemical apron",
        "disposal": "Collect as hazardous chemical waste. Label clearly.",
    },
    "H301": {
        "category": "toxic_if_swallowed",
        "ppe": "Use in fume hood, double gloves, face shield required",
        "disposal": "Collect as hazardous chemical waste. Label clearly.",
    },
    "H302": {
        "category": "harmful_if_swallowed",
        "ppe": "Wear nitrile gloves, safety goggles, lab coat",
        "disposal": "Collect as chemical waste.",
    },
    "H304": {
        "category": "fatal_if_aspirated",
        "ppe": "Do not swallow, wear nitrile gloves, safety goggles",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H310": {
        "category": "fatal_in_contact_with_skin",
        "ppe": "Double nitrile gloves, full-body protection, face shield",
        "disposal": "Collect as hazardous chemical waste. Decontaminate surfaces.",
    },
    "H311": {
        "category": "toxic_in_contact_with_skin",
        "ppe": "Use in fume hood, double gloves, face shield required",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H312": {
        "category": "harmful_in_contact_with_skin",
        "ppe": "Wear nitrile gloves, lab coat",
        "disposal": "Collect as chemical waste.",
    },
    "H314": {
        "category": "skin_corrosion",
        "ppe": "Acid-resistant gloves, face shield, chemical apron",
        "disposal": "Neutralize before disposal. Collect in compatible container.",
    },
    "H315": {
        "category": "skin_irritation",
        "ppe": "Wear nitrile gloves, lab coat",
        "disposal": "Collect as chemical waste.",
    },
    "H317": {
        "category": "skin_sensitization",
        "ppe": "Wear nitrile gloves, lab coat, avoid skin contact",
        "disposal": "Collect as chemical waste.",
    },
    "H318": {
        "category": "eye_damage",
        "ppe": "Safety goggles, face shield recommended",
        "disposal": "Collect as chemical waste.",
    },
    "H319": {
        "category": "eye_irritation",
        "ppe": "Safety goggles, lab coat",
        "disposal": "Collect as chemical waste.",
    },
    "H330": {
        "category": "fatal_if_inhaled",
        "ppe": "Use only in well-ventilated area or fume hood, respiratory protection",
        "disposal": "Seal container. Collect as hazardous chemical waste.",
    },
    "H331": {
        "category": "toxic_if_inhaled",
        "ppe": "Use only in well-ventilated area or fume hood",
        "disposal": "Seal container. Collect as hazardous chemical waste.",
    },
    "H332": {
        "category": "harmful_if_inhaled",
        "ppe": "Use in well-ventilated area",
        "disposal": "Collect as chemical waste.",
    },
    "H334": {
        "category": "respiratory_sensitization",
        "ppe": "Respiratory protection, use in fume hood",
        "disposal": "Seal container. Collect as hazardous chemical waste.",
    },
    "H335": {
        "category": "respiratory_irritation",
        "ppe": "Use in fume hood or well-ventilated area",
        "disposal": "Seal container. Collect as chemical waste.",
    },
    "H336": {
        "category": "drowsiness",
        "ppe": "Use in well-ventilated area, avoid prolonged exposure",
        "disposal": "Collect as chemical waste.",
    },
    "H340": {
        "category": "mutagenic",
        "ppe": "Use in fume hood, double gloves, face shield, chemical apron",
        "disposal": "Collect as hazardous chemical waste. Label as mutagen.",
    },
    "H341": {
        "category": "suspected_mutagenic",
        "ppe": "Use in fume hood, nitrile gloves, safety goggles, lab coat",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H350": {
        "category": "carcinogenic",
        "ppe": "Use in fume hood, double gloves, face shield, chemical apron",
        "disposal": "Collect as hazardous chemical waste. Label as carcinogen.",
    },
    "H351": {
        "category": "suspected_carcinogenic",
        "ppe": "Use in fume hood, nitrile gloves, safety goggles, lab coat",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H360": {
        "category": "reproductive_toxicity",
        "ppe": "Use in fume hood, double gloves, face shield, chemical apron",
        "disposal": "Collect as hazardous chemical waste. Label as reproductive toxin.",
    },
    "H361": {
        "category": "suspected_reproductive_toxicity",
        "ppe": "Use in fume hood, nitrile gloves, safety goggles, lab coat",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H370": {
        "category": "organ_damage_single",
        "ppe": "Use in fume hood, double gloves, face shield",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H371": {
        "category": "organ_damage_single_suspected",
        "ppe": "Use in fume hood, nitrile gloves, safety goggles",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H372": {
        "category": "organ_damage_repeated",
        "ppe": "Use in fume hood, double gloves, face shield",
        "disposal": "Collect as hazardous chemical waste. Minimize exposure.",
    },
    "H373": {
        "category": "organ_damage_repeated_suspected",
        "ppe": "Use in fume hood, nitrile gloves, safety goggles",
        "disposal": "Collect as hazardous chemical waste.",
    },
    "H400": {
        "category": "aquatic_acute",
        "ppe": "Wear nitrile gloves, safety goggles, lab coat",
        "disposal": "Prevent release to drains, collect waste separately.",
    },
    "H401": {
        "category": "aquatic_chronic_1",
        "ppe": "Wear nitrile gloves, safety goggles, lab coat",
        "disposal": "Prevent release to drains, collect waste separately.",
    },
    "H410": {
        "category": "aquatic_chronic_1_lte",
        "ppe": "Wear nitrile gloves, safety goggles, lab coat",
        "disposal": "Prevent release to drains, collect waste separately.",
    },
    "H411": {
        "category": "aquatic_chronic_2",
        "ppe": "Wear nitrile gloves, safety goggles, lab coat",
        "disposal": "Prevent release to drains, collect waste separately.",
    },
    "H412": {
        "category": "aquatic_chronic_3",
        "ppe": "Wear nitrile gloves, lab coat",
        "disposal": "Avoid release to drains. Collect waste separately.",
    },
    "H413": {
        "category": "aquatic_chronic_4",
        "ppe": "Wear nitrile gloves, lab coat",
        "disposal": "Avoid release to drains. Collect waste separately.",
    },
    "EUH071": {
        "category": "corrosive_respiratory",
        "ppe": "Use in fume hood, respiratory protection, face shield",
        "disposal": "Collect as hazardous chemical waste.",
    },
}

_HAZARD_RE = re.compile(r"\b(H\d{3}|EUH\d{3})\b", re.IGNORECASE)


def _parse_hazard_codes(hazard_info: str) -> list[str]:
    """Extract GHS hazard codes from free-text hazard_info field."""
    if not hazard_info:
        return []
    return [m.upper() for m in _HAZARD_RE.findall(hazard_info)]


def get_ppe_requirements(hazard_class: str) -> list[str]:
    """Return PPE items needed for a single GHS hazard code.

    Parameters
    ----------
    hazard_class:
        A GHS hazard statement code (e.g. ``"H225"``, ``"H314"``).

    Returns
    -------
    list[str]
        Individual PPE items extracted from the mapped guidance string.
    """
    code = hazard_class.upper().strip()
    entry = GHS_HAZARD_MAP.get(code)
    if entry is None:
        return ["Consult SDS for detailed PPE requirements"]
    return [item.strip() for item in entry["ppe"].split(",")]


def get_waste_disposal_guide(hazard_class: str) -> str:
    """Return waste disposal instructions for a single GHS hazard code.

    Parameters
    ----------
    hazard_class:
        A GHS hazard statement code (e.g. ``"H400"``).

    Returns
    -------
    str
        Disposal guidance string.
    """
    code = hazard_class.upper().strip()
    entry = GHS_HAZARD_MAP.get(code)
    if entry is None:
        return "Follow institutional chemical waste disposal procedures."
    return entry["disposal"]


def get_product_safety_info(product: Product) -> dict:
    """Return full safety information for a product based on its hazard_info.

    Parameters
    ----------
    product:
        A Product model instance with ``hazard_info`` and ``is_hazardous`` fields.

    Returns
    -------
    dict
        Keys: ``product_id``, ``product_name``, ``is_hazardous``, ``hazard_codes``,
        ``ppe_requirements``, ``waste_disposal``.
    """
    hazard_codes = _parse_hazard_codes(getattr(product, "hazard_info", "") or "")

    ppe: list[str] = []
    disposal: list[str] = []
    for code in hazard_codes:
        ppe.extend(get_ppe_requirements(code))
        disposal.append(get_waste_disposal_guide(code))

    # Deduplicate while preserving order
    seen_ppe: set[str] = set()
    unique_ppe: list[str] = []
    for item in ppe:
        if item not in seen_ppe:
            seen_ppe.add(item)
            unique_ppe.append(item)

    seen_disposal: set[str] = set()
    unique_disposal: list[str] = []
    for item in disposal:
        if item not in seen_disposal:
            seen_disposal.add(item)
            unique_disposal.append(item)

    return {
        "product_id": product.id,
        "product_name": product.name,
        "is_hazardous": getattr(product, "is_hazardous", False),
        "hazard_codes": hazard_codes,
        "ppe_requirements": unique_ppe,
        "waste_disposal": unique_disposal,
    }


def check_inventory_safety(db: Session) -> list[dict]:
    """Scan inventory for hazardous items without proper safety data.

    Returns warnings for:
    - Products marked ``is_hazardous`` but missing ``hazard_info``
    - Products with ``hazard_info`` but no recognizable GHS codes
    - Products marked ``is_hazardous`` but missing ``cas_number``
    """
    warnings: list[dict] = []

    # Hazardous products missing hazard_info
    products_no_info = db.scalars(
        select(Product).where(
            Product.is_hazardous == True,  # noqa: E712
            (Product.hazard_info == None) | (Product.hazard_info == ""),  # noqa: E711
        )
    ).all()

    for p in products_no_info:
        warnings.append(
            {
                "product_id": p.id,
                "product_name": p.name,
                "catalog_number": p.catalog_number,
                "warning_type": "missing_hazard_info",
                "severity": "warning",
                "message": (
                    f"Product '{p.name}' (ID {p.id}) is marked hazardous but has no "
                    f"hazard info. Please update with GHS hazard codes."
                ),
            }
        )

    # Hazardous products missing CAS number
    products_no_cas = db.scalars(
        select(Product).where(
            Product.is_hazardous == True,  # noqa: E712
            (Product.cas_number == None) | (Product.cas_number == ""),  # noqa: E711
        )
    ).all()

    for p in products_no_cas:
        warnings.append(
            {
                "product_id": p.id,
                "product_name": p.name,
                "catalog_number": p.catalog_number,
                "warning_type": "missing_cas_number",
                "severity": "info",
                "message": (
                    f"Product '{p.name}' (ID {p.id}) is hazardous but has no CAS number. "
                    f"Adding CAS number enables automated SDS lookups."
                ),
            }
        )

    # Products with hazard_info but no recognizable GHS codes
    products_bad_codes = db.scalars(
        select(Product).where(
            Product.is_hazardous == True,  # noqa: E712
            Product.hazard_info != None,  # noqa: E711
            Product.hazard_info != "",
        )
    ).all()

    for p in products_bad_codes:
        codes = _parse_hazard_codes(getattr(p, "hazard_info", "") or "")
        if not codes:
            warnings.append(
                {
                    "product_id": p.id,
                    "product_name": p.name,
                    "catalog_number": p.catalog_number,
                    "warning_type": "unrecognized_hazard_codes",
                    "severity": "info",
                    "message": (
                        f"Product '{p.name}' (ID {p.id}) has hazard info "
                        f"'{p.hazard_info}' but no recognized GHS codes found. "
                        f"Use standard H-codes (e.g. H225, H314)."
                    ),
                }
            )

    return warnings
