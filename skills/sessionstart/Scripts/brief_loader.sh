#!/usr/bin/env bash
# brief_loader.sh — single-shot Stage 2 brief loader for sessionstart.
# Collapses ~10 sequential file Reads into one Bash invocation. Caller
# Reads the script's stdout instead of doing N round-trips itself.
#
# Usage:
#   brief_loader.sh [--dept <name>] [--shape <dept-work|ops-infra|mixed>]
#
# Defaults: --dept ops --shape ops-infra (the most common path)
#
# Sections emitted (always in this order, demarcated by marker lines):
#   ===DEPT_CLAUDE===           dept CLAUDE.md (full body, capped 200 lines)
#   ===LATEST_SESSION===        most recent dept session file frontmatter + open_loops
#   ===DECISIONS_PENDING===     dept decisions.md unresolved entries (last 14 days)
#   ===DASHBOARD_HEADER===      first 40 lines of master-brain/DASHBOARD.md
#   ===AWARENESS_DEPT===        awareness.md block for the dept
#   ===MEMORY_INDEX===          MEMORY.md (full — already capped by HM06)
#   ===STATE_FILES===           circuit-breakers.json + wiki.toml summary
#   ===ARCHITECTURE===          diagram tiles inventory (title + status + mtime)
#   ===FLEET_PROBE===           fleet_probe.py output (1 line)
#   ===KANBAN_PROBE===          per-board path probe (local + optional remote fleet node)
#   ===MEMORY_SIZE===           memory_size_probe.py output
#   ===SOURCE_TAG_LINT===       source-tag-lint summary (1 line)
#   ===LEDGER_STALENESS===      ledger-staleness-report.json summary (F1/F3/F6 staleness)
#   ===DASHBOARD_RENDER===      dashboard_render.py --query all (or q1)
#   ===END===
#
# Always exits 0. Missing sections still emit the marker + a SKIP line.
#
# Reference: master-brain/skills/sessionstart/references/stage2_read.md

set -u
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
DEPT="ops"
SHAPE="ops-infra"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dept)  DEPT="$2"; shift 2 ;;
    --shape) SHAPE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Resolve dept paths (ops → master-brain, else → <dept>/brain)
if [[ "$DEPT" == "ops" || "$DEPT" == "master-brain" ]]; then
  DEPT_DIR="${PROJECT_DIR}/master-brain"
  DEPT_CLAUDE="${DEPT_DIR}/CLAUDE.md"
  SESSIONS_DIR="${DEPT_DIR}/sessions"
  DECISIONS="${DEPT_DIR}/decisions/decisions.md"
  PIPELINE="${DEPT_DIR}/pipeline/current-state.md"
else
  DEPT_DIR="${PROJECT_DIR}/${DEPT}"
  DEPT_CLAUDE="${DEPT_DIR}/CLAUDE.md"
  SESSIONS_DIR="${DEPT_DIR}/brain/sessions"
  DECISIONS="${DEPT_DIR}/brain/decisions/decisions.md"
  PIPELINE="${DEPT_DIR}/brain/pipeline/current-state.md"
fi

emit_section() { printf '\n===%s===\n' "$1"; }
emit_skip()    { printf 'SKIP — %s\n' "$1"; }

# 0. Priority reads — optional operator-defined priority file block.
#    Operators can re-enable by setting PRIORITY_FILE to a path the brief loader
#    should surface first (e.g., an in-flight handoff). Kept commented for reversibility.
# emit_section "PRIORITY_READ"
# PRIORITY_FILE="${PROJECT_DIR}/<operator-handoff-path>.md"
# if [[ -f "$PRIORITY_FILE" ]]; then ... fi

# 1. Dept CLAUDE.md (cap 100 lines; full read on demand)
emit_section "DEPT_CLAUDE"
if [[ -f "$DEPT_CLAUDE" ]]; then
  head -100 "$DEPT_CLAUDE"
else
  emit_skip "${DEPT_CLAUDE} not found; fallback workspace-root CLAUDE.md"
  [[ -f "${PROJECT_DIR}/CLAUDE.md" ]] && head -100 "${PROJECT_DIR}/CLAUDE.md"
fi

