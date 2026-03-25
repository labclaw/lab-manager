"""Vendor name normalization — map OCR variants to canonical names."""

from __future__ import annotations

VENDOR_ALIASES: dict[str, str] = {
    # Sigma-Aldrich / MilliporeSigma / Merck
    "sigma-aldrich": "Sigma-Aldrich",
    "sigma-aldrich, inc.": "Sigma-Aldrich",
    "sigma-aldrich, inc": "Sigma-Aldrich",
    "sigma aldrich": "Sigma-Aldrich",
    "sigma aldrich, inc.": "Sigma-Aldrich",
    "milliporesigma": "MilliporeSigma",
    "milliporesigma corporation": "MilliporeSigma",
    "emd millipore corporation": "MilliporeSigma",
    # Thermo Fisher / Fisher Scientific
    "fisher scientific": "Fisher Scientific",
    "fisher scientific co": "Fisher Scientific",
    "fisher scientific co.": "Fisher Scientific",
    "fisher scientific company": "Fisher Scientific",
    "fisher scientific technology inc.": "Fisher Scientific",
    "thermo fisher scientific chemicals inc.": "Thermo Fisher Scientific",
    "thermofisher scientific": "Thermo Fisher Scientific",
    # Bio-Rad
    "bio-rad": "Bio-Rad Laboratories",
    "bio-rad laboratories, inc.": "Bio-Rad Laboratories",
    # Invitrogen / Life Technologies
    "invitrogen": "Invitrogen",
    "invitrogen by life technologies": "Invitrogen",
    "invitrogen\u2122 by life technologies\u2122": "Invitrogen",
    "life technologies": "Invitrogen",
    "life technologies corpora": "Invitrogen",
    # McMaster-Carr
    "mcmaster-carr": "McMaster-Carr",
    # Westnet
    "westnet": "Westnet",
    "westnet - canton": "Westnet",
    "westnet inc.": "Westnet",
    # Genesee
    "genesee scientific": "Genesee Scientific",
    "genesee scientific, llc": "Genesee Scientific",
    # MedChemExpress
    "medchemexpress llc": "MedChemExpress",
    "medchem express llc": "MedChemExpress",
    # Patterson
    "patterson dental supply, inc.": "Patterson Dental",
    "patterson logistics services, inc.": "Patterson Dental",
    # Medline
    "medline": "Medline Industries",
    "medline industries lp": "Medline Industries",
    # Grainger
    "grainger": "Grainger",
    "ww grainger": "Grainger",
    # CDW
    "cdw-g": "CDW",
    "cdw logistics llc": "CDW",
    # DigiKey
    "digikey": "DigiKey Electronics",
    "digikey electronics": "DigiKey Electronics",
    "digikay": "DigiKey Electronics",
    # PluriSelect
    "pluriselect usa, inc.": "PluriSelect",
    "pluriselect usa, inc": "PluriSelect",
    # Creative Biolabs
    "creative biolabs": "Creative Biolabs",
    "creative biolabs inc.": "Creative Biolabs",
    # Nikon
    "nikon": "Nikon Instruments",
    "nikon instruments consignment": "Nikon Instruments",
}


def _normalize_key(s: str) -> str:
    """Produce a stable lookup key: lowercase, stripped, no trailing dots."""
    return s.lower().strip().rstrip(".")


# Pre-build lookup table with normalized keys so both "inc." and "inc" match
_LOOKUP: dict[str, str] = {_normalize_key(k): v for k, v in VENDOR_ALIASES.items()}


def normalize_vendor(name: str | None) -> str | None:
    """Normalize vendor name to canonical form.

    Lookup is case-insensitive with trailing-dot stripping.
    Returns the canonical name if matched, otherwise the original name unchanged.
    """
    if not name:
        return name
    key = _normalize_key(name)
    return _LOOKUP.get(key, name)
