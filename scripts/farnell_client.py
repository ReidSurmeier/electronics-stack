"""Farnell / Element14 component search client.

API: element14 Product Search API v1
Docs: https://partner.element14.com/docs/Product_Search_API_REST__Description

Setup:
    1. Register: https://partner.element14.com/
    2. Add FARNELL_API_KEY to ~/.config/electronics-stack/.env

Usage:
    from farnell_client import FarnellClient
    client = FarnellClient.from_env()
    parts = client.keyword_search("STM32F103C8T6", limit=3)

Interface (DEEP module — hides HTTP/auth detail):
    keyword_search(mpn, limit) -> list[PartRecord]

PartRecord schema:
    {
      "mpn": str,
      "manufacturer": str,
      "sku": str,
      "stock": int,
      "price_tiers": [{"qty": int, "price_usd": float}],
      "datasheet_url": str | None,
      "image_url": str | None
    }

Error modes:
    RuntimeError if FARNELL_API_KEY not set.
    Returns [] for empty results (does not raise).
    Returns {"error": ...} dict on transient HTTP failures.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

CONFIG_DIR = Path.home() / ".config" / "electronics-stack"
CACHE_DIR = Path.home() / ".cache" / "electronics-stack" / "farnell"
ENV_FILE = CONFIG_DIR / ".env"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://api.element14.com/catalog/products"
STORE_ID = "us.farnell.com"
CACHE_TTL = 3600  # 1 hour


def _load_env() -> dict[str, str]:
    env: dict[str, str] = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def _cache_key(mpn: str, limit: int) -> str:
    import hashlib
    return hashlib.md5(f"farnell:{mpn}:{limit}".encode()).hexdigest()


def _cache_get(key: str) -> Any | None:
    p = CACHE_DIR / f"{key}.json"
    if p.exists() and (time.time() - p.stat().st_mtime) < CACHE_TTL:
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _cache_set(key: str, val: Any) -> None:
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(val))


def _parse_price_tiers(prices: list[dict]) -> list[dict[str, Any]]:
    """Convert Farnell price break list to standard tier format."""
    tiers = []
    for p in prices or []:
        try:
            tiers.append({
                "qty": int(p.get("from", 1)),
                "price_usd": round(float(p.get("cost", 0)), 6),
            })
        except (TypeError, ValueError):
            continue
    return tiers


def _product_to_record(product: dict) -> dict[str, Any]:
    """Convert Farnell API product dict to standard PartRecord."""
    prices = product.get("prices", [])
    inv = product.get("inventoryStatus", {})
    stock = 0
    try:
        stock = int(inv.get("breakPackQuantity", 0) or 0)
    except (TypeError, ValueError):
        pass

    # Pick best datasheet URL
    datasheet_url: str | None = None
    for ds in product.get("datasheets", []) or []:
        url = ds.get("url", "")
        if url:
            datasheet_url = url
            break

    image_url: str | None = None
    thumbnail = product.get("thumbnailImageUrl", "")
    if thumbnail:
        image_url = thumbnail

    return {
        "mpn": product.get("translatedManufacturerPartNumber", "")
               or product.get("id", ""),
        "manufacturer": product.get("brandName", ""),
        "sku": product.get("sku", ""),
        "stock": stock,
        "price_tiers": _parse_price_tiers(prices),
        "datasheet_url": datasheet_url,
        "image_url": image_url,
    }


class FarnellClient:
    """Farnell/Element14 component search.

    Interface:
        keyword_search(mpn, limit) -> list[PartRecord]

    Error modes:
        RuntimeError if FARNELL_API_KEY not set.
        Returns [] on empty results (does not raise).
        Raises requests.HTTPError on non-retriable API errors.

    Invariants:
        Results cached for 1 hour on disk to avoid redundant calls.
        API key never echoed in error messages.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_env(cls) -> "FarnellClient":
        """Construct from FARNELL_API_KEY in env or .env file.

        Raises:
            RuntimeError: if FARNELL_API_KEY is not set.
        """
        env = _load_env()
        key = env.get("FARNELL_API_KEY")
        if not key:
            raise RuntimeError(
                f"FARNELL_API_KEY not set. Add to {ENV_FILE}"
            )
        return cls(key)

    def keyword_search(self, mpn: str, limit: int = 3) -> list[dict[str, Any]]:
        """Search by MPN. Returns up to `limit` PartRecord dicts.

        Results ordered by Farnell relevance score (descending).
        Returns [] if no matches found.
        """
        ck = _cache_key(mpn, limit)
        cached = _cache_get(ck)
        if cached is not None:
            return cached

        params = {
            "term": f"manuPartNum:{mpn}",
            "storeInfo.id": STORE_ID,
            "resultsSettings.offset": 0,
            "resultsSettings.numberOfResults": limit,
            "resultsSettings.responseGroup": "large",
            "callInfo.apiKey": self._api_key,
            "callInfo.responseDataFormat": "json",
        }

        resp = requests.get(API_BASE, params=params, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        products = (
            data.get("keywordSearchReturn", {})
            .get("products", [])
        ) or []

        records = [_product_to_record(p) for p in products[:limit]]
        _cache_set(ck, records)
        return records
