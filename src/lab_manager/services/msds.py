"""MSDS / SDS auto-linking service via PubChem."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_PUBCHEM_COMPOUND_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/JSON"
)
_TIMEOUT = 5.0

# GHS hazard pictogram keywords mapped to standard hazard classes.
_HAZARD_KEYWORDS: dict[str, str] = {
    "Flammable": "Flammable",
    "Flam.": "Flammable",
    "Pyrophoric": "Pyrophoric",
    "Self-reactive": "Self-reactive",
    "Self-heating": "Self-heating",
    "Organic peroxide": "Organic Peroxide",
    "Corrosive": "Corrosive",
    "Corros.": "Corrosive",
    "Skin Corrosion": "Corrosive",
    "Eye Damage": "Eye Damage",
    "Oxidizer": "Oxidizer",
    "Oxid.": "Oxidizer",
    "Gas under pressure": "Compressed Gas",
    "Compressed Gas": "Compressed Gas",
    "Liquefied gas": "Compressed Gas",
    "Toxic": "Acute Toxicity",
    "Acute Tox.": "Acute Toxicity",
    "Fatal": "Acute Toxicity",
    "Carcinogenic": "Carcinogenic",
    "Carc.": "Carcinogenic",
    "Mutagenic": "Mutagenic",
    "Muta.": "Mutagenic",
    "Reproductive": "Reproductive Toxicity",
    "Repr.": "Reproductive Toxicity",
    "STOT SE": "Specific Target Organ Toxicity (Single Exposure)",
    "STOT RE": "Specific Target Organ Toxicity (Repeated Exposure)",
    "Aspiration": "Aspiration Hazard",
    "Aquatic Acute": "Environmental Hazard",
    "Aquatic Chronic": "Environmental Hazard",
}

# Signal word mapping based on hazard severity.
_SIGNAL_WORD_MAP: dict[str, str] = {
    "Flammable": "Warning",
    "Pyrophoric": "Danger",
    "Self-reactive": "Danger",
    "Self-heating": "Warning",
    "Organic Peroxide": "Danger",
    "Corrosive": "Danger",
    "Eye Damage": "Danger",
    "Oxidizer": "Danger",
    "Compressed Gas": "Warning",
    "Acute Toxicity": "Danger",
    "Carcinogenic": "Danger",
    "Mutagenic": "Danger",
    "Reproductive Toxicity": "Danger",
    "Specific Target Organ Toxicity (Single Exposure)": "Danger",
    "Specific Target Organ Toxicity (Repeated Exposure)": "Danger",
    "Aspiration Hazard": "Danger",
    "Environmental Hazard": "Warning",
}

# Hazard classes that require safety review.
_REVIEW_REQUIRED_CLASSES = {
    "Pyrophoric",
    "Self-reactive",
    "Organic Peroxide",
    "Corrosive",
    "Acute Toxicity",
    "Carcinogenic",
    "Mutagenic",
    "Reproductive Toxicity",
    "Specific Target Organ Toxicity (Single Exposure)",
    "Specific Target Organ Toxicity (Repeated Exposure)",
    "Aspiration Hazard",
}

# Safety alert messages by hazard class.
_SAFETY_ALERTS: dict[str, str] = {
    "Flammable": (
        "Flammable liquid -- use in fume hood, away from ignition sources. "
        "Store in flammable cabinet."
    ),
    "Pyrophoric": (
        "Pyrophoric substance -- ignites spontaneously in air. "
        "Handle under inert atmosphere (N2/Ar). Fire extinguisher required."
    ),
    "Self-reactive": (
        "Self-reactive substance -- may decompose explosively. "
        "Keep away from heat, light, and incompatible materials."
    ),
    "Self-heating": (
        "Self-heating substance -- may catch fire. Store in cool, well-ventilated area."
    ),
    "Organic Peroxide": (
        "Organic peroxide -- may explode when heated. "
        "Store at controlled temperature, away from metals and accelerators."
    ),
    "Corrosive": (
        "Corrosive substance -- causes severe skin burns and eye damage. "
        "Wear chemical-resistant gloves, goggles, and lab coat. Use in fume hood."
    ),
    "Eye Damage": (
        "Causes serious eye damage. "
        "Wear splash-proof goggles. Eye wash station must be accessible."
    ),
    "Oxidizer": (
        "Oxidizing substance -- may cause or intensify fire. "
        "Keep away from flammable and combustible materials."
    ),
    "Compressed Gas": (
        "Compressed gas -- risk of explosion if heated. "
        "Secure cylinder upright, use pressure regulator, ventilated area."
    ),
    "Acute Toxicity": (
        "Acute toxic substance -- fatal if swallowed, inhaled, or absorbed. "
        "Use in fume hood with full PPE. Do not taste or smell."
    ),
    "Carcinogenic": (
        "Carcinogen -- may cause cancer. "
        "Minimize exposure. Use glove box or fume hood. Full PPE required."
    ),
    "Mutagenic": (
        "Mutagen -- may cause genetic damage. "
        "Avoid skin contact and inhalation. Use in containment."
    ),
    "Reproductive Toxicity": (
        "Reproductive toxicant -- may damage fertility or unborn child. "
        "Inform supervisor if pregnant. Strict exposure control."
    ),
    "Specific Target Organ Toxicity (Single Exposure)": (
        "STOT-SE -- may cause organ damage from single exposure. "
        "Use in well-ventilated area. Know target organs."
    ),
    "Specific Target Organ Toxicity (Repeated Exposure)": (
        "STOT-RE -- causes organ damage through prolonged exposure. "
        "Monitor exposure, use PPE, schedule regular health checks."
    ),
    "Aspiration Hazard": (
        "Aspiration hazard -- may be fatal if swallowed and enters airways. "
        "Do NOT induce vomiting if swallowed. Seek immediate medical help."
    ),
    "Environmental Hazard": (
        "Environmental hazard -- toxic to aquatic life. "
        "Do not discharge into drains. Collect spills for proper disposal."
    ),
}


def _extract_ghs_hazards(data: dict[str, Any]) -> list[str]:
    """Extract GHS hazard classifications from PubChem JSON response."""
    hazards: list[str] = []
    sections = data.get("PC_Compounds", [{}])[0].get("props", [])
    for prop in sections:
        label = prop.get("urn", {}).get("label", "")
        if "GHS" in label or "Hazard" in label:
            value = prop.get("value", {})
            sval = value.get("sval", "")
            if sval:
                hazards.append(sval)
    return hazards


def _classify_hazard(hazards: list[str]) -> tuple[str, str]:
    """Classify GHS hazards into a hazard class and signal word.

    Returns (hazard_class, signal_word). hazard_class is comma-separated
    unique classes; signal_word is "Danger" if any mapped class maps to it.
    """
    found_classes: list[str] = []
    signal_word = ""
    for hazard_text in hazards:
        for keyword, cls in _HAZARD_KEYWORDS.items():
            if keyword in hazard_text and cls not in found_classes:
                found_classes.append(cls)
                if _SIGNAL_WORD_MAP.get(cls) == "Danger":
                    signal_word = "Danger"
    if not signal_word and found_classes:
        signal_word = "Warning"
    hazard_class = ", ".join(found_classes)
    return hazard_class, signal_word


def _build_msds_url(cid: int | None) -> str | None:
    """Build a link to the PubChem compound page (acts as SDS landing page)."""
    if cid is None:
        return None
    return f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"


def lookup_msds(cas_number: str) -> dict[str, Any]:
    """Look up MSDS/SDS data for a compound by CAS number.

    Returns dict with keys: msds_url, hazard_class, signal_word,
    requires_safety_review. Returns empty-valued dict on failure.
    """
    result: dict[str, Any] = {
        "msds_url": None,
        "hazard_class": None,
        "signal_word": None,
        "requires_safety_review": False,
    }
    if not cas_number or not cas_number.strip():
        return result
    url = _PUBCHEM_COMPOUND_URL.format(query=cas_number.strip())
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code == 404:
            logger.info("PubChem: no compound found for CAS %s", cas_number)
            return result
        if resp.status_code == 429:
            logger.warning("PubChem rate limit exceeded for CAS %s", cas_number)
            return result
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        logger.warning("PubChem timeout for CAS %s", cas_number)
        return result
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "PubChem HTTP %s for CAS %s",
            exc.response.status_code,
            cas_number,
        )
        return result
    except Exception:
        logger.exception("Unexpected error looking up MSDS for CAS %s", cas_number)
        return result

    # Extract CID for the SDS URL.
    cid_list = data.get("PC_Compounds", [])
    cid = None
    if cid_list:
        cid = cid_list[0].get("id", {}).get("id", {}).get("cid")
    result["msds_url"] = _build_msds_url(cid)

    # Extract GHS hazard classifications.
    hazards = _extract_ghs_hazards(data)
    hazard_class, signal_word = _classify_hazard(hazards)
    result["hazard_class"] = hazard_class or None
    result["signal_word"] = signal_word or None
    result["requires_safety_review"] = any(
        cls in _REVIEW_REQUIRED_CLASSES
        for cls in hazard_class.split(", ")
        if hazard_class
    )
    return result


def get_safety_alert(product_name: str, hazard_class: str) -> str:
    """Return a safety reminder text based on hazard class.

    If multiple classes are present (comma-separated), returns the most
    severe alert. Falls back to a generic message for unknown classes.
    """
    if not hazard_class:
        return f"No specific safety data available for {product_name}."
    classes = [c.strip() for c in hazard_class.split(",")]
    for cls in reversed(classes):
        alert = _SAFETY_ALERTS.get(cls)
        if alert:
            return alert
    return (
        f"Hazard class '{hazard_class}' detected for {product_name}. "
        "Consult the Safety Data Sheet and follow institutional protocols."
    )