# 2. Latest session frontmatter + open_loops
emit_section "LATEST_SESSION"
LATEST=$(ls -t "$SESSIONS_DIR"/[0-9]*.md 2>/dev/null | head -1)
if [[ -n "${LATEST:-}" && -f "$LATEST" ]]; then
  printf 'file: %s\n\n' "$(basename "$LATEST")"
  # Frontmatter block (between first two --- lines)
  awk '/^---$/{c++; next} c==1{print} c==2{exit}' "$LATEST"
  printf '\n--- Accomplished / Open Loops ---\n'
  awk '/^### (Accomplished|Open Loops)/{p=1} /^## /{if(p && NR>1){p=0}} p' "$LATEST" | head -25
else
  emit_skip "no session file found in $SESSIONS_DIR"
fi

# 3. Decisions pending (last 14 days, no "Resolved:" marker)
emit_section "DECISIONS_PENDING"
if [[ -f "$DECISIONS" ]]; then
  CUTOFF=$(date -v-14d +%Y-%m-%d 2>/dev/null || date -d "14 days ago" +%Y-%m-%d 2>/dev/null)
  awk -v cutoff="$CUTOFF" '
    /^## [0-9]{4}-[0-9]{2}-[0-9]{2}/ { match($0, /[0-9]{4}-[0-9]{2}-[0-9]{2}/); d=substr($0, RSTART, 10); show=(d>=cutoff) }
    show && !/^_?Resolved:/ { print }
  ' "$DECISIONS" | head -80
else
  emit_skip "$DECISIONS not found"
fi

# 4. DASHBOARD header (cap 12 lines; multi-session prose rollup violates §3 governance — full read on demand)
emit_section "DASHBOARD_HEADER"
DASH="${PROJECT_DIR}/master-brain/DASHBOARD.md"
[[ -f "$DASH" ]] && head -12 "$DASH" || emit_skip "DASHBOARD.md not found"

# 5. awareness.md dept block (lines around dept heading)
emit_section "AWARENESS_DEPT"
AWARE="${PROJECT_DIR}/master-brain/awareness.md"
if [[ -f "$AWARE" ]]; then
  awk -v dept="$DEPT" '
    BEGIN { IGNORECASE=1 }
    /^## / { in_block=0 }
    tolower($0) ~ tolower(dept) && /^## / { in_block=1 }
    in_block { print; n++; if (n>8) exit }
  ' "$AWARE"
  # Always include the "Last: <today>" digest line for the dept (top-3 only)
  grep -E "Last: [0-9]{4}-[0-9]{2}-[0-9]{2}" "$AWARE" | head -3
else
  emit_skip "awareness.md not found"
fi

# 6. MEMORY.md index — lifecycle-filtered (active + pinned only; legacy unfrontmattered = include)
#    2026-05-19 Tier-2 wire: skips entries whose target file is lifecycle:{stale,archived}.
#    Closes N3 session-to-session drift class. Reversibility #5: filter is mechanical;
#    rolling back = revert this block to `cat "$MEM"`.
emit_section "MEMORY_INDEX"
# Derive Claude Code project memory dir from current workspace path.
# CC encodes the absolute project path as `-Users-name-Path-Project` (replace / with -).
# Override with CLAUDE_PROJECT_MEM_DIR env var if your install differs.
if [[ -n "${CLAUDE_PROJECT_MEM_DIR:-}" ]]; then
  MEM_DIR="${CLAUDE_PROJECT_MEM_DIR}"
else
  _project_slug="$(printf '%s' "${PROJECT_DIR}" | tr '/' '-')"
  MEM_DIR="${HOME}/.claude/projects/${_project_slug}/memory"
fi
MEM="${MEM_DIR}/MEMORY.md"
SURFACED_IDS=""  # newline-separated paths; piped to access_log record-batch at the end
if [[ -f "$MEM" ]]; then
  printf '# [filter: lifecycle != stale|archived; default-include if no frontmatter]\n'
  filtered_skipped=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Match entry rows: `- [Title](file.md) — hook`
    if [[ "$line" =~ ^-[[:space:]]+\[.+\]\(([^\)]+\.md)\) ]]; then
      target="${MEM_DIR}/${BASH_REMATCH[1]}"
      if [[ -f "$target" ]]; then
        # Probe frontmatter (first 20 lines) for terminal lifecycle states.
        # 2026-05-21 Phase B-3a: added closed|superseded|completed to skip set.
        if head -20 "$target" | grep -qE '^lifecycle:[[:space:]]+(stale|archived|closed|superseded|completed)'; then
          filtered_skipped=$((filtered_skipped + 1))
          continue
        fi
        # Capture surfaced ID for batch access-log emit (Phase 1 LLM Curator wiring,
        # decision 2026-05-19-llm-curator-access-log-scope-lock §Component A).
        SURFACED_IDS="${SURFACED_IDS}${target}"$'\n'
      fi
    fi
    printf '%s\n' "$line"
  done < "$MEM"
  printf '\n# [filter-stats: skipped=%d]\n' "$filtered_skipped"
