#!/bin/bash
# Idempotent shallow-clone of corpus from manifest.csv.
# Use --depth=1 + --filter=blob:limit=10m to skip large vendor blobs.

set -u
cd "$(dirname "$0")"
MANIFEST="manifest.csv"
LOG="download.log"

export GIT_TERMINAL_PROMPT=0

if [ ! -f "$MANIFEST" ]; then
  echo "manifest.csv not found"
  exit 1
fi

: > "$LOG"
total=0
ok=0
skipped=0
failed=0

# Skip header
while IFS=, read -r category name github_url kicad_version kicad_pro_path sch_count has_pcb license notes; do
  [ "$category" = "category" ] && continue
  [ -z "$category" ] && continue
  total=$((total+1))

  target_dir="$category/$name"
  if [ -d "$target_dir/.git" ]; then
    echo "[$(date -u +%FT%TZ)] SKIP existing $target_dir" | tee -a "$LOG"
    skipped=$((skipped+1))
    ok=$((ok+1))
    continue
  fi
  mkdir -p "$category"

  echo "[$(date -u +%FT%TZ)] CLONE $github_url -> $target_dir" | tee -a "$LOG"
  if git clone --depth=1 --filter=blob:limit=10m --no-tags --single-branch \
       "$github_url" "$target_dir" >>"$LOG" 2>&1; then
    ok=$((ok+1))
  else
    echo "[$(date -u +%FT%TZ)] FAIL $github_url" | tee -a "$LOG"
    failed=$((failed+1))
    # Cleanup partial clone
    [ -d "$target_dir" ] && rm -rf "$target_dir"
  fi

  # Polite sleep if no GITHUB_TOKEN (rate-limit kindness)
  if [ -z "${GITHUB_TOKEN:-}" ]; then
    sleep 1
  fi
done < "$MANIFEST"

echo "" | tee -a "$LOG"
echo "=== SUMMARY ===" | tee -a "$LOG"
echo "Total in manifest: $total" | tee -a "$LOG"
echo "OK (cloned or already present): $ok" | tee -a "$LOG"
echo "Already present (skipped): $skipped" | tee -a "$LOG"
echo "Failed: $failed" | tee -a "$LOG"
