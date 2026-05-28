#!/usr/bin/env bash
# run_daily.sh — Phase 3 daily wrapper for cerebro-doctor.
#
# Scheduled via launchd (see references/com.cerebro.doctor.daily.plist).
# Runs check_resolvable.py, files a dated digest to master-brain/cerebro-doctor-reports/,
# and exits with the script's own exit code so launchd can surface drift
# via the standard-error log.
#
# Scope contract: reads AGENTS.md + SKILL.md files; writes ONE file per day
# to master-brain/cerebro-doctor-reports/. No network, no git, no Ollama.

set -euo pipefail

# Resolve workspace root. In production launchd installs, CEREBRO_WORKSPACE_ROOT
# is set in the plist EnvironmentVariables block. Fallback: walk up from
# this script to find the workspace root (three levels above master-brain/skills/cerebro-doctor/Scripts).
if [[ -z "${CEREBRO_WORKSPACE_ROOT:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    CEREBRO_WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
fi

BRAIN_DIR="$CEREBRO_WORKSPACE_ROOT/master-brain"
CHECK_SCRIPT="$BRAIN_DIR/skills/cerebro-doctor/Scripts/check_resolvable.py"
AUDITS_DIR="$BRAIN_DIR/cerebro-doctor-reports"
DATE_STAMP="$(date +%Y-%m-%d)"
OUT_FILE="$AUDITS_DIR/$DATE_STAMP-cerebro-doctor.md"

mkdir -p "$AUDITS_DIR"

# Capture the script's stdout + exit code separately so we can still file
# the digest even when drift is found.
set +e
REPORT_BODY="$(python3 "$CHECK_SCRIPT" --root "$BRAIN_DIR" 2>&1)"
EXIT_CODE=$?
set -e

# Compose the audit file with frontmatter.
cat > "$OUT_FILE" <<EOF
---
date: $DATE_STAMP
audit: cerebro-doctor
exit_code: $EXIT_CODE
principle_anchors: ["Parity #2", "Governance #1", "Reproducibility #8"]
source_script: master-brain/skills/cerebro-doctor/Scripts/check_resolvable.py
wrapper: master-brain/skills/cerebro-doctor/Scripts/run_daily.sh
---

# cerebro-doctor daily audit — $DATE_STAMP

\`\`\`
$REPORT_BODY
\`\`\`

*Filed by launchd job \`com.cerebro.doctor.daily\`. Exit code $EXIT_CODE —
0 = clean, 1 = reachability drift, 2 = DRY overlap, 3 = both.*
EOF

# Exit with the check script's code so launchd's error-log reflects drift.
exit $EXIT_CODE
