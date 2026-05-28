#!/usr/bin/env bash
# Step 7.5 — Writeback Guard, single-shot wrapper.
# Collapses 5+ sequential checks into one Bash invocation. Same payoff as
# sessionstart Stage 0 collapse (199ms vs ~90s prior).
#
# Usage:
#   writeback_guard.sh <session_file_path>
#
# Output format (always to stdout, always exit 0 — never blocks close):
#   [VERIFY] frontmatter: PASS | FAIL — reason
#   [VERIFY] rollup-q1:   PASS | FAIL — reason
#   [VERIFY] awareness:   PASS | FAIL — reason
#   [DRIFT]  parity:      OK | N findings
#   [DRIFT]  halts:       OK | N HALT_TO_OPERATOR
#   [DRIFT]  skill-lint:  OK | N CRITICAL
#   [DRIFT]  source-tag:  OK | N CRITICAL / M WARN
#   [DRIFT]  auditor:     OK | N CRITICAL
#   [DRIFT]  hermes-cfg:  OK | N findings | SKIPPED
#   [DRIFT]  diagram-tags: OK | N drifted
#   [INJECT] frontmatter: surface=... host=... | noop
#   [STATUS] PASS | NEEDS-ATTENTION
#
# Caller logic:
#   - All [VERIFY] PASS → proceed to CEO Brief
#   - Any [VERIFY] FAIL → block, prompt operator for retry
#   - Any [DRIFT] non-OK → surface as open-loop / CEO Brief section (advisory)

set -u
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SESSION_FILE="${1:-}"
TODAY=$(date +%Y-%m-%d)
EXIT_STATUS="PASS"

note_fail() { EXIT_STATUS="NEEDS-ATTENTION"; }

# ---------- PRE-VERIFY: AUTO-POPULATE FRONTMATTER ----------

# 0. Inject surface/host into session note frontmatter (idempotent)
# Closes 2026-05-19 open loop "Sessionend auto-population of surface/host/session_id".
# Runs BEFORE frontmatter VERIFY so injected fields count toward FM_HITS if needed.
INJECT="${PROJECT_DIR}/master-brain/skills/sessionend/Scripts/inject_frontmatter.sh"
if [[ -x "$INJECT" && -f "$SESSION_FILE" ]]; then
  INJECT_OUT=$("$INJECT" "$SESSION_FILE" 2>&1 || echo "[inject_frontmatter] error")
  # Extract last line (the result)
  echo "[INJECT] $(echo "$INJECT_OUT" | tail -1 | sed 's/^\[inject_frontmatter\] //')"
fi

# ---------- BLOCKING CHECKS ----------

# 1. Session file exists + has frontmatter
if [[ -z "$SESSION_FILE" || ! -f "$SESSION_FILE" ]]; then
  echo "[VERIFY] frontmatter: FAIL — session file missing or not provided"
  note_fail
else
  FM_HITS=$(head -20 "$SESSION_FILE" | grep -cE "^(date|dept|status|open_loops):")
  if (( FM_HITS >= 4 )); then
    echo "[VERIFY] frontmatter: PASS"
  else
    echo "[VERIFY] frontmatter: FAIL — only $FM_HITS/4 required fields found"
    note_fail
  fi
fi

# 2. Rollup Q1 surfaces today's session
RENDERER="${PROJECT_DIR}/master-brain/skills/dashboard-view/dashboard_render.py"
if [[ -f "$RENDERER" ]]; then
  Q1_HIT=$(python3 "$RENDERER" --query q1 2>/dev/null | grep -c "$TODAY" || true)
  if (( Q1_HIT > 0 )); then
    echo "[VERIFY] rollup-q1:   PASS"
  else
    echo "[VERIFY] rollup-q1:   FAIL — Q1 shows no session note for $TODAY"
    note_fail
  fi
else
  echo "[VERIFY] rollup-q1:   SKIPPED — renderer not found"
fi

# 3. awareness.md one-liner has today's date
AWARE="${PROJECT_DIR}/master-brain/awareness.md"
if [[ -f "$AWARE" ]] && grep -q "Last: $TODAY" "$AWARE"; then
  echo "[VERIFY] awareness:   PASS"
elif [[ -f "$AWARE" ]] && ! grep -qE "^Last: |- \*\*Last:|^Last:" "$AWARE"; then
  # First-run state: scaffolded awareness.md never had a Last: line.
  # Don't fail — this is the operator's first close, not drift.
  echo "[VERIFY] awareness:   SKIPPED — first-run (no prior 'Last:' lines; will populate on next close)"
