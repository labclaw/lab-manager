"""PubChem PUG REST API client for product enrichment."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PROPERTIES = "MolecularWeight,MolecularFormula,CanonicalSMILES,IUPACName,CID"
_TIMEOUT = 3.0  # seconds
_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_MAX = 1024
_LOCK = __import__("threading").Lock()

# Rate limiting: PubChem allows 5 requests/second
_MIN_INTERVAL = 0.2  # 200ms between requests
_last_request_time: float = 0.0


def _rate_limit() -> None:
    """Enforce minimum interval between PubChem requests.

    Uses slot-claiming: inside the lock we advance _last_request_time
    to the moment the caller's request *will* fire, so the next thread
    sees a future timestamp and computes its own wait accordingly.
    The actual sleep happens outside the lock to avoid blocking others.
    """
    global _last_request_time
    with _LOCK:
        now = time.monotonic()
        next_slot = max(now, _last_request_time + _MIN_INTERVAL)
        _last_request_time = next_slot
    wait = next_slot - now
    if wait > 0:
        time.sleep(wait)


def _fetch_properties(
    identifier: str, namespace: str = "name"
) -> dict[str, Any] | None:
    """Fetch compound properties from PubChem by name or other namespace.

    Returns raw property dict or None on failure/not-found.
    """
    url = f"{_BASE_URL}/compound/{namespace}/{identifier}/property/{_PROPERTIES}/JSON"
    _rate_limit()
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code == 404:
            return None
        if resp.status_code == 429:
            logger.warning("PubChem rate limit exceeded")
            return None
        resp.raise_for_status()
        data = resp.json()
        props_list = data.get("PropertyTable", {}).get("Properties", [])
        if not props_list:
            return None
        return props_list[0]
    except httpx.TimeoutException:
        logger.warning("PubChem request timed out for %s/%s", namespace, identifier)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "PubChem HTTP error %s for %s/%s",
            exc.response.status_code,
            namespace,
            identifier,
        )
        return None
    except Exception:
        logger.exception(
            "Unexpected error fetching PubChem data for %s/%s", namespace, identifier
        )
        return None


def _fetch_cas(cid: int) -> str | None:
    """Fetch CAS number from PubChem synonyms for a given CID.

    CAS numbers follow the pattern NNNNN-NN-N and are typically listed
    among PubChem synonyms.
    """
    import re

    url = f"{_BASE_URL}/compound/cid/{cid}/synonyms/JSON"
    _rate_limit()
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code != 200:
            return None
        data = resp.json()
        synonyms_list = data.get("InformationList", {}).get("Information", [])
        if not synonyms_list:
            return None
        synonyms = synonyms_list[0].get("Synonym", [])
        cas_re = re.compile(r"^\d{2,7}-\d{2}-\d$")
        for syn in synonyms:
            if cas_re.match(syn):
                return syn
        return None
    except Exception:
        logger.warning("Failed to fetch CAS for CID %s", cid)
        return None


def _props_to_result(props: dict[str, Any], cas: str | None = None) -> dict[str, Any]:
    """Convert raw PubChem properties to our enrichment dict."""
    result: dict[str, Any] = {}
    cid = props.get("CID")
    if cid is not None:
        result["pubchem_cid"] = int(cid)
    mw = props.get("MolecularWeight")
    if mw is not None:
        result["molecular_weight"] = float(mw)
    mf = props.get("MolecularFormula")
    if mf:
        result["molecular_formula"] = str(mf)
    smiles = props.get("CanonicalSMILES")
    if smiles:
        result["smiles"] = str(smiles)
    iupac = props.get("IUPACName")
    if iupac:
        result["iupac_name"] = str(iupac)
    if cas:
        result["cas_number"] = cas
    return result


def enrich_product(name: str, catalog_number: str | None = None) -> dict[str, Any]:
    """Look up product info from PubChem by name (and optionally catalog number).

    Returns a dict with available fields:
        cas_number, molecular_weight, molecular_formula, smiles,
        iupac_name, pubchem_cid

    Returns empty dict if nothing found.

    NOTE: This call is synchronous and blocks for 6-9s (up to 3 HTTP calls
    with 3s timeout each + rate-limit sleeps). Should be moved to a background
    task (e.g. via FastAPI BackgroundTasks or an async queue) in a future
    iteration so it doesn't block the API response.
    """
    # Check cache first
    cache_key = f"{name}|{catalog_number or ''}"
    with _LOCK:
        if cache_key in _CACHE:
            return _CACHE[cache_key]

    # Try by name first
    props = _fetch_properties(name, "name")

    # Fallback: try catalog_number as name
    if props is None and catalog_number:
        props = _fetch_properties(catalog_number, "name")

    if props is None:
        result: dict[str, Any] = {}
        _cache_put(cache_key, result)
        return result

    # Fetch CAS from synonyms
    cid = props.get("CID")
    cas = _fetch_cas(cid) if cid else None

    result = _props_to_result(props, cas)
    _cache_put(cache_key, result)
    return result


def _cache_put(key: str, value: dict[str, Any]) -> None:
    """Store result in cache, evicting oldest if full."""
    with _LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            oldest = next(iter(_CACHE))
            del _CACHE[oldest]
        _CACHE[key] = value


def clear_cache() -> None:
    """Clear the enrichment cache (useful for testing)."""
    _CACHE.clear()
