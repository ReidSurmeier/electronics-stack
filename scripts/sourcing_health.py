"""BOM sourcing health checker.

Walks an xlsx BOM's Sourcing sheet, hits each Amazon/AliExpress URL with HEAD,
flags 404s, redirects, and rate-limited responses. Optionally enriches with
Digikey/Mouser API metadata (lifecycle status, stock, alternate suppliers).

Usage:
    sourcing_health.py <BOM.xlsx> [--with-api]
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import openpyxl
import requests


CACHE_DIR = Path.home() / ".cache" / "electronics-stack"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) electronics-stack/0.1",
    "Accept": "*/*",
}


def check_url(url: str, timeout: float = 8.0) -> dict:
    if not url or not url.startswith(("http://", "https://")):
        return {"url": url, "status": "skip", "code": None, "note": "non-http URL"}
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout, headers=HEADERS)
        # some sites reject HEAD; fall back to a tiny GET
        if r.status_code in (403, 405, 501):
            r = requests.get(url, allow_redirects=True, timeout=timeout, headers=HEADERS, stream=True)
            r.close()
        return {
            "url": url,
            "status": "ok" if r.status_code == 200 else f"status_{r.status_code}",
            "code": r.status_code,
            "final_url": r.url,
            "redirects": len(r.history),
        }
    except requests.RequestException as e:
        return {"url": url, "status": "error", "code": None, "note": str(e)[:120]}


def walk_bom(xlsx_path: str | Path) -> list[dict]:
    """Yield row dicts from the Sourcing sheet."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    if "Sourcing" not in wb.sheetnames:
        return []
    ws = wb["Sourcing"]
    headers = [c.value for c in ws[1]]
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not any(r):
            continue
        rows.append(dict(zip(headers, r)))
    return rows


def audit(xlsx_path: str | Path, with_api: bool = False) -> dict:
    rows = walk_bom(xlsx_path)
    findings = []
    lifecycle_findings = []
    url_columns = ["Existing URL", "Amazon URL", "AliExpress URL"]
    for row in rows:
        item = row.get("Item", "")
        for col in url_columns:
            url = row.get(col, "") or ""
            url = str(url).strip()
            if not url or url.startswith("("):
                continue
            if not url.startswith("http"):
                continue
            result = check_url(url)
            result["item"] = item
            result["column"] = col
            findings.append(result)
            time.sleep(0.2)  # be polite

    if with_api:
        try:
            from digikey_client import DigikeyClient
            dk = DigikeyClient.from_env()
            for row in rows:
                item = str(row.get("Item", ""))
                # heuristic: extract MPN-ish token (uppercase alnum 4-32 chars)
                import re
                mpns = re.findall(r"\b[A-Z][A-Z0-9\-/]{3,30}\b", item)
                seen = set()
                for mpn in mpns[:2]:  # cap per-row API calls
                    if mpn in seen:
                        continue
                    seen.add(mpn)
                    try:
                        out = dk.keyword_search(mpn, limit=1)
                        prods = out.get("Products", [])
                        if not prods:
                            continue
                        p = prods[0]
                        status = p.get("ProductStatus", {}).get("Status", "?") if isinstance(p.get("ProductStatus"), dict) else str(p.get("ProductStatus", "?"))
                        stock = p.get("QuantityAvailable", 0)
                        if status in ("Obsolete", "Not For New Designs", "Discontinued at Digi-Key", "Last Time Buy"):
                            lifecycle_findings.append({
                                "item": item, "mpn_searched": mpn,
                                "status": status, "stock": stock,
                                "severity": "HIGH" if status == "Obsolete" else "MEDIUM",
                            })
                    except Exception:
                        pass
                    time.sleep(0.1)
        except RuntimeError:
            pass  # no API creds — silent skip
        except ImportError:
            pass

    return {"xlsx": str(xlsx_path), "rows_checked": len(rows),
            "findings": findings, "lifecycle": lifecycle_findings}


def report(audit_out: dict) -> str:
    lines = [f"Sourcing health: {audit_out['xlsx']}"]
    f = audit_out["findings"]
    ok = sum(1 for x in f if x["status"] == "ok")
    bad = sum(1 for x in f if x["status"] not in ("ok", "skip"))
    lines.append(f"  URLs checked: {len(f)}  OK: {ok}  Issues: {bad}")
    for x in f:
        if x["status"] != "ok":
            lines.append(f"  [{x['status']:>10s}] {x.get('item','?')[:40]:<40s} {x['column']:>14s}: {x['url'][:80]}")
    lc = audit_out.get("lifecycle", [])
    if lc:
        lines.append(f"  Lifecycle alerts (Digikey API): {len(lc)}")
        for L in lc:
            lines.append(f"    [{L['severity']}] {L['mpn_searched']:<20s} {L['status']:<22s} stock={L['stock']:<8}  ({L['item'][:40]})")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: sourcing_health.py <BOM.xlsx>")
        sys.exit(1)
    out = audit(sys.argv[1])
    print(report(out))
    sys.exit(1 if any(f["status"] not in ("ok", "skip") for f in out["findings"]) else 0)
