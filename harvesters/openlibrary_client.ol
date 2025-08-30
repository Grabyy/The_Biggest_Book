# openlibrary_client.py
from __future__ import annotations

import re
import requests
from typing import Tuple, Optional, Dict, Any, List

BASE = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org/b/"


# --------- Utilities ---------
def _cover_url(cover_i: int | None, size: str = "L") -> Optional[str]:
    """Build a cover URL from a cover id."""
    return f"{COVERS}id/{cover_i}-{size}.jpg" if cover_i else None


# --------- Title search (WORK-level) ---------
def search_title(q: str, limit: int = 12) -> List[Dict[str, Any]]:
    """
    Loose title search. Returns lightweight WORK-level hits.
    NOTE: This is one HTTP call used for the search UI, not for the add step.
    """
    r = requests.get(f"{BASE}/search.json", params={"q": q, "limit": limit}, timeout=12)
    r.raise_for_status()
    docs = r.json().get("docs", [])[:limit]

    hits: List[Dict[str, Any]] = []
    for d in docs:
        hits.append(
            {
                "external_id": d.get("key"),  # e.g. "/works/OL12345W"
                "title": d.get("title"),
                "year": d.get("first_publish_year"),
                "authors": d.get("author_name", []) or [],
                "cover_url": _cover_url(d.get("cover_i")),
                "language": (d.get("language") or [None])[0],
            }
        )
    return hits


# --------- Dimensions helpers (normalize to centimeters) ---------
def _parse_dimensions(dim_str: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Parse strings like:
      "20 x 13 x 2.5 centimeters" or "8.5 x 5.5 x 1.2 inches"
    Returns (height_cm, width_cm, thickness_cm) or (None, None, None).
    All dimensions normalized to centimeters.
    """
    if not dim_str:
        return None, None, None

    nums = re.findall(r"[\d\.]+", dim_str)
    if len(nums) < 3:
        return None, None, None

    h, w, t = map(float, nums[:3])
    s = dim_str.lower()

    if "inch" in s:
        factor = 2.54          # inches → cm
    elif "millimeter" in s or "millimetre" in s or "mm" in s:
        factor = 0.1           # mm → cm
    elif "centimeter" in s or "centimetre" in s or "cm" in s:
        factor = 1.0           # already cm
    else:
        factor = 1.0           # assume cm (conservative)

    return h * factor, w * factor, t * factor


def _estimate_thickness_cm_from_pages(pages: Optional[int]) -> Optional[float]:
    """
    Very rough paperback average ≈ 0.07 mm/page ≈ 0.007 cm/page.
    """
    if not pages or pages <= 0:
        return None
    return round(pages * 0.007, 3)


def _choose_edition_with_dims(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Pick a 'best' edition:
      1) has physical_dimensions
      2) else has number_of_pages (so we can estimate thickness)
      3) else first entry
    """
    for e in entries:
        if e.get("physical_dimensions"):
            return e
    for e in entries:
        if e.get("number_of_pages"):
            return e
    return entries[0] if entries else None


def fetch_dims_for_work(work_key: str) -> Dict[str, Optional[float]]:
    """
    ONE HTTP CALL:
      Given a work key like '/works/OL12345W', hit
      /works/{id}/editions.json and return {height_cm, width_cm, thickness_cm, pages}.
    """
    out: Dict[str, Optional[float]] = {
        "height_cm": None,
        "width_cm": None,
        "thickness_cm": None,
        "pages": None,
    }
    if not work_key:
        return out

    wk = work_key.split("/")[-1]  # "OL12345W"
    url = f"{BASE}/works/{wk}/editions.json"
    r = requests.get(url, params={"limit": 50}, timeout=12)
    if r.status_code != 200:
        return out

    entries = (r.json() or {}).get("entries", []) or []
    ed = _choose_edition_with_dims(entries)
    if not ed:
        return out

    pages = ed.get("number_of_pages")
    h, w, t = _parse_dimensions(ed.get("physical_dimensions", ""))

    # If thickness missing but pages are present, estimate
    if (t is None) and pages:
        t = _estimate_thickness_cm_from_pages(pages)

    out.update(
        {
            "height_cm": float(h) if h is not None else None,
            "width_cm": float(w) if w is not None else None,
            "thickness_cm": float(t) if t is not None else None,
            "pages": int(pages) if isinstance(pages, int) else (int(pages) if str(pages).isdigit() else None),
        }
    )
    return out


def _to_int_or_none(x) -> Optional[int]:
    """Round float centimeters/pages to int (cm/pages), or None."""
    try:
        if x is None:
            return None
        return int(round(float(x)))
    except Exception:
        return None


# --------- Build payload for DAL (ONE extra call on Add) ---------
def build_payload_from_title_hit(hit: dict) -> dict:
    """
    Build the payload for DAL using exactly ONE HTTP call at add time:
    - Call editions.json to get dimensions/pages (in cm).
    """
    dims = fetch_dims_for_work(hit.get("external_id"))

    return {
        "external_id": hit.get("external_id"),   # e.g. "/works/OL12345W"
        "title": hit.get("title"),
        "year": hit.get("year"),
        "description": None,
        "cover_url": hit.get("cover_url"),
        "authors": hit.get("authors") or [],
        "language": hit.get("language"),
        # ints (cm/pages) — adjust DAL if your DB still expects *_mm
        "height_cm": _to_int_or_none(dims.get("height_cm")),
        "width_cm": _to_int_or_none(dims.get("width_cm")),
        "thickness_cm": _to_int_or_none(dims.get("thickness_cm")),
        "pages": _to_int_or_none(dims.get("pages")),
    }

