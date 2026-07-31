# Electronics Stack agent guide

Electronics Stack is a local, on-demand KiCad verification and experimental
design toolchain. Start by reading `PROJECT.md`, then `CONTEXT.md`. Read the
relevant decision records under `docs/adr/` before changing behavior.

## Boundaries

- Treat source KiCad projects and downloaded corpus repositories as immutable
  inputs. Write reports and generated designs to explicit output directories.
- Verification findings are engineering evidence, not proof that hardware is
  safe, manufacturable, or production-ready.
- Keep default tests offline. Do not spend distributor quotas or download the
  corpus during tests.
- Never commit credentials, provider responses containing account data,
  local caches, generated dependencies, or host-specific absolute paths.
- Provider and external-tool failures must be explicit. Do not silently turn a
  missing dependency, blocked site, or exhausted quota into a passing result.
- Preserve the historical pipeline reports. Correct stale status in a new
  dated section or follow-up report rather than rewriting prior observations.

## Commands

Create an isolated environment before running the full suite:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[test,design]'
```

Validation:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q scripts mcp-server tests reverse-engineer
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/verify.py --help
bash -n test-corpus/download_all.sh scripts/install_pre_commit_hook.sh
```

The repository contract can run without third-party packages:

```bash
python3 -m unittest tests.test_repository_contract -v
```

## Agent skills

### Issue tracker

Issues and PRDs live in GitHub Issues for `ReidSurmeier/electronics-stack`.
See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five standard Matt Pocock triage roles. See
`docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository with `CONTEXT.md` at the root and
decisions in `docs/adr/`. See `docs/agents/domain.md`.
