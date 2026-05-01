"""Nexar/Octopart GraphQL client.

Setup:
  1. Register: https://nexar.com/  -> create app -> save client_id + client_secret
  2. Free tier: 1000 requests/month for SupplyV4.
  3. Add to ~/.config/electronics-stack/.env :
       NEXAR_CLIENT_ID=...
       NEXAR_CLIENT_SECRET=...
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path

import requests


CONFIG_DIR = Path.home() / ".config" / "electronics-stack"
CACHE_DIR = Path.home() / ".cache" / "electronics-stack" / "octopart"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
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


class OctopartClient:
    TOKEN_URL = "https://identity.nexar.com/connect/token"
    GRAPHQL_URL = "https://api.nexar.com/graphql"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: dict | None = None
        self._load_token()

    @classmethod
    def from_env(cls):
        env = load_env()
        cid = env.get("NEXAR_CLIENT_ID")
        sec = env.get("NEXAR_CLIENT_SECRET")
        if not cid or not sec:
            raise RuntimeError(f"NEXAR_CLIENT_ID/SECRET not set. Add to {ENV_FILE}.")
        return cls(cid, sec)

    def _load_token(self):
        if TOKEN_FILE.exists():
            try:
                t = json.loads(TOKEN_FILE.read_text())
                if t.get("expires_at", 0) > time.time() + 30:
                    self._token = t
            except Exception:
                pass

    def _refresh(self):
        r = requests.post(self.TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "supply.domain",
        }, timeout=15)
        r.raise_for_status()
        body = r.json()
        body["expires_at"] = time.time() + int(body.get("expires_in", 1800))
        self._token = body
        TOKEN_FILE.write_text(json.dumps(body))
        try:
            TOKEN_FILE.chmod(0o600)
        except Exception:
            pass

    def _headers(self) -> dict:
        if not self._token or self._token.get("expires_at", 0) < time.time() + 30:
            self._refresh()
        return {"Authorization": f"Bearer {self._token['access_token']}", "Content-Type": "application/json"}

    def query(self, gql: str, variables: dict | None = None) -> dict:
        cache_key = f"q_{abs(hash(gql))}_{abs(hash(json.dumps(variables or {}, sort_keys=True)))}"
        p = CACHE_DIR / f"{cache_key}.json"
        if p.exists() and (time.time() - p.stat().st_mtime) < 86400:
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
        r = requests.post(self.GRAPHQL_URL, headers=self._headers(),
                          json={"query": gql, "variables": variables or {}}, timeout=30)
        r.raise_for_status()
        out = r.json()
        p.write_text(json.dumps(out))
        return out

    def search_mpn(self, mpn: str, limit: int = 10) -> dict:
        q = """
        query MPNSearch($mpn: String!, $limit: Int!) {
          supSearchMpn(q: $mpn, limit: $limit) {
            results {
              part {
                mpn
                manufacturer { name }
                shortDescription
                bestImage { url }
                specs { attribute { name } displayValue }
                bestDatasheet { url }
                medianPrice1000 { price currency }
                octopartUrl
                sellers {
                  company { name }
                  offers {
                    sku
                    inventoryLevel
                    moq
                    prices { price currency quantity }
                  }
                }
              }
            }
          }
        }
        """
        return self.query(q, {"mpn": mpn, "limit": limit})


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: octopart_client.py <MPN>")
        sys.exit(1)
    try:
        c = OctopartClient.from_env()
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(2)
    print(json.dumps(c.search_mpn(sys.argv[1]), indent=2)[:4000])
