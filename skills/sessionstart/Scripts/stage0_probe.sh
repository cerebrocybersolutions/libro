#!/usr/bin/env bash
# Stage 0 — single-shot turn-start probe.
# Replaces the v2.3 4-tool-call probe with one Bash invocation.
#
# Behavior:
#   - Finds most recent session file under master-brain/sessions/.
#   - If status==closed AND gap < SESSIONSTART_STAGE0_WINDOW (default 3600s):
#       emit 3-line probe to stdout, exit 0.
#   - Else: emit nothing, exit 0 (caller falls through to full Stage 1-5).
#
# Output format (when fires):
#   [STAGE0]
#   Previous session: <session_id> (closed <hh:mm>)
#   Open loops carried: <N> — see Q2 on demand
#   Delta since close: <commit_subject> | <commit_subject> | <commit_subject>
#
# Invocation:
#   - SessionStart hook (auto-fires every session open)
#   - sessionstart skill Stage 0 (explicit /sessionstart bypass still calls this)
#
# Reference: master-brain/skills/sessionstart/references/stage0_turn_start.md

set -u
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SESSIONS_DIR="${PROJECT_DIR}/master-brain/sessions"
WINDOW="${SESSIONSTART_STAGE0_WINDOW:-3600}"

[[ -d "$SESSIONS_DIR" ]] || exit 0

# Most recent session file by mtime, filter out non-session files (log, etc.)
LATEST=$(ls -t "$SESSIONS_DIR"/[0-9]*.md 2>/dev/null | head -1)
[[ -n "${LATEST:-}" && -f "$LATEST" ]] || exit 0

# status: closed check (frontmatter)
grep -q "^status: closed$" "$LATEST" || exit 0

# Close timestamp extraction (priority: closed_at YAML > *Closed: marker > mtime)
CLOSE_EPOCH=""
CLOSED_AT=$(grep -m1 "^closed_at:" "$LATEST" 2>/dev/null | sed -E 's/^closed_at:[[:space:]]*//')
if [[ -n "$CLOSED_AT" ]]; then
  CLOSE_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M" "${CLOSED_AT%:[0-9][0-9]}" "+%s" 2>/dev/null || \
                date -j -f "%Y-%m-%dT%H:%M:%S" "$CLOSED_AT" "+%s" 2>/dev/null || echo "")
fi
if [[ -z "$CLOSE_EPOCH" ]]; then
  CLOSED_MARK=$(grep -m1 -E "^\*?Closed:[[:space:]]*[0-9]{1,2}:[0-9]{2}" "$LATEST" 2>/dev/null | \
                sed -E 's/.*Closed:[[:space:]]*([0-9]{1,2}:[0-9]{2}).*/\1/')
  if [[ -n "$CLOSED_MARK" ]]; then
    SESSION_DATE=$(basename "$LATEST" | grep -oE "^[0-9]{4}-[0-9]{2}-[0-9]{2}")
    CLOSE_EPOCH=$(date -j -f "%Y-%m-%d %H:%M" "$SESSION_DATE $CLOSED_MARK" "+%s" 2>/dev/null || echo "")
  fi
fi
if [[ -z "$CLOSE_EPOCH" ]]; then
  CLOSE_EPOCH=$(stat -f "%m" "$LATEST" 2>/dev/null || echo "")
fi
[[ -n "$CLOSE_EPOCH" ]] || exit 0

NOW_EPOCH=$(date +%s)
GAP=$((NOW_EPOCH - CLOSE_EPOCH))
(( GAP >= 0 && GAP < WINDOW )) || exit 0

# Render fields
SESSION_ID=$(basename "$LATEST" .md)
HHMM=$(date -r "$CLOSE_EPOCH" "+%H:%M" 2>/dev/null || echo "??:??")

# Count open_loops items (YAML list under `open_loops:` until next top-level key or `---`)
N=$(awk '
  /^open_loops:[[:space:]]*$/ {in_block=1; next}
  in_block && /^[a-z_]+:/ {exit}
  in_block && /^---[[:space:]]*$/ {exit}
  in_block && /^[[:space:]]+-[[:space:]]/ {count++}
  END {print count+0}
' "$LATEST")

# Delta: top-3 commits since close, dirty-tree check
cd "$PROJECT_DIR" 2>/dev/null || exit 0
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  DELTA="working tree dirty — see git status"
else
  ISO=$(date -r "$CLOSE_EPOCH" "+%Y-%m-%dT%H:%M:%S" 2>/dev/null)
  DELTA=$(git log --oneline --since="$ISO" 2>/dev/null | head -3 | awk '{$1=""; sub(/^ /,""); print}' | paste -sd " | " -)
  [[ -n "$DELTA" ]] || DELTA="no commits since close"
fi

printf '[STAGE0]\nPrevious session: %s (closed %s)\nOpen loops carried: %s — see Q2 on demand\nDelta since close: %s\n' \
  "$SESSION_ID" "$HHMM" "$N" "$DELTA"