elif [[ ! -f "$AWARE" ]]; then
  echo "[VERIFY] awareness:   SKIPPED — awareness.md not present (greenfield)"
else
  echo "[VERIFY] awareness:   FAIL — no 'Last: $TODAY' line in awareness.md"
  note_fail
fi

# ---------- ADVISORY DRIFT CHECKS ----------

# 4. Parity drift (conditional on changed paths)
PARITY_TRIGGER=$(cd "$PROJECT_DIR" 2>/dev/null && git status --porcelain 2>/dev/null | \
  grep -cE "master-brain/(decisions|skills|hardware-inventory|labels|state/fleet-dispatch\.json)/|master-brain/(CLAUDE_CODE_SOP|NAMING_CONVENTION|CREDENTIAL_HANDLING_SOP|BRAIN_GOVERNANCE)\.md" || true)
if (( PARITY_TRIGGER > 0 )); then
  PARITY_OUT=$(python3 "${PROJECT_DIR}/master-brain/skills/sessionend/Scripts/parity_drift_check.py" 2>&1 || echo "ERROR")
  PARITY_FINDINGS=$(echo "$PARITY_OUT" | grep -cE "missing-active|bare-retired" || true)
  if (( PARITY_FINDINGS > 0 )); then
    echo "[DRIFT]  parity:      $PARITY_FINDINGS findings"
  else
    echo "[DRIFT]  parity:      OK"
  fi
else
  echo "[DRIFT]  parity:      OK (no trigger paths touched)"
fi