else
  emit_skip "MEMORY.md not found"
fi

# Fire-and-forget access-log batch emit for memory entries surfaced into the brief.
# Stderr-redirected so failures don't pollute stdout sections.
ACCESS_LOG_PY="${PROJECT_DIR}/master-brain/skills/memory-writer/scripts/access_log.py"
if [[ -f "$ACCESS_LOG_PY" && -n "$SURFACED_IDS" ]]; then
  surface_label="${LIBRO_WRITER_SURFACE:-sessionstart-$(hostname -s 2>/dev/null || echo localhost)}"
  printf '%s' "$SURFACED_IDS" | python3 "$ACCESS_LOG_PY" record-batch "$surface_label" --context "brief-loader" >/dev/null 2>&1 || true
fi

# 7. State files
emit_section "STATE_FILES"
CB="${PROJECT_DIR}/master-brain/state/circuit-breakers.json"
WIKI="${PROJECT_DIR}/master-brain/knowledge-vault/wiki.toml"
if [[ -f "$CB" ]]; then
  printf 'circuit-breakers.json:\n'
  cat "$CB"
else
  printf 'circuit-breakers.json: not present\n'
fi
if [[ -f "$WIKI" ]]; then
  printf '\nwiki.toml (model config):\n'
  grep -E "^(model|fast|heavy|auto_commit|temperature)" "$WIKI" | head -20
else
  printf '\nwiki.toml: not present\n'
fi

