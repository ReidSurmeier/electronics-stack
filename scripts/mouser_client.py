"""Mouser API v2 client. Free tier = unlimited search requests with API key.

Setup:
  1. Sign up: https://www.mouser.com/api-signup/
  2. Add MOUSER_API_KEY to ~/.config/electronics-stack/.env
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path

import requests


CONFIG_DIR = Path.home() / ".config" / "electronics-stack"
CACHE_DIR = Path.home() / ".cache" / "electronics-stack" / "mouser"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = CONFIG_DIR / ".env"


def load_env() -> dict:
    env = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


class MouserClient:
    BASE = "https://api.mouser.com/api/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "MouserClient":
        env = load_env()
        key = env.get("MOUSER_API_KEY")
        if not key:
            raise RuntimeError(f"MOUSER_API_KEY not set. Add to {ENV_FILE}.")
        return cls(key)

    def _cache_get(self, key: str):
        p = CACHE_DIR / f"{key}.json"
        if p.exists() and (time.time() - p.stat().st_mtime) < 86400:
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
        return None

    def _cache_set(self, key: str, val):
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(val))

    def keyword_search(self, keyword: str, records: int = 10) -> dict:
        cache_key = f"kw_{abs(hash(keyword))}_{records}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        url = f"{self.BASE}/search/keyword"
        body = {"SearchByKeywordRequest": {"keyword": keyword, "records": records, "startingRecord": 0,
                                            "searchOptions": "", "searchWithYourSignUpLanguage": ""}}
        r = requests.post(url, params={"apiKey": self.api_key}, json=body, timeout=30)
        r.raise_for_status()
        out = r.json()
        self._cache_set(cache_key, out)
        return out

    def part_number_search(self, mpn: str) -> dict:
        cache_key = f"pn_{abs(hash(mpn))}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        url = f"{self.BASE}/search/partnumber"
        body = {"SearchByPartRequest": {"mouserPartNumber": mpn, "partSearchOptions": ""}}
        r = requests.post(url, params={"apiKey": self.api_key}, json=body, timeout=30)
        r.raise_for_status()
        out = r.json()
        self._cache_set(cache_key, out)
        return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: mouser_client.py <keyword|MPN>")
        sys.exit(1)
    try:
        c = MouserClient.from_env()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(2)
    print(json.dumps(c.keyword_search(sys.argv[1]), indent=2)[:4000])
