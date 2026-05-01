"""URL routing + HTTP check layer for sourcing_health.

Provides:
  classify_url()       — routing layer (API / placeholder, returns None to fall through)
  http_check()         — HTTP HEAD with UA rotation; flags anti-scrape codes
  browserbase_fetch()  — Browserbase escalation via `bb fetch`
  cache_get/set()      — 7-day disk cache keyed by SHA-256
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".cache" / "electronics-stack"
URL_CACHE_DIR = CACHE_DIR / "sourcing" / "url_health"
URL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 7 * 24 * 3600  # 7 days


def cache_get(url: str) -> dict | None:
    p = URL_CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL:
        return None
    try:
        data = json.loads(p.read_text())
        data["via"] = "cached"
        data["escalated"] = False
        return data
    except Exception:
        return None


def cache_set(url: str, result: dict) -> None:
    p = URL_CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    payload = {k: v for k, v in result.items() if k not in ("via", "url")}
    payload["checked_at"] = time.time()
    try:
        p.write_text(json.dumps(payload))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HTTP HEAD layer
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
]
_ua_index = 0


def _next_ua() -> str:
    global _ua_index
    ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
    _ua_index += 1
    return ua


def _browser_headers() -> dict:
    return {
        "User-Agent": _next_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }


_REAL_NOT_FOUND = {404, 410, 451}
_ANTI_SCRAPE = {403, 429, 502, 503}


def http_check(url: str, timeout: float = 10.0) -> dict:
    """HEAD with realistic UA; GET fallback on 405; flags anti-scrape for escalation."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout, headers=_browser_headers())
        code = r.status_code
        if code == 405:
            r = requests.get(url, allow_redirects=True, timeout=timeout,
                             headers=_browser_headers(), stream=True)
            r.close()
            code = r.status_code
        if code in _REAL_NOT_FOUND:
            return {"status": f"status_{code}", "code": code, "final_url": r.url,
                    "via": "head", "escalated": False, "actionable": True}
        if code in _ANTI_SCRAPE:
            return {"status": f"status_{code}", "code": code, "via": "head",
                    "escalated": False, "actionable": None, "_needs_escalation": True}
        if code == 200 or code < 400:
            return {"status": "ok", "code": code, "final_url": r.url,
                    "redirects": len(r.history), "via": "head",
                    "escalated": False, "actionable": False}
        return {"status": f"status_{code}", "code": code, "final_url": r.url,
                "via": "head", "escalated": False, "actionable": True}
    except requests.Timeout:
        return {"status": "slow", "code": None, "via": "head",
                "escalated": False, "actionable": False,
                "note": f"HEAD timed out after {timeout}s"}
    except requests.RequestException as exc:
        return {"status": "error", "code": None, "via": "head",
                "escalated": False, "actionable": True, "note": str(exc)[:120]}


# ---------------------------------------------------------------------------
# Browserbase escalation
# ---------------------------------------------------------------------------

BB_PATH = Path.home() / ".npm-global" / "bin" / "bb"
BB_ESCALATION_CAP = 30


