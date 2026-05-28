#!/usr/bin/env bash
# uninstall.sh — Cerebro Libro uninstall runner
#
# Reads .libro-manifest.json at TARGET_DIR and removes every skill and scaffold
# file that Libro installed. Reverse-walks the installed manifest: skills are
# removed from .claude/skills/, scaffold files are removed from their target
# paths. .libro-manifest.json is removed last.
#
# Usage:
#   ./uninstall.sh                              # uninstall from ~/cerebro-brain (default)
#   ./uninstall.sh --target /path/to/brain      # custom target
#   ./uninstall.sh --dry-run                    # print what would be removed
#
# Safety contract (Reversibility #5):
#   - Creates a backup snapshot BEFORE removing anything
#   - Only removes paths listed in .libro-manifest.json (no guesswork)
#   - Never removes the target directory itself
#   - Exits non-zero if .libro-manifest.json is missing or unreadable
#
# Principles: Reversibility #5, Least-Privilege #7, Observability #6

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET_DIR="${HOME}/cerebro-brain"
DRY_RUN=0
# Log file precedence: LIBRO_LOG_FILE env override > target-local log > $HOME log.
# Logging is best-effort: failure to write a log line never blocks uninstall.
LOG_FILE="${LIBRO_LOG_FILE:-${HOME}/.cerebro-install.log}"

_log() {
    local level="$1"; shift
    local ts; ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    local line="${ts} [${level}] $*"
    # Always emit to stdout/stderr; log file write is best-effort.
    echo "${line}"
    # Try to ensure parent dir exists; suppress all failures so a restricted
    # $HOME or read-only LOG_FILE never aborts uninstall. The subshell wrapper
    # swallows shell-level redirect errors that 2>/dev/null can't catch when
    # the file open itself fails (bash emits errno before the command runs).
    ( mkdir -p "$(dirname "${LOG_FILE}")" >/dev/null 2>&1 && \
      printf '%s\n' "${line}" >> "${LOG_FILE}" ) >/dev/null 2>&1 || true
}
_info()  { _log INFO  "$@"; }
_warn()  { _log WARN  "$@"; }
_error() { _log ERROR "$@" >&2; }

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --target <path>   Brain directory to uninstall from (default: ~/cerebro-brain)
  --dry-run         Print what would be removed; do not delete files
  --help            Show this help

Examples:
  $(basename "$0")
  $(basename "$0") --target /tmp/libro-smoke-h22-mac
  $(basename "$0") --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)    TARGET_DIR="$2"; shift 2 ;;
        --dry-run)   DRY_RUN=1; shift ;;
        --yes|-y)    shift ;;  # no-op, accepted for CI / non-interactive use
        --help|-h)   usage; exit 0 ;;
        *)           _error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

MANIFEST_FILE="${TARGET_DIR}/.libro-manifest.json"

if [[ ! -f "${MANIFEST_FILE}" ]]; then
    _error "No .libro-manifest.json found at ${TARGET_DIR}"
    _error "Cannot uninstall: no Libro install record. If Libro was installed manually,"
    _error "remove .claude/skills/ and master-brain/ directories by hand."
    exit 1
fi

if ! python3 -c "import json; json.load(open('${MANIFEST_FILE}'))" 2>/dev/null; then
    _error "Cannot parse .libro-manifest.json — file may be corrupt."
    exit 1
fi

PROFILE=$(python3 -c "import json; print(json.load(open('${MANIFEST_FILE}')).get('profile','unknown'))")
VERSION=$(python3 -c "import json; print(json.load(open('${MANIFEST_FILE}')).get('version','unknown'))")
INSTALL_TS=$(python3 -c "import json; print(json.load(open('${MANIFEST_FILE}')).get('install_ts_utc','unknown'))")

_info "=== Libro uninstall: ${PROFILE} v${VERSION} (installed ${INSTALL_TS}) ==="
_info "Target:  ${TARGET_DIR}"
_info "Dry-run: ${DRY_RUN}"

# ---------------------------------------------------------------------------
# Backup before removing anything (Reversibility #5)
# ---------------------------------------------------------------------------

