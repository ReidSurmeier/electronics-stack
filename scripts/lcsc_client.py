"""LCSC component lookup via local jlcparts SQLite cache.

No API key needed — uses the jlcparts community-maintained SQLite database
(https://github.com/yaqwsx/jlcparts), downloaded from GitHub Pages.

Auto-refresh: if cache is older than 7 days, re-downloads all split parts.

Usage:
    from lcsc_client import LcscClient
    client = LcscClient.from_env()
    parts = client.keyword_search("STM32F103C8T6", limit=5)
    part  = client.lookup_lcsc_id("C8734")

Interface (DEEP module — hide all SQLite/HTTP detail):
    keyword_search(mpn, limit) -> list[PartRecord]
    lookup_lcsc_id(c_code)     -> PartRecord | None

PartRecord schema:
    {
      "mpn": str,
      "manufacturer": str,
      "lcsc_id": str,           # e.g. "C8734"
      "basic_extended": str,    # "Basic" | "Extended" | "Preferred"
      "stock": int,
      "price_tiers": [{"qty": int, "price_usd": float}],
      "package": str,
      "datasheet_url": str | None
    }
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "electronics-stack" / "jlc"
DB_PATH = CACHE_DIR / "cache.sqlite3"
PARTS_BASE = "https://yaqwsx.github.io/jlcparts/data"
REFRESH_SECONDS = 7 * 24 * 3600  # 7 days


def _download_db() -> None:
    """Download all split-zip parts and extract cache.sqlite3."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Find how many parts exist
    import urllib.request

    parts: list[int] = []
    for i in range(1, 99):
        ext = f"z{i:02d}"
        try:
            with urllib.request.urlopen(
                f"{PARTS_BASE}/cache.{ext}", timeout=10
            ) as resp:
                if resp.status == 200:
                    parts.append(i)
                else:
                    break
        except Exception:
            break

    # Download all parts + main zip
    all_urls: list[tuple[str, Path]] = [
        (f"{PARTS_BASE}/cache.z{i:02d}", CACHE_DIR / f"cache.z{i:02d}") for i in parts
    ] + [(f"{PARTS_BASE}/cache.zip", CACHE_DIR / "cache.zip")]

    # Sequential download (no external deps)
    import urllib.request

    for url, dest in all_urls:
        if dest.exists() and dest.stat().st_size > 1_000_000:
            continue  # already present
        with urllib.request.urlopen(url, timeout=120) as resp:
            dest.write_bytes(resp.read())

    # Extract using 7z (installed via p7zip package)
    if DB_PATH.exists():
        DB_PATH.unlink()
    subprocess.run(
        ["7z", "x", str(CACHE_DIR / "cache.zip"), f"-o{CACHE_DIR}/", "-y"],
        check=True,
        capture_output=True,
    )


def _ensure_db() -> None:
    """Ensure DB exists and is fresh (<7 days old)."""
    if DB_PATH.exists():
        age = time.time() - DB_PATH.stat().st_mtime
        if age < REFRESH_SECONDS:
            return
    _download_db()


def _parse_price_tiers(raw: str | None) -> list[dict[str, Any]]:
    """Parse JSON price string -> [{qty, price_usd}]."""
    if not raw:
        return []
    try:
        tiers = json.loads(raw)
        return [
            {"qty": t.get("qFrom", 1), "price_usd": round(float(t.get("price", 0)), 6)}
            for t in tiers
            if isinstance(t, dict)
        ]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _row_to_record(row: tuple) -> dict[str, Any]:
    """Convert a DB row tuple to a PartRecord dict."""
    lcsc, mfr, manufacturer, package, basic, preferred, stock, price, datasheet = row
    if preferred:
        tier = "Preferred"
    elif basic:
        tier = "Basic"
    else:
        tier = "Extended"
    return {
        "mpn": mfr or "",
        "manufacturer": manufacturer or "",
        "lcsc_id": f"C{lcsc}",
        "basic_extended": tier,
        "stock": int(stock) if stock else 0,
        "price_tiers": _parse_price_tiers(price),
        "package": package or "",
        "datasheet_url": datasheet if datasheet else None,
    }


_QUERY_BY_MFR = """
    SELECT c.lcsc, c.mfr, COALESCE(m.name, '') AS manufacturer,
           c.package, c.basic, c.preferred, c.stock, c.price, c.datasheet
    FROM components c
    LEFT JOIN manufacturers m ON c.manufacturer_id = m.id
    WHERE c.mfr LIKE ?
    ORDER BY c.preferred DESC, c.basic DESC, c.stock DESC
    LIMIT ?
"""

_QUERY_BY_DESC = """
    SELECT c.lcsc, c.mfr, COALESCE(m.name, '') AS manufacturer,
           c.package, c.basic, c.preferred, c.stock, c.price, c.datasheet
    FROM components c
    LEFT JOIN manufacturers m ON c.manufacturer_id = m.id
    WHERE c.description LIKE ? OR c.mfr LIKE ?
    ORDER BY c.preferred DESC, c.basic DESC, c.stock DESC
    LIMIT ?
"""

_QUERY_BY_LCSC = """
    SELECT c.lcsc, c.mfr, COALESCE(m.name, '') AS manufacturer,
           c.package, c.basic, c.preferred, c.stock, c.price, c.datasheet
    FROM components c
    LEFT JOIN manufacturers m ON c.manufacturer_id = m.id
    WHERE c.lcsc = ?
"""


class LcscClient:
    """LCSC component lookup backed by a local jlcparts SQLite cache.

    Interface:
        keyword_search(mpn, limit) -> list[PartRecord]
        lookup_lcsc_id(c_code)     -> PartRecord | None

    Error modes:
        RuntimeError if DB missing and cannot be downloaded.
        Returns [] / None (not raises) for no-match queries.

    Invariants:
        DB refresh happens at most once per 7 days.
        All SQL is read-only (no writes to the cache).
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @classmethod
    def from_env(cls) -> "LcscClient":
        """Construct client; ensures DB is present and fresh."""
        _ensure_db()
        if not DB_PATH.exists():
            raise RuntimeError(
                f"jlcparts cache not found at {DB_PATH}. "
                "Run LcscClient._download_db() manually."
            )
        return cls(DB_PATH)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def keyword_search(self, mpn: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search by MPN / keyword. Returns up to `limit` PartRecord dicts.

        Prefers exact mfr matches over description matches.
        Results ordered: Preferred > Basic > Extended, then by stock descending.
        """
        conn = self._get_conn()
        pattern = f"%{mpn}%"
        # Try exact mfr first
        rows = conn.execute(_QUERY_BY_MFR, (pattern, limit)).fetchall()
        if not rows:
            rows = conn.execute(_QUERY_BY_DESC, (pattern, pattern, limit)).fetchall()
        return [_row_to_record(tuple(r)) for r in rows]

    def lookup_lcsc_id(self, c_code: str) -> dict[str, Any] | None:
        """Lookup a component by LCSC C-number (e.g. 'C8734' or '8734').

        Returns PartRecord or None if not found.
        """
        raw = c_code.lstrip("Cc")
        try:
            lcsc_int = int(raw)
        except ValueError:
            return None
        conn = self._get_conn()
        row = conn.execute(_QUERY_BY_LCSC, (lcsc_int,)).fetchone()
        if row is None:
            return None
        return _row_to_record(tuple(row))

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "LcscClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
