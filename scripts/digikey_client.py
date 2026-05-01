"""Digikey API v3 client with OAuth client_credentials flow + on-disk cache.

Setup (one-time):
  1. Create developer account: https://developer.digikey.com/
  2. Create a Production app, scope = ProductInformation, Marketplace = US.
  3. Save credentials in ~/.config/electronics-stack/.env :
       DIGIKEY_CLIENT_ID=...
       DIGIKEY_CLIENT_SECRET=...
  4. Free tier: 1000 keyword + 1000 KeywordSearch req/day.

Usage:
    from digikey_client import DigikeyClient
    dk = DigikeyClient.from_env()
    parts = dk.keyword_search("WM8960CGEFL/RV")
    info  = dk.product_details("296-WM8960CGEFL/RVCT-ND")
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any

import requests


CONFIG_DIR = Path.home() / ".config" / "electronics-stack"
CACHE_DIR = Path.home() / ".cache" / "electronics-stack" / "digikey"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = CONFIG_DIR / ".env"
TOKEN_FILE = CACHE_DIR / "token.json"


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


class DigikeyClient:
    BASE = "https://api.digikey.com"
    TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"

    def __init__(self, client_id: str, client_secret: str, locale_site: str = "US",
                 locale_language: str = "en", locale_currency: str = "USD"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.locale_site = locale_site
        self.locale_language = locale_language
        self.locale_currency = locale_currency
        self._token: dict | None = None
        self._load_token()

    @classmethod
    def from_env(cls) -> "DigikeyClient":
        env = load_env()
        cid = env.get("DIGIKEY_CLIENT_ID")
        sec = env.get("DIGIKEY_CLIENT_SECRET")
        if not cid or not sec:
            raise RuntimeError(
                "DIGIKEY_CLIENT_ID and DIGIKEY_CLIENT_SECRET not set. "
                f"Add them to {ENV_FILE} or your shell environment."
            )
        return cls(cid, sec)

    def _load_token(self):
        if TOKEN_FILE.exists():
            try:
                t = json.loads(TOKEN_FILE.read_text())
                if t.get("expires_at", 0) > time.time() + 30:
                    self._token = t
            except Exception:
                pass

    def _save_token(self):
        if self._token:
            TOKEN_FILE.write_text(json.dumps(self._token))
            try:
                TOKEN_FILE.chmod(0o600)
            except Exception:
                pass

    def _refresh_token(self):
        r = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        r.raise_for_status()
        body = r.json()
        body["expires_at"] = time.time() + int(body.get("expires_in", 600))
        self._token = body
        self._save_token()

    def _headers(self) -> dict:
        if not self._token or self._token.get("expires_at", 0) < time.time() + 30:
            self._refresh_token()
        return {
            "Authorization": f"Bearer {self._token['access_token']}",
            "X-DIGIKEY-Client-Id": self.client_id,
            "X-DIGIKEY-Locale-Site": self.locale_site,
            "X-DIGIKEY-Locale-Language": self.locale_language,
            "X-DIGIKEY-Locale-Currency": self.locale_currency,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _cache_get(self, key: str) -> Any | None:
        p = CACHE_DIR / f"{key}.json"
        if p.exists() and (time.time() - p.stat().st_mtime) < 86400:
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
        return None

    def _cache_set(self, key: str, value: Any):
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(value))

    def keyword_search(self, keyword: str, limit: int = 10) -> dict:
        """v4 ProductSearch endpoint: GET /products/v4/search/keyword (POST body)."""
        cache_key = f"kw_{abs(hash(keyword))}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        url = f"{self.BASE}/products/v4/search/keyword"
        body = {"Keywords": keyword, "Limit": limit, "Offset": 0}
        r = requests.post(url, headers=self._headers(), json=body, timeout=30)
        r.raise_for_status()
        out = r.json()
        self._cache_set(cache_key, out)
        return out

    def product_details(self, dk_part_number: str) -> dict:
        """v4 product details: GET /products/v4/search/{partNumber}/productdetails"""
        cache_key = f"pd_{abs(hash(dk_part_number))}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        from urllib.parse import quote
        url = f"{self.BASE}/products/v4/search/{quote(dk_part_number, safe='')}/productdetails"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        out = r.json()
        self._cache_set(cache_key, out)
        return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: digikey_client.py <keyword|MPN>")
        sys.exit(1)
    try:
        dk = DigikeyClient.from_env()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(2)
    out = dk.keyword_search(sys.argv[1], limit=5)
    print(json.dumps(out, indent=2)[:4000])