if [[ $DRY_RUN -eq 0 ]]; then
    BACKUP_TS=$(date -u +"%Y-%m-%dT%H%M%SZ")
    _TARGET_SLUG="$(basename "${TARGET_DIR}")"
    _PARENT_REAL="$(cd "${TARGET_DIR%/*}" 2>/dev/null && pwd -P)" || _PARENT_REAL="${TARGET_DIR%/*}"
    BACKUP_DIR="${_PARENT_REAL}/.libro-backup-${_TARGET_SLUG}-${BACKUP_TS}"
    _info "Backup: ${TARGET_DIR} → ${BACKUP_DIR}"
    cp -r "${TARGET_DIR}" "${BACKUP_DIR}"
    _info "Backup complete. Rollback: install.sh --rollback --target ${TARGET_DIR}"
fi

# ---------------------------------------------------------------------------
# Remove installed skills
# ---------------------------------------------------------------------------

_info "--- Removing installed skills ---"
SKILLS_REMOVED=0
SKILLS_MISSING=0

while IFS= read -r skill_name; do
    [[ -z "${skill_name}" ]] && continue
    skill_dir="${TARGET_DIR}/.claude/skills/${skill_name}"
    if [[ -d "${skill_dir}" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            _info "  DRY-RUN: would remove skill: ${skill_name}"
        else
            rm -rf "${skill_dir}"
            _info "  REMOVED skill: ${skill_name}"
        fi
        SKILLS_REMOVED=$((SKILLS_REMOVED + 1))
    else
        _warn "  SKIP (not found on disk): ${skill_name}"
        SKILLS_MISSING=$((SKILLS_MISSING + 1))
    fi
done < <(python3 -c "
import json, sys
d = json.load(open('${MANIFEST_FILE}'))
for s in d.get('installed_skills', []):
    print(s)
" 2>/dev/null || true)

# ---------------------------------------------------------------------------
# Remove installed scaffold files (leaf-first to allow rmdir of empty dirs)
# ---------------------------------------------------------------------------

_info "--- Removing installed scaffold files ---"
SCAFFOLD_REMOVED=0
SCAFFOLD_MISSING=0

while IFS= read -r rel_path; do
    [[ -z "${rel_path}" ]] && continue
    full_path="${TARGET_DIR}/${rel_path}"
    if [[ -f "${full_path}" ]]; then
        if [[ $DRY_RUN -eq 1 ]]; then
            _info "  DRY-RUN: would remove scaffold: ${rel_path}"
        else
            rm -f "${full_path}"
            _info "  REMOVED scaffold: ${rel_path}"
        fi
        SCAFFOLD_REMOVED=$((SCAFFOLD_REMOVED + 1))
    else
        _warn "  SKIP (not found on disk): ${rel_path}"
        SCAFFOLD_MISSING=$((SCAFFOLD_MISSING + 1))
    fi
done < <(python3 -c "
import json, sys
d = json.load(open('${MANIFEST_FILE}'))
for s in sorted(d.get('installed_scaffold', []), reverse=True):
    print(s)
" 2>/dev/null || true)

# ---------------------------------------------------------------------------
# Remove .libro-manifest.json (last — only on real run)
# ---------------------------------------------------------------------------

if [[ $DRY_RUN -eq 1 ]]; then
    _info "  DRY-RUN: would remove .libro-manifest.json"
else
    rm -f "${MANIFEST_FILE}"
    _info "  REMOVED .libro-manifest.json"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

_info "=== Uninstall summary ==="
_info "  Skills removed:    ${SKILLS_REMOVED}"
_info "  Skills not found:  ${SKILLS_MISSING}"
_info "  Scaffold removed:  ${SCAFFOLD_REMOVED}"
_info "  Scaffold not found: ${SCAFFOLD_MISSING}"
if [[ $DRY_RUN -eq 0 ]]; then
    _info "  Backup at: ${BACKUP_DIR:-none}"
fi
if [[ $DRY_RUN -eq 1 ]]; then
    _info "=== Uninstall: DRY-RUN complete (nothing removed) ==="
else
    _info "=== Uninstall complete: ${PROFILE} removed from ${TARGET_DIR} ==="
fi
