"""Vendor website URL patterns for one-click reorder."""

VENDOR_SEARCH_URLS: dict[str, str] = {
    "sigma-aldrich": "https://www.sigmaaldrich.com/US/en/search/{catalog}",
    "milliporesigma": "https://www.sigmaaldrich.com/US/en/search/{catalog}",
    "thermo fisher": "https://www.thermofisher.com/search/results?query={catalog}",
    "fisher scientific": "https://www.fishersci.com/us/en/search/{catalog}",
    "bio-rad": "https://www.bio-rad.com/en-us/search?query={catalog}",
    "addgene": "https://www.addgene.org/search/all/?q={catalog}",
    "abcam": "https://www.abcam.com/search?q={catalog}",
    "cell signaling": "https://www.cellsignal.com/search?q={catalog}",
    "atcc": "https://www.atcc.org/search#q={catalog}",
    "vwr": "https://us.vwr.com/store/search?query={catalog}",
    "goldbio": "https://www.goldbio.com/search?q={catalog}",
    "biolegend": "https://www.biolegend.com/en-us/search-results?query={catalog}",
    "mcmaster-carr": "https://www.mcmaster.com/{catalog}",
    "genesee scientific": "https://gfrsa.com/?s={catalog}",
    "miltenyi": "https://www.miltenyibiotec.com/search?query={catalog}",
    "eppendorf": "https://www.eppendorf.com/us-en/search/?query={catalog}",
    "takara bio": "https://www.takarabio.com/search?q={catalog}",
    "qiagen": "https://www.qiagen.com/us/search?query={catalog}",
    "proteintech": "https://www.ptglab.com/search?query={catalog}",
    "santa cruz": "https://www.scbt.com/search?q={catalog}",
    "invitrogen": "https://www.thermofisher.com/search/results?query={catalog}",
}


def get_reorder_url(vendor_name: str, catalog_number: str) -> str | None:
    """Generate vendor website URL for reordering a product.

    Matches vendor name against known URL patterns (fuzzy substring match).
    Falls back to Google search for unknown vendors.
    Returns None if vendor_name or catalog_number is empty.
    """
    if not vendor_name or not catalog_number:
        return None
    key = vendor_name.lower().strip()
    for vendor_key, url_pattern in VENDOR_SEARCH_URLS.items():
        if vendor_key in key or key in vendor_key:
            return url_pattern.replace("{catalog}", catalog_number)
    return f"https://www.google.com/search?q={vendor_name}+{catalog_number}+order"