# 5. Council halts (conditional on file presence + non-empty)
HALTS_FILE="${PROJECT_DIR}/master-brain/state/council-halts.jsonl"
if [[ -s "$HALTS_FILE" ]]; then
  CUTOFF=$(date -v-30d +%Y-%m-%d 2>/dev/null || date -d "30 days ago" +%Y-%m-%d 2>/dev/null || echo "")
  HALT_COUNT=$(python3 -c "
import json, sys
cnt = 0
cutoff = '$CUTOFF'
for line in open('$HALTS_FILE'):
    try:
        r = json.loads(line)
        if r.get('outcome') == 'HALT_TO_OPERATOR' and r.get('ts','')[:10] >= cutoff:
            cnt += 1
    except: pass
print(cnt)
" 2>/dev/null || echo "0")
  if (( HALT_COUNT > 0 )); then
    echo "[DRIFT]  halts:       $HALT_COUNT HALT_TO_OPERATOR (last 30d)"
  else
    echo "[DRIFT]  halts:       OK"
  fi
else
  echo "[DRIFT]  halts:       OK"
fi

# 6. Skill discoverability lint
LINT="${PROJECT_DIR}/master-brain/skills/skill-discoverability-lint/Scripts/lint.py"
if [[ -f "$LINT" ]]; then
  # Count actual [CRITICAL] finding lines, NOT the summary line which always contains "0 CRITICAL / ..."
  LINT_CRIT=$(python3 "$LINT" 2>/dev/null | grep -c "^  \[CRITICAL\]" || true)
  if (( LINT_CRIT > 0 )); then
    echo "[DRIFT]  skill-lint:  $LINT_CRIT CRITICAL"
  else
    echo "[DRIFT]  skill-lint:  OK"
  fi
else
  echo "[DRIFT]  skill-lint:  SKIPPED"
fi

# 6b. Source-tag lint (memory frontmatter source-surface fields)
STAG="${PROJECT_DIR}/master-brain/skills/source-tag-lint/Scripts/lint.py"
if [[ -f "$STAG" ]]; then
  STAG_OUT=$(python3 "$STAG" --summary 2>/dev/null || echo "")
  # Parse: "source-tag-lint: scanned=N CRITICAL=N WARN=N INFO=N"
  STAG_CRIT=$(echo "$STAG_OUT" | grep -oE 'CRITICAL=[0-9]+' | head -1 | cut -d= -f2)
  STAG_WARN=$(echo "$STAG_OUT" | grep -oE 'WARN=[0-9]+' | head -1 | cut -d= -f2)
  STAG_CRIT=${STAG_CRIT:-0}
  STAG_WARN=${STAG_WARN:-0}
  if (( STAG_CRIT > 0 )); then
    echo "[DRIFT]  source-tag:  $STAG_CRIT CRITICAL / $STAG_WARN WARN"
  elif (( STAG_WARN > 0 )); then
    echo "[DRIFT]  source-tag:  $STAG_WARN WARN (post-doctrine writes via bypass path)"
  else
    echo "[DRIFT]  source-tag:  OK"
  fi
else
  echo "[DRIFT]  source-tag:  SKIPPED"
fi

# 7. Cerebro auditor
AUDITOR="${PROJECT_DIR}/master-brain/skills/cerebro-auditor/Scripts/audit.py"
if [[ -f "$AUDITOR" ]]; then
  AUD_OUT=$(CEREBRO_AUDITOR_PUSH=1 python3 "$AUDITOR" --critical-only 2>/dev/null || echo "")
  AUD_CRIT=$(echo "$AUD_OUT" | grep -c "CRITICAL" || true)
  if (( AUD_CRIT > 0 )); then
    echo "[DRIFT]  auditor:     $AUD_CRIT CRITICAL"
  else
    echo "[DRIFT]  auditor:     OK"
  fi
else
  echo "[DRIFT]  auditor:     SKIPPED"
fi

# 8. Hermes config drift
HCFG="${PROJECT_DIR}/master-brain/skills/sessionend/Scripts/hermes_config_drift.py"
if [[ -f "$HCFG" ]]; then
  HCFG_OUT=$( { gtimeout 8 python3 "$HCFG" 2>&1 || python3 "$HCFG" 2>&1; } || echo "TIMEOUT")
  if echo "$HCFG_OUT" | grep -q "not present — skip"; then
    echo "[DRIFT]  hermes-cfg:  SKIPPED (N/A — cerebro-deploy/ not present)"
  elif echo "$HCFG_OUT" | grep -q "TIMEOUT\|unreachable\|ssh:"; then
    echo "[DRIFT]  hermes-cfg:  SKIPPED (hub unreachable)"
  else
    HCFG_FINDINGS=$(echo "$HCFG_OUT" | grep -cE "DRIFT|MISSING|MISMATCH" || true)
    if (( HCFG_FINDINGS > 0 )); then
      echo "[DRIFT]  hermes-cfg:  $HCFG_FINDINGS findings"
    else
      echo "[DRIFT]  hermes-cfg:  OK"
    fi
  fi
else
  echo "[DRIFT]  hermes-cfg:  SKIPPED"
fi

# 9. Diagram drift-tag check
DDC="${PROJECT_DIR}/master-brain/skills/sessionend/Scripts/diagram_drift_check.py"
if [[ -x "$DDC" ]]; then
  python3 "$DDC" 2>/dev/null || echo "[DRIFT]  diagram-tags: SKIPPED (probe error)"
else
  echo "[DRIFT]  diagram-tags: SKIPPED"
fi

# 10. Git-tree probe — verifies session-critical work was committed,
#     not just left dirty in working tree. Sessionend verifies that direct-commit happened
#     for the session's critical paths. Noise paths (state logs, memory health JSON, audit
#     overrides) excluded — they churn outside session scope.
GIT_DIRTY_CRITICAL=$(cd "$PROJECT_DIR" 2>/dev/null && git status --porcelain 2>/dev/null | \
  grep -E "^.[MADRCU?] (master-brain/(decisions|skills|sessions|CLAUDE\.md|awareness\.md|DASHBOARD\.md|CLAUDE_CODE_SOP\.md|NAMING_CONVENTION\.md|CREDENTIAL_HANDLING_SOP\.md|BRAIN_GOVERNANCE\.md)|[a-z]+/CLAUDE\.md|[a-z]+/brain/(sessions|decisions)|constellation/|CLAUDE\.md|AGENTS\.md)" | \
  grep -vE "(memory-stack-health\.json|audit-overrides\.log|memory-budget-alert\.txt|curator-runs/)" || true)
GIT_CRIT_COUNT=$(echo -n "$GIT_DIRTY_CRITICAL" | grep -c . || true)
if (( GIT_CRIT_COUNT > 0 )); then
  echo "[DRIFT]  git-tree:    $GIT_CRIT_COUNT session-critical files uncommitted (commit before close)"
  echo "$GIT_DIRTY_CRITICAL" | head -5 | sed 's/^/             /'
  (( GIT_CRIT_COUNT > 5 )) && echo "             ... (+$((GIT_CRIT_COUNT - 5)) more)"
else
  echo "[DRIFT]  git-tree:    OK (no session-critical uncommitted work)"
fi

echo "[STATUS] $EXIT_STATUS"
exit 0
