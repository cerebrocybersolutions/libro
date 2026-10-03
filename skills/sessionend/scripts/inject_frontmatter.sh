#!/usr/bin/env bash
# inject_frontmatter.sh — auto-populate surface/host on session-note frontmatter
#
# Closes open loop "Sessionend auto-population of surface/host/session_id"
# from 2026-05-19-source-tag-lint-and-launcher-injection-ops.md.
#
# Behavior:
#   - Idempotent: if `surface:` already present in frontmatter, exit 0 no-op.
#   - Reads CEREBRO_WRITER_SURFACE env var; falls back to "unknown".
#   - Reads `hostname -s` for host.
#   - Inserts both before the closing `---` of the YAML frontmatter.
#   - Session ID is already in frontmatter (line 3 of every Cerebro session note);
#     not re-emitted to avoid duplication.
#
# Usage:
#   inject_frontmatter.sh <session_file_path>
#
# Exit codes:
#   0 — success (injected or already present)
#   1 — file not found or no frontmatter detected
#
# Reversibility #5: backup at <file>.bak-frontmatter before in-place edit.

set -u
FILE="${1:-}"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "[inject_frontmatter] error: file not found: $FILE" >&2
  exit 1
fi

# Confirm frontmatter present: first line must be exactly `---`
if [ "$(head -n1 "$FILE")" != "---" ]; then
  echo "[inject_frontmatter] skip: $FILE has no YAML frontmatter" >&2
  exit 1
fi

# Idempotency check — bail if surface already injected
if grep -qE "^surface:" "$FILE"; then
  echo "[inject_frontmatter] noop: surface already present in $FILE"
  exit 0
fi

SURFACE="${CEREBRO_WRITER_SURFACE:-unknown}"
HOST="$(hostname -s)"

# Find the line number of the closing `---` (second `---` in file)
CLOSE_LINE="$(awk '/^---$/{c++; if(c==2){print NR; exit}}' "$FILE")"

if [ -z "$CLOSE_LINE" ]; then
  echo "[inject_frontmatter] skip: $FILE has unclosed frontmatter" >&2
  exit 1
fi

# Backup
cp "$FILE" "${FILE}.bak-frontmatter"

# Insert before closing `---`
INSERT_LINE=$((CLOSE_LINE - 1))
TMP="$(mktemp)"
awk -v ins_line="$INSERT_LINE" -v surface="$SURFACE" -v host="$HOST" '
  NR == ins_line {
    print
    print "surface: " surface
    print "host: " host
    next
  }
  { print }
' "$FILE" > "$TMP"

mv "$TMP" "$FILE"

echo "[inject_frontmatter] injected surface=$SURFACE host=$HOST into $FILE"
exit 0