def browserbase_fetch(url: str) -> dict:
    """Escalate to `bb fetch` for anti-scrape-blocked URLs."""
    if not BB_PATH.exists():
        return {"status": "error", "code": None, "via": "browserbase",
                "escalated": True, "actionable": True, "note": "bb not installed"}
    try:
        proc = subprocess.run(
            [str(BB_PATH), "fetch", "--allow-redirects", url],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return {"status": "ok", "code": 200, "via": "browserbase",
                    "escalated": True, "actionable": False}
        err = (proc.stderr or "").strip()[:120]
        if "401" in err or "unauthorized" in err.lower() or "api key" in err.lower():
            return {"status": "error", "code": None, "via": "browserbase",
                    "escalated": True, "actionable": True,
                    "note": f"Browserbase auth failure: {err}"}
        return {"status": "error", "code": None, "via": "browserbase",
                "escalated": True, "actionable": True,
                "note": f"bb fetch failed (exit {proc.returncode}): {err}"}
    except subprocess.TimeoutExpired:
        return {"status": "slow", "code": None, "via": "browserbase",
                "escalated": True, "actionable": False,
                "note": "Browserbase fetch timed out (30s)"}
    except Exception as exc:
        return {"status": "error", "code": None, "via": "browserbase",
                "escalated": True, "actionable": True, "note": str(exc)[:120]}


# ---------------------------------------------------------------------------
# Pattern matchers
# ---------------------------------------------------------------------------

_AMAZON_SEARCH_RE = re.compile(r"amazon\.[a-z.]+/s(?:\?|$)|amazon\.[a-z.]+/s/")
_AMAZON_K_RE = re.compile(r"amazon\.[a-z.]+/[^?]*\?.*\bk=")
_ALIEXPRESS_RE = re.compile(r"aliexpress\.[a-z.]+/w/wholesale|aliexpress\.[a-z.]+/wholesale\?")
_DIGIKEY_RE = re.compile(r"digikey\.[a-z.]+/en/products/detail/")
_MOUSER_RE = re.compile(r"mouser\.[a-z.]+/ProductDetail/")
_LCSC_RE = re.compile(r"lcsc\.com/product-detail/|lcsc\.com/products/.*_C(\d+)\.html")
_LCSC_C_RE = re.compile(r"[_/](C\d+)\.html", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Individual routers
# ---------------------------------------------------------------------------

def route_amazon_search(url: str) -> dict | None:
    if "amazon." not in url:
        return None
    parsed = urlparse(url)
    is_search = (
        _AMAZON_SEARCH_RE.search(url)
        or _AMAZON_K_RE.search(url)
        or (parsed.path in ("/s", "/s/") and parsed.query)
    )
    if not is_search:
        return None
    return {"status": "ok_search_url", "code": None, "via": "search_placeholder",
            "escalated": False, "actionable": False,
            "note": "Amazon search URL — not health-checked; verify product manually"}


def route_aliexpress_wholesale(url: str) -> dict | None:
    if "aliexpress." not in url or not _ALIEXPRESS_RE.search(url):
        return None
    return {"status": "ok_search_url", "code": None, "via": "search_placeholder",
            "escalated": False, "actionable": False,
            "note": "AliExpress wholesale search URL — not health-checked; verify product manually"}


def route_digikey(url: str) -> dict | None:
    if not _DIGIKEY_RE.search(url):
        return None
    m = re.search(r"/products/detail/[^/]+/([^/]+)", url)
    if not m:
        return None
    part = m.group(1)
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from digikey_client import DigikeyClient
        dk = DigikeyClient.from_env()
    except (ImportError, RuntimeError):
        return None
    try:
        result = dk.product_details(part)
        prod = result.get("Product") or (result.get("Products") or [None])[0]
        if prod is None:
            return {"status": "not_found", "code": 404, "via": "digikey_api",
                    "escalated": False, "actionable": True,
                    "note": f"Digikey API: part {part!r} not found"}
        ps = prod.get("ProductStatus", {})
        status_str = ps.get("Status", "Active") if isinstance(ps, dict) else str(ps)
        bad = {"Obsolete", "Not For New Designs", "Discontinued at Digi-Key", "Last Time Buy"}
        if status_str in bad:
            return {"status": "lifecycle_" + status_str.lower().replace(" ", "_"),
                    "code": None, "via": "digikey_api", "escalated": False,
                    "actionable": True, "note": f"Digikey: {status_str}"}
        return {"status": "ok", "code": 200, "via": "digikey_api",
                "escalated": False, "actionable": False}
    except Exception:
        return None


def route_mouser(url: str) -> dict | None:
    if not _MOUSER_RE.search(url):
        return None
    m = re.search(r"/ProductDetail/([^/?#]+)", url)
    if not m:
        return None
    part = m.group(1)
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from mouser_client import MouserClient
        mc = MouserClient.from_env()
    except (ImportError, RuntimeError):
        return None
    try:
        result = mc.part_number_search(part)
        parts = result.get("SearchResults", {}).get("Parts", [])
        if not parts:
            return {"status": "not_found", "code": 404, "via": "mouser_api",
                    "escalated": False, "actionable": True,
                    "note": f"Mouser API: part {part!r} not found"}
        lifecycle = parts[0].get("LifecycleStatus", "") or ""
        if lifecycle in ("Obsolete", "Not For New Designs", "End of Life"):
            return {"status": "lifecycle_" + lifecycle.lower().replace(" ", "_"),
                    "code": None, "via": "mouser_api", "escalated": False,
                    "actionable": True, "note": f"Mouser: {lifecycle}"}
        return {"status": "ok", "code": 200, "via": "mouser_api",
                "escalated": False, "actionable": False}
    except Exception:
        return None


def route_lcsc(url: str) -> dict | None:
    if "lcsc.com" not in url or not _LCSC_RE.search(url):
        return None
    m = _LCSC_C_RE.search(url)
    if not m:
        m = re.search(r"[_/-](C\d+)(?:[_/-]|$)", url, re.IGNORECASE)
    if not m:
        return None
    c_num = m.group(1)
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from lcsc_client import LcscClient, DB_PATH
        if not DB_PATH.exists():
            return None
        client = LcscClient(DB_PATH)
        part = client.lookup_lcsc_id(c_num)
    except Exception:
        return None
    if part is None:
        return {"status": "not_found", "code": 404, "via": "lcsc_db",
                "escalated": False, "actionable": True,
                "note": f"LCSC DB: {c_num} not found"}
    return {"status": "ok", "code": 200, "via": "lcsc_db",
            "escalated": False, "actionable": False}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_ROUTERS = [route_amazon_search, route_aliexpress_wholesale,
            route_digikey, route_mouser, route_lcsc]


def classify_url(url: str) -> dict | None:
    """Try all routers. Returns result dict or None (fall through to HTTP)."""
    for router in _ROUTERS:
        result = router(url)
        if result is not None:
            return result
    return None
