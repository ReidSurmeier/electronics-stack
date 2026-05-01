"""KiCad 7/9 schematic + symbol s-expression parser.
Lightweight, no external KiCad python API required."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
import sexpdata


def load(path: str | Path):
    with open(path, "rb") as f:
        raw = f.read()
    # KiCad files are nominally UTF-8 but vendor symbols sometimes embed latin-1
    # (degree signs in pin names, etc.). Be permissive.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return sexpdata.loads(text)


def sym_name(item) -> str:
    if isinstance(item, sexpdata.Symbol):
        return item.value()
    return str(item)


def find_all(node, name: str) -> Iterator[list]:
    """Yield all child s-expressions whose head symbol == name."""
    if not isinstance(node, list):
        return
    for child in node:
        if isinstance(child, list) and child and sym_name(child[0]) == name:
            yield child
        if isinstance(child, list):
            yield from find_all(child, name)


def get_value(node, key: str, default=None):
    """Return the first child arg of a (key value) sub-expr."""
    for child in node:
        if isinstance(child, list) and child and sym_name(child[0]) == key:
            return child[1] if len(child) > 1 else default
    return default


def get_property(symbol_inst, prop_name: str, default=None):
    """Walk a (symbol ...) instance and return the value of (property "Name" "Value" ...)."""
    for child in symbol_inst:
        if isinstance(child, list) and child and sym_name(child[0]) == "property":
            if len(child) >= 3 and child[1] == prop_name:
                return child[2]
    return default


@dataclass
class Pin:
    number: str
    name: str
    etype: str  # power_in, power_out, input, output, bidirectional, passive, ...
    at: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class SymbolDef:
    name: str
    pins: list[Pin] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass
class SymbolInstance:
    refdes: str
    lib_id: str
    value: str = ""
    properties: dict = field(default_factory=dict)
    at: tuple[float, float] = (0.0, 0.0)
    uuid: str = ""


@dataclass
class Net:
    name: str
    label_positions: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Schematic:
    path: Path
    symbol_defs: dict[str, SymbolDef] = field(default_factory=dict)
    instances: list[SymbolInstance] = field(default_factory=list)
    labels: list[tuple[str, float, float]] = field(default_factory=list)
    wires: list[list[tuple[float, float]]] = field(default_factory=list)
    no_connects: list[tuple[float, float]] = field(default_factory=list)
    title: str = ""
    rev: str = ""


def parse_pin(node) -> Pin:
    """Pin syntax: (pin <etype> <shape> (at x y rot) (length L) (name "..." ...) (number "..." ...))"""
    etype = sym_name(node[1]) if len(node) > 1 else "passive"
    at_node = next((c for c in node if isinstance(c, list) and c and sym_name(c[0]) == "at"), None)
    if at_node:
        at = (float(at_node[1]), float(at_node[2]), float(at_node[3]) if len(at_node) > 3 else 0.0)
    else:
        at = (0.0, 0.0, 0.0)
    name_node = next((c for c in node if isinstance(c, list) and c and sym_name(c[0]) == "name"), None)
    number_node = next((c for c in node if isinstance(c, list) and c and sym_name(c[0]) == "number"), None)
    name = name_node[1] if name_node else ""
    number = str(number_node[1]) if number_node else ""
    return Pin(number=number, name=name, etype=etype, at=at)


def parse_schematic(path: str | Path) -> Schematic:
    path = Path(path)
    root = load(path)
    sch = Schematic(path=path)

    # --- title block
    title_block = next(find_all(root, "title_block"), None)
    if title_block:
        sch.title = get_value(title_block, "title", "")
        sch.rev = get_value(title_block, "rev", "")

    # --- symbol library defs (lib_symbols)
    lib_symbols = next((c for c in root if isinstance(c, list) and c and sym_name(c[0]) == "lib_symbols"), None)
    if lib_symbols:
        for symdef in lib_symbols[1:]:
            if not (isinstance(symdef, list) and symdef and sym_name(symdef[0]) == "symbol"):
                continue
            name = symdef[1] if len(symdef) > 1 else ""
            sd = SymbolDef(name=name)
            # pin can be inside nested (symbol "<name>_1_1" ...)
            for pin_node in find_all(symdef, "pin"):
                try:
                    sd.pins.append(parse_pin(pin_node))
                except Exception:
                    pass
            sch.symbol_defs[name] = sd

    # --- top-level symbol instances
    for inst in root[1:]:
        if not (isinstance(inst, list) and inst and sym_name(inst[0]) == "symbol"):
            continue
        # skip the lib_symbols container (already handled)
        if len(inst) > 1 and inst[1] == "":
            pass
        lib_id = get_value(inst, "lib_id", "")
        at_node = next((c for c in inst if isinstance(c, list) and c and sym_name(c[0]) == "at"), None)
        at = (float(at_node[1]), float(at_node[2])) if at_node else (0.0, 0.0)
        si = SymbolInstance(refdes="", lib_id=str(lib_id), at=at)
        # gather properties
        for child in inst:
            if isinstance(child, list) and child and sym_name(child[0]) == "property":
                if len(child) >= 3:
                    si.properties[child[1]] = child[2]
                    if child[1] == "Reference":
                        si.refdes = child[2]
                    elif child[1] == "Value":
                        si.value = child[2]
        if si.refdes:
            sch.instances.append(si)

    # --- labels (local + global + hierarchical)
    for kind in ("label", "global_label", "hierarchical_label"):
        for lab in find_all(root, kind):
            if len(lab) > 1:
                name = lab[1]
                at_node = next((c for c in lab if isinstance(c, list) and c and sym_name(c[0]) == "at"), None)
                if at_node:
                    sch.labels.append((str(name), float(at_node[1]), float(at_node[2])))

    # --- wires
    for wire in find_all(root, "wire"):
        pts_node = next((c for c in wire if isinstance(c, list) and c and sym_name(c[0]) == "pts"), None)
        if pts_node:
            pts = []
            for xy in pts_node[1:]:
                if isinstance(xy, list) and xy and sym_name(xy[0]) == "xy":
                    pts.append((float(xy[1]), float(xy[2])))
            if pts:
                sch.wires.append(pts)

    # --- no_connects
    for nc in find_all(root, "no_connect"):
        at_node = next((c for c in nc if isinstance(c, list) and c and sym_name(c[0]) == "at"), None)
        if at_node:
            sch.no_connects.append((float(at_node[1]), float(at_node[2])))

    return sch


def get_symbol_def_for_instance(sch: Schematic, inst: SymbolInstance) -> SymbolDef | None:
    """Return the SymbolDef matching an instance's lib_id."""
    return sch.symbol_defs.get(inst.lib_id)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: sch_parser.py <schematic.kicad_sch>")
        sys.exit(1)
    s = parse_schematic(sys.argv[1])
    print(f"Schematic: {s.title} (rev {s.rev})")
    print(f"  symbol defs: {len(s.symbol_defs)}")
    print(f"  instances:   {len(s.instances)}")
    print(f"  labels:      {len(s.labels)}")
    print(f"  wires:       {len(s.wires)}")
    print(f"  no_connects: {len(s.no_connects)}")
    refs = sorted(i.refdes for i in s.instances)
    print(f"  refdes:      {refs[:20]}{' …' if len(refs) > 20 else ''}")
