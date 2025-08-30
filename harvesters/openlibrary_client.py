# openlibrary_client.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from requests.adapters import HTTPAdapter, Retry

# ---------------------------------------------------------------------------
# Constants / session
# ---------------------------------------------------------------------------

BASE = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org/b/"
DEFAULT_TIMEOUT = 12  # seconds
DEFAULT_LIMIT = 12

# One shared session with retry/backoff for resilience
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """
    Lazily create a requests.Session with reasonable retries and a helpful UA.
    """
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": "BookShelfApp/1.0 (+https://github.com/yourname/yourrepo)",
                "Accept": "application/json",
            }
        )
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
        )
        adapter = HTTPAdapter(max_retries=retries)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _session = s
    return _session


# ---------------------------------------------------------------------------
# Types / helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EditionPick:
    """
    Minimal info we care about from an edition entry to compute dimensions/pages.
    """
    physical_dimensions: Optional[str]
    number_of_pages: Optional[int]


def _cover_url(cover_i: Optional[int], size: str = "L") -> Optional[str]:
    """
    Build a cover URL from a cover id.
    Valid sizes are 'S', 'M', 'L' per OpenLibrary docs.
    """
    if not cover_i:
        return None
    size = size.upper()
    if size not in {"S", "M", "L"}:
        size = "L"
    return f"{COVERS}id/{cover_i}-{size}.jpg"


# ---------------------------------------------------------------------------
# Title search (WORK-level)
# ---------------------------------------------------------------------------

def search_title(q: str, limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    """
    Loose title search. Returns lightweight WORK-level hits suitable for a UI list.

    This is intentionally a single HTTP call (used for search UI, not the add step).
    """
    q = (q or "").strip()
    if not q:
        return []

    session = _get_session()
    r = session.get(
        f"{BASE}/search.json",
        params={"q": q, "limit": limit},
        timeout=DEFAULT_TIMEOUT,
    )
    r.raise_for_status()
    docs = (r.json() or {}).get("docs", [])[: max(0, int(limit))]

    hits: List[Dict[str, Any]] = []
    for d in docs:
        lang_list = d.get("language") or []
        lang = lang_list[0] if lang_list else None
        hits.append(
            {
                "external_id": d.get("key"),  # e.g. "/works/OL12345W"
                "title": d.get("title"),
                "year": d.get("first_publish_year"),
                "authors": d.get("author_name", []) or [],
                "cover_url": _cover_url(d.get("cover_i")),
                "language": lang,
            }
        )
    return hits


# ---------------------------------------------------------------------------
# Dimension utilities (normalize to centimeters)
# ---------------------------------------------------------------------------

_DIM_SEP = re.compile(r"\s*[x×]\s*", re.IGNORECASE)
_NUM = re.compile(r"[\d]+(?:[.,]\d+)?")  # supports "13.5" or "13,5"


def _parse_dimensions(dim_str: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Parse strings like:
      "20 x 13 x 2.5 centimeters", "8.5 × 5.5 × 1.2 inches", or "210 x 148 x 20 mm"
    Returns (height_cm, width_cm, thickness_cm) normalized to centimeters, or (None, None, None).

    We accept 'x' or '×' separators and decimal commas.
    """
    if not dim_str:
        return None, None, None

    s = dim_str.strip().lower()
    # Extract first three numeric tokens, allowing comma decimals.
    nums = _NUM.findall(s)
    if len(nums) < 3:
        # Try splitting on 'x' and parsing each component for robustness
        parts = _DIM_SEP.split(s)
        if len(parts) >= 3:
            nums = []
            for p in parts[:3]:
                m = _NUM.search(p)
                if not m:
                    nums.append(None)
                else:
                    nums.append(m.group(0))
        else:
            return None, None, None

    def _to_float(x: Optional[str]) -> Optional[float]:
        if not x:
            return None
        # normalize decimal comma to dot
        return float(x.replace(",", "."))

    try:
        h = _to_float(nums[0])
        w = _to_float(nums[1])
        t = _to_float(nums[2])
    except Exception:
        return None, None, None

    # Guess unit
    if "inch" in s or "inches" in s or "in." in s:
        factor = 2.54          # inches → cm
    elif "millimeter" in s or "millimetre" in s or "mm" in s:
        factor = 0.1           # mm → cm
    elif "centimeter" in s or "centimetre" in s or "cm" in s:
        factor = 1.0           # already cm
    else:
        factor = 1.0           # assume cm (conservative)

    def _mul(v: Optional[float]) -> Optional[float]:
        return v * factor if v is not None else None

    return _mul(h), _mul(w), _mul(t)


def _estimate_thickness_cm_from_pages(pages: Optional[int]) -> Optional[float]:
    """
    Very rough paperback average ≈ 0.07 mm/page ≈ 0.007 cm/page.
    Only used when explicit thickness is absent but pages exist.
    """
    if not pages or pages <= 0:
        return None
    return round(pages * 0.007, 3)


def _choose_edition_with_dims(entries: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# Work → editions (single call for dimensions/pages)
# ---------------------------------------------------------------------------

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
    if not wk:
        return out

    url = f"{BASE}/works/{wk}/editions.json"
    session = _get_session()
    r = session.get(url, params={"limit": 50}, timeout=DEFAULT_TIMEOUT)
    if r.status_code != 200:
        return out

    entries = (r.json() or {}).get("entries", []) or []
    ed = _choose_edition_with_dims(entries)
    if not ed:
        return out

    pages = ed.get("number_of_pages")
    try:
        pages_int = int(pages) if pages is not None else None
    except Exception:
        pages_int = None

    h, w, t = _parse_dimensions(ed.get("physical_dimensions", "") or "")

    # If thickness missing but pages are present, estimate
    if (t is None) and pages_int:
        t = _estimate_thickness_cm_from_pages(pages_int)

    out.update(
        {
            "height_cm": float(h) if h is not None else None,
            "width_cm": float(w) if w is not None else None,
            "thickness_cm": float(t) if t is not None else None,
            "pages": pages_int,
        }
    )
    return out


def _to_int_or_none(x: Any) -> Optional[int]:
    """
    Round float centimeters/pages to int, or None on failure.
    """
    try:
        if x is None:
            return None
        return int(round(float(x)))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Build payload for DAL (ONE extra call on Add)
# ---------------------------------------------------------------------------

def build_payload_from_title_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the payload for DAL using exactly ONE HTTP call at add time:
    - Call editions.json to get dimensions/pages (in cm).
    """
    dims = fetch_dims_for_work(hit.get("external_id"))

    return {
        "external_id": hit.get("external_id"),   # e.g. "/works/OL12345W"
        "title": hit.get("title"),
        "year": hit.get("year"),
        "description": None,                     # could be fetched via /works/{id}.json if desired
        "cover_url": hit.get("cover_url"),
        "authors": hit.get("authors") or [],
        "language": hit.get("language"),
        # ints (cm/pages) — keep aligned with your DB schema
        "height_cm": _to_int_or_none(dims.get("height_cm")),
        "width_cm": _to_int_or_none(dims.get("width_cm")),
        "thickness_cm": _to_int_or_none(dims.get("thickness_cm")),
        "pages": _to_int_or_none(dims.get("pages")),
    }

