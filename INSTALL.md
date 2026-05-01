# Electronics Stack — Install Status

Host: Linux Ubuntu 24.04, Python 3.12.3, KiCad 9.0.8 (PPA).
Last updated: 2026-04-30.

## Tool Status

- **KiBot** 1.8.5: installed (pip --user, reinstalled with `--no-compile` to fix macros plugin loader) — verify: `kibot --version`
- **KiAuto** 2.3.7: installed (pip --user) — verify: `python3 -c "import kiauto"` (no `__version__` attr; package present)
- **KiBot apt deps**: installed — `xvfb`, `imagemagick` 6.9.12, `poppler-utils` 24.02.0, `ghostscript` 10.02.1, `pandoc` 3.1.3
- **InteractiveHtmlBom** 2.11.1: installed (pip --user, CLI: `generate_interactive_bom`) — verify: `xvfb-run generate_interactive_bom --help` (needs DISPLAY, use xvfb-run)
- **Kiri**: cloned at `~/electronics-stack/tools/kiri` — SKIPPED auto-install. `install_dependencies.sh` installs apt+opam+kicad-via-apt and could conflict with the PPA KiCad. Manual install steps:
  ```
  sudo apt-get install -y build-essential libgtk-3-dev libgmp-dev pkg-config opam zenity librsvg2-bin imagemagick xdotool rename
  bash -c "INSTALL_KIRI_REMOTELLY=1; $(curl -fsSL https://raw.githubusercontent.com/leoheck/kiri/main/install_kiri.sh)"
  # Add to ~/.bashrc:
  #   eval $(opam env)
  #   export KIRI_HOME=$HOME/.local/share/kiri
  #   export PATH=$KIRI_HOME/submodules/KiCad-Diff/bin:$KIRI_HOME/bin:$PATH
  ```
  Skip reason: opam install pulls a multi-hundred-MB OCaml toolchain; user should opt in.
- **kicad-happy**: NOT auto-installable from sub-agent. Run inside Claude Code session: `/plugin marketplace add aklofas/kicad-happy`
- **Docling** 2.92.0: installed (pip --user, ~500MB IBM models will download on first use) — verify: `docling --version`
- **Ki-nTree** 1.2.1: installed via clone at `~/electronics-stack/tools/Ki-nTree` (PyPI publishes only Python 3.9–3.11 wheels; we ran `pip install .` from source which works on 3.12) — verify: `kintree --help` (DB server required for actual use)
- **PySpice** 1.5: installed (pip --user) — verify: `python3 -c "import PySpice; print(PySpice.__version__)"`
- **ngspice**: pre-installed (apt) — verify: `ngspice --version`
- **ERCheck**: SKIPPED — does not exist as a public project. KiCad's built-in ERC + KiBot's `erc` preflight (uses `kicad-cli sch erc`) covers this.
- **Nexar Design Render Demo** (`NexarDeveloper/nexar-design-render-demo`): cloned at `tools/nexar-design-render-demo` — `.NET 6 / WinForms / OpenTK`, **Windows-only**, NOT runnable on Linux (`dotnet` not installed; `net6.0-windows` target). The reusable bits — GraphQL queries (`Nexar.Client/Resources/Queries.graphql`) and the OAuth flow against `identity.nexar.com` — were ported into `scripts/nexar_render.py` (Python 3, headless CLI, talks straight to `api.nexar.com/graphql`). The full demo lives on disk only as a reference for the schema and the line-inflation/tessellation algorithms, in case 2D primitive rendering is ever wanted.

### Nexar Design API setup

`scripts/nexar_render.py` uses the same `NEXAR_CLIENT_ID` / `NEXAR_CLIENT_SECRET`
as `octopart_client.py`, but requires a **different OAuth scope**:

  - `octopart_client.py` -> scope `supply.domain` (Digikey/Mouser/Octopart parts)
  - `nexar_render.py`    -> scope `design.domain` (Altium 365 PCB primitives + 3D mesh)

If the existing Nexar app at portal.nexar.com only has Supply, you must:

1. Sign in to https://portal.nexar.com
2. Open your app's **Permissions** tab
3. Add the `design.domain` scope and accept the developer agreement
4. (No code change — the token cache will refresh on next call)

The two clients keep separate token files
(`~/.cache/electronics-stack/octopart/token.json` vs
`~/.cache/electronics-stack/nexar_design/token.json`) so the same app can hold
both scopes simultaneously.

**Nexar Design API caveat:** the API operates on **Altium 365 cloud workspaces**
exclusively. KiCad project uploads are not accepted. For pure-KiCad rendering,
use `kicad-cli pcb export step|glb` instead — that path is independent of Nexar.

Verify (will cleanly error if creds/scope are missing):
```
python3 ~/electronics-stack/scripts/nexar_render.py workspaces
```

## KiBot Smoke Test

Config: `~/electronics-stack/kibot/sample.kibot.yaml` (schematic-only safe; uses kicad-cli-driven outputs).

Stock KiCad demo (`/usr/share/doc/ngspice/examples/osdi/hicuml0/KiCad`):
```
cd /tmp/kicad-demo
kibot -c ~/electronics-stack/kibot/sample.kibot.yaml --skip-pre erc -d /tmp/kibot-test
```
Result: PASS — produced `docs/ECL-OR-schematic.pdf` (70 KB) + `docs/ECL-OR-schematic.svg` (247 KB).

User's `Phone_Project`:
```
cd /home/reidsurmeier/KiCad/projects/Phone_Project
kibot -c ~/electronics-stack/kibot/sample.kibot.yaml -e Phone_Project.kicad_sch --skip-pre erc -d /tmp/kibot-test
```
Result: FAIL with `Missing argument 2 in 'pin name'`. KiBot's strict internal SCH parser rejects KiCad 9 multi-line pin syntax `(name "X") (number "Y")` without `(effects ...)` child elements (used in custom symbols `Phone_Project.kicad_sym`, `RASPBERRY_PI_ZERO_2_W.kicad_sym`, etc.). This is a kibot parser limitation, not an install issue. Workaround: rewrite custom symbols with full `(name "X" (effects (font (size 1.27 1.27))))` form, or upstream-report.

## Notes / Action Items

- KiCad 9 PPA install is missing `/usr/share/kicad/symbols/` and a default system `sym-lib-table` — kibot/kiauto warn at runtime but workarounds via `KICAD9_SYMBOL_DIR` env var or manual table creation. Look into `kicad-symbols` apt package if needed.
- For real ERC on user projects, run `kicad-cli sch erc Phone_Project.kicad_sch -o erc.json` directly — bypasses kibot's strict parser entirely.
- Plugin install (`/plugin marketplace add aklofas/kicad-happy`) is user-action.
- IBOM CLI requires X (`xvfb-run generate_interactive_bom ...`).

## Tooling Layout

```
~/electronics-stack/
  INSTALL.md                  # this file
  kibot/sample.kibot.yaml     # smoke-test config
  tools/
    kiri/                     # cloned, NOT installed (manual opam toolchain needed)
    Ki-nTree/                 # cloned, installed via `pip install .`
    InteractiveHtmlBom/       # not cloned, pip-installed system-wide
```
