# harvesters/openlibrary_client.py
from __future__ import annotations
import re
import requests
from typing import Tuple, Optional, Dict, Any, List

BASE = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org/b/"

def _cover_url(cover_i: int | None, size="L"):
    return f"{COVERS}id/{cover_i}-{size}.jpg" if cover_i else None

def search_title(q: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Loose title search. Returns WORK-level hits (lightweight)."""
    r = requests.get(f"{BASE}/search.json", params={"q": q, "limit": limit}, timeout=12)
    r.raise_for_status()
    docs = r.json().get("docs", [])[:limit]
    hits = []
    for d in docs:
        hits.append({
            "external_id": d.get("key"),                    # e.g. "/works/OL12345W"
            "title": d.get("title"),
            "year": d.get("first_publish_year"),
            "authors": d.get("author_name", []) or [],
            "subjects": (d.get("subject") or [])[:8],
            "cover_url": _cover_url(d.get("cover_i")),
            "language": (d.get("language") or [None])[0],
        })
    return hits

# ---------- Dimensions helpers ----------

def _parse_dimensions(dim_str: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Parses strings like:
      "20 x 13 x 2.5 centimeters" or "8.5 x 5.5 x 1.2 inches"
    Returns (height_mm, width_mm, thickness_mm) as floats, or (None, None, None).
    """
    if not dim_str:
        return None, None, None
    nums = re.findall(r"[\d\.]+", dim_str)
    if len(nums) < 3:
        return None, None, None
    h, w, t = map(float, nums[:3])
    s = dim_str.lower()
    if "inch" in s:
        factor = 25.4        # inches → mm
    elif "centimeter" in s or "centimetre" in s or "cm" in s:
        factor = 10.0        # cm → mm
    elif "millimeter" in s or "millimetre" in s or "mm" in s:
        factor = 1.0
    else:
        # unknown unit; assume mm to avoid exaggeration
        factor = 1.0
    return h * factor, w * factor, t * factor

def _estimate_thickness_mm_from_pages(pages: Optional[int]) -> Optional[float]:
    if not pages or pages <= 0:
        return None
    # very rough paperback average ≈ 0.065–0.08 mm/page; pick 0.07
    return round(pages * 0.07, 2)

def _choose_edition_with_dims(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Pick the 'best' edition:
      1) has physical_dimensions
      2) else has number_of_pages (for thickness estimate)
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
    Given a work key like '/works/OL12345W', fetch editions and return
    height_mm, width_mm, thickness_mm, pages if available.
    """
    out = {"height_mm": None, "width_mm": None, "thickness_mm": None, "pages": None}
    if not work_key:
        return out

    # /works/{id}/editions.json
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

    # If thickness missing but pages available, estimate thickness
    if (t is None) and pages:
        t = _estimate_thickness_mm_from_pages(pages)

    out.update({
        "height_mm": float(h) if h is not None else None,
        "width_mm": float(w) if w is not None else None,
        "thickness_mm": float(t) if t is not None else None,
        "pages": int(pages) if isinstance(pages, int) else (int(pages) if str(pages).isdigit() else None),
    })
    return out

def _to_int_or_none(x):
    try:
        if x is None:
            return None
        # if float like 203.2 mm, round to nearest mm
        return int(round(float(x)))
    except Exception:
        return None

def build_payload_from_title_hit(hit: dict) -> dict:
    dims = fetch_dims_for_work(hit.get("external_id"))
    return {
        "external_id": hit.get("external_id"),
        "title": hit.get("title"),
        "year": hit.get("year"),
        "description": None,
        "cover_url": hit.get("cover_url"),
        "authors": hit.get("authors") or [],
        "subjects": hit.get("subjects") or [],
        "language": hit.get("language"),
        # ensure ints for ORM Integer columns
        "height_mm": _to_int_or_none(dims.get("height_mm")),
        "width_mm": _to_int_or_none(dims.get("width_mm")),
        "thickness_mm": _to_int_or_none(dims.get("thickness_mm")),
        "pages": _to_int_or_none(dims.get("pages")),
    }

