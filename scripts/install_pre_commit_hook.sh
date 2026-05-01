#!/usr/bin/env bash
# Installs a pre-commit git hook in a KiCad project that runs ERC + connectivity audit
# on any committed .kicad_sch file. Aborts the commit if either check fails.
#
# Usage: cd /path/to/project && ~/electronics-stack/scripts/install_pre_commit_hook.sh

set -euo pipefail

if [ ! -d .git ]; then
    echo "Error: not a git repository (no .git/ found in $PWD)" >&2
    exit 1
fi

HOOK=.git/hooks/pre-commit

cat > "$HOOK" << 'EOF'
#!/usr/bin/env bash
# electronics-verify pre-commit hook
set -euo pipefail

VERIFY=$HOME/electronics-stack/scripts/verify.py

# Find changed .kicad_sch files in this commit
CHANGED_SCH=$(git diff --cached --name-only --diff-filter=ACM | grep '\.kicad_sch$' || true)
if [ -z "$CHANGED_SCH" ]; then
    exit 0
fi

# Run verify on each unique project containing a changed sch
PROJECTS=$(echo "$CHANGED_SCH" | xargs -n1 dirname | sort -u)
FAIL=0
for proj in $PROJECTS; do
    echo "[pre-commit] verify --erc --conn $proj"
    if ! python3 "$VERIFY" "$proj" --erc --conn; then
        FAIL=1
    fi
done
if [ "$FAIL" -ne 0 ]; then
    echo "[pre-commit] verify failed. Fix or use --no-verify to bypass." >&2
    exit 1
fi
exit 0
EOF
chmod +x "$HOOK"
echo "Installed $HOOK"
