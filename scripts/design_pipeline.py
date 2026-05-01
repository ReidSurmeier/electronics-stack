"""design_pipeline.py — end-to-end PCB design from a plain-English spec.

Parses a spec string → picks parts → generates skidl schematic → runs ERC →
writes parts.json, schematic.kicad_sch, bom.xlsx, verify_report.json.

Known limitations documented in docs/known-limitations.md when skidl
crashes on KiCad 9 symbol resolution.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path

import openpyxl

# Silence KICAD dir warnings before any skidl import
warnings.filterwarnings("ignore", message=".*KICAD.*SYMBOL.*DIR.*")
os.environ.setdefault("KICAD9_SYMBOL_DIR", "/usr/share/kicad/symbols")

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PartRequest:
    category: str          # resistor | capacitor | led | transistor | ic | connector | crystal
    value: str             # "10k", "100nF", "NE555", "red 5mm"
    footprint_hint: str    # "0402", "THT", "SOT-23", ""
    qty: int = 1
    refdes: str = ""       # filled in by pipeline
    mpn: str = ""          # resolved MPN
    datasheet_url: str = ""
    price_usd: float = 0.0
    stock: int = 0
    provider: str = ""


@dataclass
class Part:
    refdes: str
    category: str
    value: str
    footprint_hint: str
    mpn: str
    datasheet_url: str
    price_usd: float
    stock: int
    provider: str


# ---------------------------------------------------------------------------
# Spec parser
# ---------------------------------------------------------------------------

# Resistor: must have explicit Ω, ohm, or k/K/M/m suffix (not bare integers)
_RES_PAT = re.compile(
    r'\b(\d+(?:\.\d+)?)\s*'
    r'(k|K|M|m|kΩ|KΩ|MΩ|mΩ|Ω|ohm|ohms)'
    r'(?:\s+resistor)?\b',
    re.IGNORECASE,
)
# Capacitor: number + pF/nF/uF/µF/μF
_CAP_PAT = re.compile(
    r'\b(\d+(?:\.\d+)?)\s*(p|n|u|µ|μ)F\b',
    re.IGNORECASE,
)
_CRYSTAL_PAT = re.compile(r'\b(\d+(?:\.\d+)?)\s*MHz\b', re.IGNORECASE)

# Known ICs: keyword → (category, value, footprint_hint, mpn)
_IC_MAP = {
    "ne555":      ("ic", "NE555",        "DIP-8",   "NE555P"),
    "555":        ("ic", "NE555",        "DIP-8",   "NE555P"),
    "esp32":      ("ic", "ESP32",        "MODULE",  "ESP32-WROOM-32"),
    "atmega328":  ("ic", "ATmega328P",   "DIP-28",  "ATMEGA328P-PU"),
    "stm32f103":  ("ic", "STM32F103",   "LQFP-48", "STM32F103C8T6"),
    "lm317":      ("ic", "LM317",        "TO-220",  "LM317T"),
    "lm7805":     ("ic", "LM7805",       "TO-220",  "LM7805CT"),
    "lm7812":     ("ic", "LM7812",       "TO-220",  "LM7812CT"),
}

# Connectors
_CONN_MAP = {
    "usb-c":        ("connector", "USB-C",        "USB_C_Receptacle", 1),
    "usb c":        ("connector", "USB-C",        "USB_C_Receptacle", 1),
    "jst":          ("connector", "JST-PH-2",     "JST_PH_2pin",      1),
    "battery clip": ("connector", "BatteryClip",  "BatClip_9V",       1),
    "9v battery":   ("connector", "BatteryClip",  "BatClip_9V",       1),
    "9v":           ("connector", "BatteryClip",  "BatClip_9V",       1),
}

_TRANSISTOR_MAP = {
    "2n3904": ("transistor", "2N3904", "TO-92", "2N3904"),
    "2n2222": ("transistor", "2N2222", "TO-92", "2N2222A"),
    "bc547":  ("transistor", "BC547",  "TO-92", "BC547B"),
}

# Implicit topology parts injected when explicit values are missing
_BLINKER_IMPLICITS = [
    PartRequest(category="resistor", value="4.7kΩ",   footprint_hint="0402", mpn=""),
    PartRequest(category="resistor", value="470kΩ",   footprint_hint="0402", mpn=""),
    PartRequest(category="capacitor", value="1UF",    footprint_hint="0402", mpn=""),
]


def _res_value(m: re.Match) -> str:
    num = m.group(1)
    raw_suffix = m.group(2)
    # normalise to just the multiplier letter + Ω
    s = raw_suffix.lower().rstrip("ω").rstrip("ohm").strip()
    letter = s[0].upper() if s else ""
    if letter in ("K", "M"):
        return f"{num}{letter}Ω"
    if letter == "M":
        return f"{num}MΩ"
    return f"{num}Ω"


def _cap_value(m: re.Match) -> str:
    num = m.group(1)
    unit = m.group(2).replace("µ", "u").replace("μ", "u")
    return f"{num}{unit.upper()}F"


def parse_spec(text: str) -> list[PartRequest]:
    """Parse plain-English circuit spec → list of PartRequests."""
    parts: list[PartRequest] = []
    lower = text.lower()
    detected_ic: str | None = None

    # ICs first (highest priority — stops "555" matching as a resistor)
    for kw, (cat, val, fp, mpn) in _IC_MAP.items():
        if kw in lower:
            parts.append(PartRequest(category=cat, value=val, footprint_hint=fp, mpn=mpn))
            detected_ic = val
            break

    # Connectors / power supply
    for kw, (cat, val, fp, qty) in _CONN_MAP.items():
        if kw in lower:
            parts.append(PartRequest(category=cat, value=val, footprint_hint=fp, qty=qty))
            break

    # Transistors
    for kw, (cat, val, fp, mpn) in _TRANSISTOR_MAP.items():
        if kw in lower:
            parts.append(PartRequest(category=cat, value=val, footprint_hint=fp, mpn=mpn))

    # LED detection
    led_match = re.search(r'(\d+mm)?\s*(red|green|blue|yellow|white|amber)?\s*led', lower)
    if led_match:
        colour = led_match.group(2) or "red"
        size = led_match.group(1) or "5mm"
        parts.append(PartRequest(
            category="led",
            value=f"{colour} {size}",
            footprint_hint="THT",
            mpn="LED_5MM_RED" if colour == "red" else "LED_5MM",
        ))
        # Current-limiting resistor for LED
        parts.append(PartRequest(category="resistor", value="470Ω", footprint_hint="0402", mpn=""))

    # Crystal
    for m in _CRYSTAL_PAT.finditer(text):
        parts.append(PartRequest(category="crystal", value=f"{m.group(1)}MHz", footprint_hint="THT"))
        parts.append(PartRequest(category="capacitor", value="22PF", footprint_hint="0402", qty=2))

    # Explicit resistors from text
    existing_res = {p.value for p in parts if p.category == "resistor"}
    for m in _RES_PAT.finditer(text):
        val = _res_value(m)
        if val not in existing_res:
            parts.append(PartRequest(category="resistor", value=val, footprint_hint="0402"))
            existing_res.add(val)

    # Explicit capacitors from text
    existing_cap = {p.value for p in parts if p.category == "capacitor"}
    for m in _CAP_PAT.finditer(text):
        val = _cap_value(m)
        if val not in existing_cap:
            parts.append(PartRequest(category="capacitor", value=val, footprint_hint="0402"))
            existing_cap.add(val)

    # Inject implicit timing parts for 555 blinker if none explicitly given
    if detected_ic == "NE555":
        has_timing_cap = any(p.category == "capacitor" for p in parts)
        has_timing_res = sum(1 for p in parts if p.category == "resistor") >= 2
        if not has_timing_cap or not has_timing_res:
            for imp in _BLINKER_IMPLICITS:
                key = (imp.category, imp.value)
                if not any((p.category, p.value) == key for p in parts):
                    from copy import copy
                    parts.append(copy(imp))

    # Assign refdes
    counters: dict[str, int] = {}
    prefix_map = {
        "resistor": "R", "capacitor": "C", "led": "D",
        "transistor": "Q", "ic": "U", "connector": "J", "crystal": "Y",
    }
    for p in parts:
        prefix = prefix_map.get(p.category, "X")
        counters[prefix] = counters.get(prefix, 0) + 1
        p.refdes = f"{prefix}{counters[prefix]}"

    return parts


# ---------------------------------------------------------------------------
# Topology picker
# ---------------------------------------------------------------------------

def pick_topology(parts: list[PartRequest]) -> str:
    values = {p.value for p in parts}
    mpns = {p.mpn for p in parts}

    if any("NE555" in v or "555" in v for v in values | mpns):
        return "555_blinker"
    if any("ESP32" in v for v in values | mpns):
        return "esp32_minimal"
    cats = {p.category for p in parts}
    if "resistor" in cats and "capacitor" not in cats and len(parts) <= 3:
        return "voltage_divider"
    return "generic_fallback"


# ---------------------------------------------------------------------------
# skidl script renderer
# ---------------------------------------------------------------------------

_SKIDL_PART_MAP = {
    "ic":         ("Device", "NE555"),
    "resistor":   ("Device", "R"),
    "capacitor":  ("Device", "C"),
    "led":        ("Device", "LED"),
    "transistor": ("Device", "Q_NPN_BCE"),
    "connector":  ("Connector", "Conn_01x02"),
    "crystal":    ("Device", "Crystal"),
}

_TOPOLOGY_COMMENT = {
    "555_blinker": (
        "# 555 astable blinker\n"
        "# VCC → R1 → pin8(VCC), pin4(RESET)\n"
        "# GND → pin1(GND)\n"
        "# R1 between VCC and pin7(DISCH)\n"
        "# R2 between pin7 and pin2/6(TRIG/THRES)\n"
        "# C1 between pin2/6 and GND\n"
        "# pin3(OUT) → R_led → LED → GND"
    ),
    "voltage_divider": "# Voltage divider: VCC → R1 → MID → R2 → GND",
    "esp32_minimal":   "# ESP32 minimal: VCC → decoupling caps → ESP32 → GND",
    "generic_fallback": "# Generic: parts laid out, VCC/GND rails only",
}


def render_skidl(parts: list[PartRequest], topology: str) -> str:
    """Render a skidl Python script string for the given parts + topology."""
    lines = [
        "import warnings, os",
        "warnings.filterwarnings('ignore', message='.*KICAD.*SYMBOL.*DIR.*')",
        "os.environ.setdefault('KICAD9_SYMBOL_DIR', '/usr/share/kicad/symbols')",
        "from skidl.logger import SkidlLogger as _SL",
        "import logging; logging.setLoggerClass(_SL)",
        "import skidl",
        "skidl.reset()",
        "",
        _TOPOLOGY_COMMENT.get(topology, ""),
        "",
        "vcc = skidl.Net('VCC')",
        "gnd = skidl.Net('GND')",
        "",
    ]

    for p in parts:
        lib, sym = _SKIDL_PART_MAP.get(p.category, ("Device", "R"))
        if p.category == "ic" and "NE555" in (p.mpn or p.value):
            lib, sym = "Timer", "NE555"
        lines += [
            f"# {p.refdes}: {p.category} {p.value}",
            f"_{p.refdes}_tmpl = skidl.Part({lib!r}, {sym!r}, dest=skidl.TEMPLATE)",
            f"{p.refdes} = _{p.refdes}_tmpl()",
            f"{p.refdes}.ref = {p.refdes!r}",
            f"{p.refdes}.value = {p.value!r}",
            "",
        ]

    lines += [
        f"skidl.generate_schematic(file_=OUT_PATH)",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Part lookup (provider-agnostic, cache-friendly)
# ---------------------------------------------------------------------------

def _lookup_part_providers(mpn: str, providers: list[str], cache_dir: Path) -> dict:
    """Try each provider in order; return first hit with stock > 0."""
    cache_file = cache_dir / f"part_{re.sub(r'[^a-zA-Z0-9]', '_', mpn)}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass

    result: dict = {}
    for prov in providers:
        try:
            if prov == "lcsc":
                from lcsc_client import LcscClient
                hits = LcscClient.from_env().keyword_search(mpn, limit=3)
                if hits:
                    h = hits[0]
                    result = {
                        "mpn": h.get("mpn", mpn),
                        "provider": "lcsc",
                        "stock": h.get("stock", 0),
                        "price_usd": (h.get("price_tiers") or [{}])[0].get("price_usd", 0.0),
                        "datasheet_url": h.get("datasheet_url", ""),
                    }
            elif prov == "digikey":
                from digikey_client import DigikeyClient
                r = DigikeyClient.from_env().keyword_search(mpn, limit=3)
                products = r.get("Products") or r.get("products") or []
                if products:
                    p0 = products[0]
                    result = {
                        "mpn": p0.get("ManufacturerPartNumber", mpn),
                        "provider": "digikey",
                        "stock": p0.get("QuantityAvailable", 0),
                        "price_usd": float((p0.get("UnitPrice") or "0").replace(",", "") or 0),
                        "datasheet_url": p0.get("PrimaryDatasheet", ""),
                    }
            elif prov == "mouser":
                from mouser_client import MouserClient
                r = MouserClient.from_env().keyword_search(mpn, records=3)
                parts = (r.get("SearchResults") or {}).get("Parts") or []
                if parts:
                    p0 = parts[0]
                    result = {
                        "mpn": p0.get("ManufacturerPartNumber", mpn),
                        "provider": "mouser",
                        "stock": int(p0.get("Availability", "0").split()[0] or 0),
                        "price_usd": float(
                            (p0.get("PriceBreaks") or [{}])[0].get("Price", "0")
                            .replace("$", "") or 0
                        ),
                        "datasheet_url": p0.get("DataSheetUrl", ""),
                    }
        except Exception:
            continue
        if result.get("stock", 0) > 0:
            break

    if result:
        try:
            cache_file.write_text(json.dumps(result))
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# ERC runner
# ---------------------------------------------------------------------------

def _run_erc(schematic_path: Path) -> dict:
    rpt = schematic_path.with_suffix(".erc.rpt")
    try:
        r = subprocess.run(
            ["kicad-cli", "sch", "erc", "--severity-error", "--severity-warning",
             "-o", str(rpt), str(schematic_path)],
            capture_output=True, text=True, timeout=120,
        )
        text = rpt.read_text() if rpt.exists() else ""
        return {
            "rc": r.returncode,
            "errors": text.count("; error"),
            "warnings": text.count("; warning"),
            "report_path": str(rpt),
            "excerpt": text[:2000],
        }
    except FileNotFoundError:
        return {"rc": -1, "errors": 0, "warnings": 0, "note": "kicad-cli not found"}
    except subprocess.TimeoutExpired:
        return {"rc": -2, "errors": 0, "warnings": 0, "note": "ERC timed out"}


# ---------------------------------------------------------------------------
# BOM writer
# ---------------------------------------------------------------------------

def _write_bom(parts: list[PartRequest], out_path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOM"
    ws.append(["RefDes", "Category", "Value", "MPN", "Provider", "Stock", "Price USD", "Datasheet"])
    for p in parts:
        ws.append([p.refdes, p.category, p.value, p.mpn, p.provider,
                   p.stock, p.price_usd, p.datasheet_url])
    wb.save(str(out_path))


# ---------------------------------------------------------------------------
# Stub schematic writer (fallback when skidl fails)
# ---------------------------------------------------------------------------

_STUB_SCH_HEADER = """\
(kicad_sch (version 20231012) (generator design_pipeline_stub)
  ;; STUB: skidl schematic generation failed on this system.
"""


def _write_stub_schematic(parts: list[PartRequest], path: Path, reason: str) -> None:
    lines = [_STUB_SCH_HEADER, f"  ;; Failure reason: {reason}\n"]
    for p in parts:
        lines.append(f"  ;; {p.refdes}  {p.category}  {p.value}  {p.mpn}\n")
    lines.append(")\n")
    path.write_text("".join(lines))


def _record_known_limitation(reason: str) -> None:
    docs = Path(__file__).resolve().parent.parent / "docs"
    docs.mkdir(exist_ok=True)
    lim_file = docs / "known-limitations.md"
    existing = lim_file.read_text() if lim_file.exists() else "# Known Limitations\n\n"
    entry = f"- **skidl KiCad 9 symbol resolution**: {reason}\n"
    if entry not in existing:
        lim_file.write_text(existing + entry)


# ---------------------------------------------------------------------------
# skidl execution (subprocess with timeout — prevents hangs)
# ---------------------------------------------------------------------------

def _exec_skidl(skidl_src: str, sch_path: Path, timeout: int = 60) -> tuple[bool, str]:
    """Write skidl script to a temp file and run it in a subprocess.

    Returns (success, error_message).
    Using subprocess isolates skidl's global state and prevents hangs.
    """
    src = f'OUT_PATH = {str(sch_path)!r}\n' + skidl_src.replace(
        "file_=OUT_PATH", f"file_={str(sch_path)!r}"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(src)
        tmp_path = f.name
    try:
        r = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "KICAD9_SYMBOL_DIR": "/usr/share/kicad/symbols"},
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "skidl exited non-zero").strip()
            return False, err
        if not sch_path.exists():
            return False, "skidl ran but produced no .kicad_sch file"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"skidl timed out after {timeout}s"
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main pipeline class
# ---------------------------------------------------------------------------

class DesignPipeline:
    def __init__(
        self,
        providers: list[str] | None = None,
        cache_dir: Path | None = None,
    ):
        self.providers = providers or ["digikey", "lcsc"]
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "electronics-stack" / "design")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def design(self, spec: str, out_dir: Path) -> dict:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        known_limitations: list[str] = []

        # 1. Parse spec
        requests = parse_spec(spec)
        if not requests:
            return {
                "success": False,
                "out_dir": str(out_dir),
                "parts_count": 0,
                "erc_errors": 0,
                "known_limitations": ["No parts could be parsed from spec"],
            }

        # 2. Lookup parts
        for req in requests:
            if req.mpn:
                hit = _lookup_part_providers(req.mpn, self.providers, self.cache_dir)
                req.datasheet_url = hit.get("datasheet_url", "")
                req.price_usd = hit.get("price_usd", 0.0)
                req.stock = hit.get("stock", 0)
                req.provider = hit.get("provider", "")

        # 3. Write parts.json
        parts_json = out_dir / "parts.json"
        parts_json.write_text(json.dumps([asdict(r) for r in requests], indent=2))

        # 4. Pick topology + render skidl
        topology = pick_topology(requests)
        skidl_src = render_skidl(requests, topology)
        skidl_file = out_dir / "circuit.skidl.py"
        skidl_file.write_text(skidl_src)

        # 5. Execute skidl (subprocess, timeout-protected)
        sch_path = out_dir / "schematic.kicad_sch"
        skidl_success, skidl_error = _exec_skidl(skidl_src, sch_path)

        if not skidl_success:
            known_limitations.append(f"skidl schematic generation failed: {skidl_error}")
            _record_known_limitation(skidl_error)
            _write_stub_schematic(requests, sch_path, skidl_error)

        # 6. Run ERC on whatever schematic exists
        erc_result: dict = {"errors": 0, "warnings": 0}
        if sch_path.exists():
            erc_result = _run_erc(sch_path)

        # 7. Write BOM
        bom_path = out_dir / "bom.xlsx"
        _write_bom(requests, bom_path)

        # 8. Write verify_report.json
        report = {
            "spec": spec,
            "topology": topology,
            "parts_count": len(requests),
            "skidl_success": skidl_success,
            "skidl_error": skidl_error,
            "erc": erc_result,
            "files": {
                "parts_json": str(parts_json),
                "schematic": str(sch_path),
                "bom": str(bom_path),
                "skidl_src": str(skidl_file),
            },
            "known_limitations": known_limitations,
        }
        (out_dir / "verify_report.json").write_text(json.dumps(report, indent=2))

        return {
            "success": skidl_success,
            "out_dir": str(out_dir),
            "parts_count": len(requests),
            "erc_errors": erc_result.get("errors", 0),
            "known_limitations": known_limitations,
        }