# 7b. Architecture snapshot — diagram tiles inventory.
#     Per Diagram-First Doctrine #14 + pinned feedback "diagrams = canonical when same-day,
#     runtime probe = drift-verification, not architecture-derivation": session-open must
#     surface the topology map BEFORE the runtime probe so the latter reads as drift-check.
#     Emits one line per tile: <filename> | <title> | mtime=YYYY-MM-DD | status=<first badge>
emit_section "ARCHITECTURE"
TILES_DIR="${PROJECT_DIR}/master-brain/diagrams/tiles"
if [[ -d "$TILES_DIR" ]]; then
  count=0
  for tile in "$TILES_DIR"/*.html; do
    [[ -f "$tile" ]] || continue
    fname="$(basename "$tile")"
    title="$(grep -oE '<title>[^<]+</title>' "$tile" | head -1 | sed -E 's|</?title>||g')"
    [[ -z "$title" ]] && title="(no title)"
    # First badge in document body — strip HTML tags, take inner text.
    status="$(grep -oE '<span class="badge badge-[a-z]+">[^<]+</span>' "$tile" | head -1 | sed -E 's|<[^>]+>||g')"
    [[ -z "$status" ]] && status="—"
    mtime="$(stat -f '%Sm' -t '%Y-%m-%d' "$tile" 2>/dev/null || stat -c '%y' "$tile" 2>/dev/null | cut -d' ' -f1)"
    printf '%s | %s | mtime=%s | status=%s\n' "$fname" "$title" "$mtime" "$status"
    count=$((count + 1))
  done
  printf '\n[tiles: %d]\n' "$count"
else
  emit_skip "diagrams/tiles/ not found"
fi

# 8. Fleet probe
emit_section "FLEET_PROBE"
FLEET="${PROJECT_DIR}/master-brain/skills/sessionstart/Scripts/fleet_probe.py"
if [[ -f "$FLEET" ]]; then
  python3 "$FLEET" 2>/dev/null || emit_skip "fleet probe timeout or error"
else
  emit_skip "fleet_probe.py not found"
fi

# 8b. Kanban per-board probe — optional integration with kanban backend if installed.
#     Real boards live at ~/.hermes/kanban/boards/<slug>/kanban.db when the kanban
#     backend is present. Operator can opt-in by exporting LIBRO_KANBAN_BOARD; a remote
#     fleet node can be probed via LIBRO_KANBAN_REMOTE (SSH-reachable host) when set.
emit_section "KANBAN_PROBE"
BOARD_NAME="${LIBRO_KANBAN_BOARD:-libro-loops}"
LOCAL_DB="${HOME}/.hermes/kanban/boards/${BOARD_NAME}/kanban.db"
if [[ -f "$LOCAL_DB" ]]; then
  LOCAL_COUNTS=$(sqlite3 "$LOCAL_DB" "SELECT status || '=' || COUNT(*) FROM tasks GROUP BY status;" 2>/dev/null | tr '\n' ' ')
  printf 'local[%s]: %s\n' "$BOARD_NAME" "${LOCAL_COUNTS:-(empty)}"
else
  printf 'local[%s]: db not found at %s\n' "$BOARD_NAME" "$LOCAL_DB"
fi
if [[ -n "${LIBRO_KANBAN_REMOTE:-}" ]]; then
  REMOTE_PROBE=$(ssh -o ConnectTimeout=3 -o BatchMode=yes "$LIBRO_KANBAN_REMOTE" "test -f ~/.hermes/kanban/boards/${BOARD_NAME}/kanban.db && sqlite3 ~/.hermes/kanban/boards/${BOARD_NAME}/kanban.db \"SELECT status || '=' || COUNT(*) FROM tasks GROUP BY status;\"" 2>/dev/null | tr '\n' ' ')
  if [[ -n "$REMOTE_PROBE" ]]; then
    printf 'remote[%s]: %s\n' "$BOARD_NAME" "$REMOTE_PROBE"
  else
    printf 'remote[%s]: probe timeout or board not present\n' "$BOARD_NAME"
  fi
fi
printf '[doctrine: per-board path only; bare kanban backend default may hit a legacy DB]\n'

# 9. MEMORY size probe
emit_section "MEMORY_SIZE"
MSP="${PROJECT_DIR}/master-brain/skills/memory-writer/scripts/memory_size_probe.py"
if [[ -f "$MSP" ]]; then
  python3 "$MSP" 2>/dev/null || emit_skip "memory size probe error"
else
  emit_skip "memory_size_probe.py not found"
fi

# 9b. Source-tag lint (memory frontmatter write-time enforcement probe)
emit_section "SOURCE_TAG_LINT"
STAG="${PROJECT_DIR}/master-brain/skills/source-tag-lint/Scripts/lint.py"
if [[ -f "$STAG" ]]; then
  python3 "$STAG" --summary 2>/dev/null || emit_skip "source-tag-lint error"
else
  emit_skip "source-tag-lint not found"
fi

# 9c. Ledger staleness (Stage 2.5 integration per
# decisions/2026-05-21-state-ledger-regeneration-cadence.md Action 3)
emit_section "LEDGER_STALENESS"
LS="${PROJECT_DIR}/master-brain/state/ledger-staleness-report.json"
if [[ -f "$LS" ]]; then
  python3 - <<'PY' "$LS" 2>/dev/null || emit_skip "ledger-staleness summary error"
import json, sys
from datetime import datetime, timezone
try:
    data = json.loads(open(sys.argv[1]).read())
except Exception as e:
    print(f"SKIP — read error: {e}")
    sys.exit(0)
worst = data.get("worst_status", "?")
checked = data.get("checked_at_utc", "?")
# Probe age — surface "STALE PROBE" if the report itself is >36h old.
report_age_h = None
try:
    dt = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    report_age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
except Exception:
    pass
age_tag = ""
if report_age_h is not None and report_age_h > 36:
    age_tag = f" · ⚠️ PROBE STALE ({report_age_h:.0f}h since last check)"
print(f"worst_status={worst} · checked={checked[:16]}{age_tag}")
# Surface per-ledger one-liners (always — count of drift flags is the signal)
for L in data.get("ledgers", []):
    print(
        f"  {L.get('code','?')} {L.get('status','?'):>5} · "
        f"age={L.get('age_days_mtime','?')}d · "
        f"open_drift={L.get('open_drift_count','?')} · "
        f"path={L.get('path','?').rsplit('/',1)[-1]}"
    )
PY
else
  emit_skip "ledger-staleness-report.json not found"
fi

# 10. Dashboard render (parity with Obsidian DataView)
emit_section "DASHBOARD_RENDER"
DR="${PROJECT_DIR}/master-brain/skills/dashboard-view/dashboard_render.py"
if [[ -f "$DR" ]]; then
  # 2026-05-21 trim: --query all emits ~216KB (Q2 = full open-loop dump back to 2026-04-12,
  # broken --days filter). Session-open uses --query q1 only; Q2/Q3/Q4 on demand.
  # Phase B: patch dashboard_render.py to honor --days on Q2.
  python3 "$DR" --query q1 2>/dev/null || emit_skip "render error"
else
  emit_skip "dashboard_render.py not found"
fi

emit_section "END"
exit 0
