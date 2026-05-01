"""Run verify.py on every KiCad project in a corpus directory and aggregate results.

Usage:
    run_corpus.py <corpus_dir> [--out <results_dir>] [--checks erc,conn]

Walks <corpus_dir> recursively, finds every .kicad_pro (skipping macOS ._
prefix files), runs verify.py against each project's directory, and writes:
    <results_dir>/per_project.jsonl  — one JSON line per project
    <results_dir>/summary.md         — pass/fail counts + categorized failures
    <results_dir>/raw_logs/<name>.log — raw verify output
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
VERIFY = SCRIPTS / "verify.py"


def find_kicad_projects(root: Path) -> list[Path]:
    pros = []
    for p in root.rglob("*.kicad_pro"):
        if p.name.startswith("._"):
            continue
        pros.append(p)
    return sorted(pros)


def run_verify(project_dir: Path, checks: list[str], log_path: Path) -> dict:
    args = ["python3", str(VERIFY), str(project_dir), "--json"]
    for c in checks:
        args.append(f"--{c}")
    t0 = time.time()
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        log_path.write_text("TIMEOUT")
        return {"project": str(project_dir), "rc": -1, "elapsed": 180, "error": "timeout", "checks": []}
    elapsed = time.time() - t0
    log_path.write_text(f"# rc={r.returncode}\n# stderr:\n{r.stderr}\n# stdout:\n{r.stdout}\n")
    try:
        checks_out = json.loads(r.stdout) if r.stdout.strip() else []
    except json.JSONDecodeError:
        checks_out = []
    return {"project": str(project_dir), "rc": r.returncode, "elapsed": round(elapsed, 1),
            "checks": checks_out}


def aggregate(results: list[dict]) -> dict:
    total = len(results)
    passes = sum(1 for r in results if r["rc"] == 0)
    fails = sum(1 for r in results if r["rc"] == 1)
    errors = sum(1 for r in results if r["rc"] not in (0, 1))
    check_status: dict[str, Counter] = defaultdict(Counter)
    failure_modes: Counter = Counter()
    for r in results:
        for c in r.get("checks", []):
            check_status[c.get("check", "?")][c.get("status", "?")] += 1
            if c.get("status") == "fail":
                # categorize fail
                if c.get("errors_design", 0) > 0:
                    failure_modes["erc_design_errors"] += 1
                if c.get("high", 0) > 0:
                    failure_modes["connectivity_high"] += 1
            if c.get("status") == "error":
                failure_modes[c.get("error", "unknown")[:80]] += 1
    return {
        "total": total, "pass": passes, "fail": fails, "error": errors,
        "check_status": {k: dict(v) for k, v in check_status.items()},
        "failure_modes": failure_modes.most_common(20),
    }


def write_summary(agg: dict, out_dir: Path):
    md = []
    md.append(f"# Corpus verification summary\n")
    md.append(f"- Total projects: **{agg['total']}**")
    md.append(f"- Pass: {agg['pass']}  ({agg['pass']/agg['total']:.0%})" if agg['total'] else "- Pass: 0")
    md.append(f"- Fail: {agg['fail']}")
    md.append(f"- Error (timeout/crash): {agg['error']}\n")
    md.append("## Per-check status\n")
    for check, counts in agg["check_status"].items():
        md.append(f"### {check}\n")
        for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            md.append(f"- {status}: {n}")
        md.append("")
    md.append("## Top failure modes\n")
    for mode, n in agg["failure_modes"][:20]:
        md.append(f"- ({n}) {mode}")
    (out_dir / "summary.md").write_text("\n".join(md))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--checks", default="erc,conn")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    corpus_dir = Path(args.corpus_dir).resolve()
    out_dir = Path(args.out or (corpus_dir.parent / "corpus-results")).resolve()
    raw_dir = out_dir / "raw_logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    checks = [c.strip() for c in args.checks.split(",") if c.strip()]

    pros = find_kicad_projects(corpus_dir)
    if args.limit:
        pros = pros[: args.limit]
    print(f"[corpus] found {len(pros)} kicad_pro under {corpus_dir}")

    jsonl_path = out_dir / "per_project.jsonl"
    with open(jsonl_path, "w") as jf:
        for i, pro in enumerate(pros):
            project_dir = pro.parent
            log = raw_dir / f"{i:04d}_{pro.parent.name}.log"
            r = run_verify(project_dir, checks, log)
            jf.write(json.dumps(r) + "\n")
            jf.flush()
            status = "PASS" if r["rc"] == 0 else ("FAIL" if r["rc"] == 1 else "ERR")
            print(f"  [{i+1:>4}/{len(pros)}] [{status}] {project_dir.name}  ({r['elapsed']}s)")

    results = [json.loads(l) for l in jsonl_path.read_text().splitlines() if l.strip()]
    agg = aggregate(results)
    (out_dir / "aggregate.json").write_text(json.dumps(agg, indent=2))
    write_summary(agg, out_dir)
    print(f"[corpus] summary: {out_dir / 'summary.md'}")
    print(f"[corpus] PASS={agg['pass']}/{agg['total']}, FAIL={agg['fail']}, ERR={agg['error']}")


if __name__ == "__main__":
    main()
