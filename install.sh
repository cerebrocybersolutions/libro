#!/usr/bin/env bash
# install.sh — Cerebro Libro install runner
#
# Two-stage: plan then execute. Idempotent. Dry-run and rollback flags.
#
# Usage:
#   ./install.sh --profile libro-core              # plan + execute (default)
#   ./install.sh --profile libro-govcon --dry-run  # plan only
#   ./install.sh --profile libro-ops --target ~/my-brain   # custom install path
#   ./install.sh --rollback                        # restore from latest backup
#   ./install.sh --doctor                          # run cerebro-doctor only
#
# Behavior:
#   - Creates .libro-backup-<ISO8601>/ snapshot of existing Brain folder before
#     mutating (Reversibility #5 — --rollback restores from latest)
#   - Re-running a profile install is a no-op if Brain state matches manifest
#   - Never modifies files outside --target (default: ~/cerebro-brain)
#   - Logs every action to ~/.cerebro-install.log
#
# Principles: reversibility, least-privilege, observability.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/manifests"
LIB_DIR="${SCRIPT_DIR}/lib"
# SOURCE_ROOT = repo root (where install.sh sits). Skills, scaffold, and templates
# all live under SCRIPT_DIR in the clone-and-run distribution model.
SOURCE_ROOT="${SCRIPT_DIR}"
SKILLS_SRC_DIR="${SCRIPT_DIR}/skills"
SCAFFOLD_SRC_DIR="${SCRIPT_DIR}/scaffold"

PROFILE=""
TARGET_DIR="${HOME}/cerebro-brain"
DRY_RUN=0
ROLLBACK=0
DOCTOR_ONLY=0
STRICT=0
BUNDLE_SHA=""
LOG_FILE="${HOME}/.cerebro-install.log"

# Phase 6 closure trackers (H22 port — distribution writeback)
# Globally tracked because _install_skill / _install_scaffold_file mutate
# them and the writeback step at the bottom reads them in aggregate.
INSTALLED_SKILLS=()
INSTALLED_SCAFFOLD=()

# ---------------------------------------------------------------------------
# Logging (Observability #6)
# ---------------------------------------------------------------------------

_log() {
    local level="$1"; shift
    local msg="$*"
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "${ts} [${level}] ${msg}" | tee -a "${LOG_FILE}"
}

_info()  { _log INFO  "$@"; }
_warn()  { _log WARN  "$@"; }
_error() { _log ERROR "$@" >&2; }

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --profile <name>       Profile to install (libro-core | libro-govcon | libro-creator | libro-ops | libro-full)
  --target <path>        Install path (default: ~/cerebro-brain)
  --dry-run              Plan only; do not write any files
  --rollback             Restore Brain from the most recent .libro-backup-* snapshot
  --doctor               Run cerebro-doctor health check only (no install)
  --strict               Treat doctor warnings as errors (exit non-zero on any warning)
  --bundle-sha <sha256>  Optional source/archive SHA256; recorded in .libro-manifest.json extra
  --help                 Show this help

Examples:
  $(basename "$0") --profile libro-core
  $(basename "$0") --profile libro-govcon --dry-run
  $(basename "$0") --rollback
  $(basename "$0") --doctor
  $(basename "$0") --doctor --strict
EOF
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)       PROFILE="$2"; shift 2 ;;
        --target)        TARGET_DIR="$2"; shift 2 ;;
        --dry-run)       DRY_RUN=1; shift ;;
        --rollback)      ROLLBACK=1; shift ;;
        --doctor)        DOCTOR_ONLY=1; shift ;;
        --strict)        STRICT=1; shift ;;
        --bundle-sha)    BUNDLE_SHA="$2"; shift 2 ;;
        --yes|-y)        shift ;;  # no-op, accepted for CI / non-interactive use
        --help|-h)       usage; exit 0 ;;
        *)               _error "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

do_rollback() {
    # Resolve real path to handle macOS /tmp → /private/tmp symlink
    local parent_real target_slug
    target_slug="$(basename "${TARGET_DIR}")"
    parent_real="$(cd "${TARGET_DIR%/*}" 2>/dev/null && pwd -P)" || parent_real="${TARGET_DIR%/*}"
    _info "Rollback: searching for .libro-backup-${target_slug}-* snapshots in ${parent_real}/"
    local latest
    latest=$(find "${parent_real}" -maxdepth 1 -type d -name ".libro-backup-${target_slug}-*" \
             2>/dev/null | sort | tail -n1)
    if [[ -z "${latest}" ]]; then
        _error "No backup found. Cannot rollback."
        exit 1
    fi
    _info "Rollback: restoring from ${latest}"
    if [[ $DRY_RUN -eq 1 ]]; then
        _info "DRY-RUN: would restore ${latest} → ${TARGET_DIR}"
        exit 0
    fi
    rm -rf "${TARGET_DIR}"
    cp -r "${latest}" "${TARGET_DIR}"
    _info "Rollback: complete. Brain restored from ${latest}"
}

if [[ $ROLLBACK -eq 1 ]]; then
    do_rollback
    exit 0
fi

# ---------------------------------------------------------------------------
# Validate inputs
# ---------------------------------------------------------------------------

if [[ $DOCTOR_ONLY -eq 0 && -z "${PROFILE}" ]]; then
    _error "No --profile specified. Use --doctor for health-check only."
    usage
    exit 1
fi

MANIFEST_FILE="${MANIFESTS_DIR}/${PROFILE}.json"
if [[ $DOCTOR_ONLY -eq 0 && ! -f "${MANIFEST_FILE}" ]]; then
    _error "Profile manifest not found: ${MANIFEST_FILE}"
    _error "Available profiles:"
    find "${MANIFESTS_DIR}" -name 'libro-*.json' | sed 's/.*\//  /' | sed 's/.json//'
    exit 1
fi

# ---------------------------------------------------------------------------
# Profile chain resolution (parent profiles apply first)
# ---------------------------------------------------------------------------
#
# Delegates to ${LIB_DIR}/distribution.py resolve-chain. This is the E1
# closure from Phase 5 smoke findings — the previous in-line bash walk
# warned-and-broke on a missing parent manifest (silent partial install).
# The Python helper raises ChainError and exits 1 instead, propagating the
# failure through this function and on to install.sh's exit status.
#
# Helper output is JSON on stdout; we extract the chain names array into
# a temp file to keep the bash array population safe under `set -e`.

_resolve_profile_chain() {
    # Writes space-separated profile chain names (root-first) to STDOUT on
    # success; returns non-zero on failure. The caller MUST check the return
    # status BEFORE consuming stdout via command substitution — `exit 1` here
    # would only kill a $(...) subshell, which is exactly the silent-degrade
    # pattern this function exists to close.
    local profile="$1"
    local chain_json
    local helper="${LIB_DIR}/distribution.py"

    if [[ ! -f "${helper}" ]]; then
        _error "Distribution helper not found: ${helper}"
        return 2
    fi

    chain_json="$(mktemp)"
    if ! python3 "${helper}" resolve-chain \
            --manifests-dir "${MANIFESTS_DIR}" \
            --profile "${profile}" \
            > "${chain_json}" 2>&1; then
        _error "Profile chain resolution failed for '${profile}':"
        _error "  $(tr '\n' '|' < "${chain_json}" | sed 's/|/ \/ /g')"
        rm -f "${chain_json}"
        return 1
    fi

    python3 -c "
import json, sys
with open('${chain_json}') as fh:
    d = json.load(fh)
print(' '.join(c['name'] for c in d['chain']))
"
    rm -f "${chain_json}"
    return 0
}

# ---------------------------------------------------------------------------
# Skill installation
# ---------------------------------------------------------------------------

_install_skill() {
    local skill_name="$1"
    local source_skill="${SKILLS_SRC_DIR}/${skill_name}"
    local dest_skill="${TARGET_DIR}/.claude/skills/${skill_name}"

    if [[ ! -d "${source_skill}" ]]; then
        _error "Skill source not found: ${source_skill}"
        _error "Manifest declares skill '${skill_name}' but the folder is not in the repo."
        exit 1
    fi

    if [[ -d "${dest_skill}" ]]; then
        # Idempotency: skip if already installed and SKILL.md matches
        local src_md="${source_skill}/SKILL.md"
        local dst_md="${dest_skill}/SKILL.md"
        if [[ -f "${src_md}" && -f "${dst_md}" ]]; then
            if diff -q "${src_md}" "${dst_md}" >/dev/null 2>&1; then
                # Still record as installed-on-disk so .libro-manifest.json
                # reflects the FULL installed state, not just this run's delta.
                INSTALLED_SKILLS+=("${skill_name}")
                _info "  SKIP (already installed, up-to-date): ${skill_name}"
                return 0
            fi
        fi
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        _info "  DRY-RUN: would install skill: ${skill_name}"
        return 0
    fi

    mkdir -p "$(dirname "${dest_skill}")"
    cp -r "${source_skill}" "${dest_skill}"
    INSTALLED_SKILLS+=("${skill_name}")
    _info "  INSTALLED skill: ${skill_name}"
}

# ---------------------------------------------------------------------------
# Brain scaffold installation
# ---------------------------------------------------------------------------

_install_scaffold_file() {
    local rel_path="$1"
    local src="${SCAFFOLD_SRC_DIR}/${rel_path}"
    local dst="${TARGET_DIR}/${rel_path}"

    if [[ ! -f "${src}" ]]; then
        _error "Scaffold source not found: ${src}"
        _error "Manifest declares scaffold '${rel_path}' but the file is not in the repo."
        exit 1
    fi

    if [[ -f "${dst}" ]]; then
        # Record installed-on-disk for manifest writeback (idempotent re-runs).
        INSTALLED_SCAFFOLD+=("${rel_path}")
        _info "  SKIP (already exists): ${rel_path}"
        return 0
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        _info "  DRY-RUN: would install scaffold: ${rel_path}"
        return 0
    fi

    mkdir -p "$(dirname "${dst}")"
    # CAUTION: scaffold files are copied as-is. Each file in the repo is expected to
    # have already passed the externalization pre-commit hook before landing here.
    cp "${src}" "${dst}"
    INSTALLED_SCAFFOLD+=("${rel_path}")
    _info "  INSTALLED scaffold: ${rel_path}"
}

_install_template_file() {
    # Like _install_scaffold_file but resolves source from SCRIPT_DIR (not SOURCE_ROOT).
    # Used for files that ship with the installer itself, not from the workspace tree.
    local src_name="$1"   # filename relative to SCRIPT_DIR
    local dst_rel="$2"    # destination path relative to TARGET_DIR
    local src="${SCRIPT_DIR}/${src_name}"
    local dst="${TARGET_DIR}/${dst_rel}"

    if [[ ! -f "${src}" ]]; then
        _warn "Template source not found: ${src}. Skipping."
        return 0
    fi

    if [[ -f "${dst}" ]]; then
        _info "  SKIP (already exists): ${dst_rel}"
        return 0
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        _info "  DRY-RUN: would install template: ${dst_rel}"
        return 0
    fi

    mkdir -p "$(dirname "${dst}")"
    cp "${src}" "${dst}"
    _info "  INSTALLED template: ${dst_rel}"
    # Track in scaffold manifest so uninstall.sh removes it cleanly.
    INSTALLED_SCAFFOLD+=("${dst_rel}")
}

# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------

do_doctor() {
    _info "cerebro-doctor: Brain health check at ${TARGET_DIR}"
    local ok=1
    local warn_count=0

    # Brain folder present
    if [[ -d "${TARGET_DIR}" ]]; then
        _info "  ✓ Brain folder present: ${TARGET_DIR}"
    else
        _warn "  ✗ Brain folder missing: ${TARGET_DIR}"
        ok=0
    fi

    # master-brain/CLAUDE.md
    if [[ -f "${TARGET_DIR}/master-brain/CLAUDE.md" ]]; then
        _info "  ✓ master-brain/CLAUDE.md present"
    else
        _warn "  ✗ master-brain/CLAUDE.md missing"
        ok=0
    fi

    # .claude/skills directory
    if [[ -d "${TARGET_DIR}/.claude/skills" ]]; then
        local n_skills
        n_skills=$(find "${TARGET_DIR}/.claude/skills" -maxdepth 1 -type d | wc -l)
        n_skills=$((n_skills - 1))  # exclude the parent dir itself
        _info "  ✓ .claude/skills present (${n_skills} skill(s))"
    else
        _warn "  ✗ .claude/skills missing"
        ok=0
    fi

    # fleet-dispatch.template.json or fleet-dispatch.json (under master-brain/state/)
    if [[ -f "${TARGET_DIR}/master-brain/state/fleet-dispatch.json" ]] || \
       [[ -f "${TARGET_DIR}/master-brain/state/fleet-dispatch.template.json" ]]; then
        _info "  ✓ master-brain/state/fleet-dispatch.[template.]json present"
    else
        _warn "  ✗ master-brain/state/fleet-dispatch[.template].json missing — run: cerebro-doctor --init-fleet"
        ok=0
    fi

    # Manifest drift check: if .libro-manifest.json exists, verify every listed
    # skill and scaffold is actually present on disk.
    local manifest_path="${TARGET_DIR}/.libro-manifest.json"
    if [[ -f "${manifest_path}" ]]; then
        local drift=0
        _info "  Manifest drift check: ${manifest_path}"
        # Check installed_skills
        while IFS= read -r skill_name; do
            [[ -z "${skill_name}" ]] && continue
            skill_dir="${TARGET_DIR}/.claude/skills/${skill_name}"
            if [[ ! -d "${skill_dir}" ]]; then
                _warn "  ✗ manifest drift: skill '${skill_name}' listed in manifest but missing from .claude/skills/"
                drift=$((drift + 1))
                warn_count=$((warn_count + 1))
            fi
        done < <(python3 -c "
import json, sys
d = json.load(open('${manifest_path}'))
for s in d.get('installed_skills', []):
    print(s)
" 2>/dev/null || true)
        # Check installed_scaffold
        while IFS= read -r rel_path; do
            [[ -z "${rel_path}" ]] && continue
            if [[ ! -f "${TARGET_DIR}/${rel_path}" ]]; then
                _warn "  ✗ manifest drift: scaffold '${rel_path}' listed in manifest but missing from target"
                drift=$((drift + 1))
                warn_count=$((warn_count + 1))
            fi
        done < <(python3 -c "
import json, sys
d = json.load(open('${manifest_path}'))
for s in d.get('installed_scaffold', []):
    print(s)
" 2>/dev/null || true)
        if [[ $drift -eq 0 ]]; then
            _info "  ✓ manifest drift: 0 discrepancies"
        else
            _warn "  manifest drift: ${drift} discrepancy(s) found"
            ok=0
        fi
    fi

    if [[ $ok -eq 1 ]]; then
        _info "cerebro-doctor: HEALTHY"
    else
        _warn "cerebro-doctor: ISSUES FOUND — review warnings above"
    fi

    # --strict: warnings become errors
    if [[ $STRICT -eq 1 && ( $ok -eq 0 || $warn_count -gt 0 ) ]]; then
        _error "cerebro-doctor: STRICT MODE — treating warnings as errors"
        return 1
    fi
    return $((1 - ok))
}

if [[ $DOCTOR_ONLY -eq 1 ]]; then
    do_doctor
    exit $?
fi

# ---------------------------------------------------------------------------
# Main install flow
# ---------------------------------------------------------------------------

_info "=== Libro install started ==="
_info "Profile:    ${PROFILE}"
_info "Target:     ${TARGET_DIR}"
_info "Source:     ${SOURCE_ROOT}"
_info "Dry-run:    ${DRY_RUN}"
_info "Log:        ${LOG_FILE}"

# Resolve profile chain (parent-first). The function returns non-zero on a
# broken/missing chain — we MUST check status BEFORE consuming stdout so the
# failure cannot be swallowed by a $(...) subshell (the original E1 pattern).
CHAIN_FILE="$(mktemp)"
if ! _resolve_profile_chain "${PROFILE}" > "${CHAIN_FILE}"; then
    rm -f "${CHAIN_FILE}"
    _error "Aborting install: profile chain unresolvable."
    exit 1
fi
PROFILE_CHAIN=()
while IFS=' ' read -r -a _names; do
    for n in "${_names[@]+"${_names[@]}"}"; do
        [[ -z "$n" ]] && continue
        PROFILE_CHAIN+=("$n")
    done
done < "${CHAIN_FILE}"
rm -f "${CHAIN_FILE}"
if [[ ${#PROFILE_CHAIN[@]} -eq 0 ]]; then
    _error "Aborting install: profile chain resolved to empty set."
    exit 1
fi
_info "Profile chain: ${PROFILE_CHAIN[*]}"

# Track whether the target existed before pre-flight mkdir, so the backup
# block can skip empty-baseline backups on fresh first installs (Codex
# Round 5 NIT-1 fix B — backup only fires when there's something to back up).
TARGET_EXISTED_BEFORE_PREFLIGHT=0
[[ -d "${TARGET_DIR}" ]] && TARGET_EXISTED_BEFORE_PREFLIGHT=1

# Pre-flight: ensure the target directory is writable. Catch permission errors
# here with a Libro-owned message before any nested mkdir leaks raw shell output.
if [[ $DRY_RUN -eq 0 ]]; then
    if [[ -d "${TARGET_DIR}" ]]; then
        if [[ ! -w "${TARGET_DIR}" ]]; then
            _error "Target directory exists but is not writable: ${TARGET_DIR}"
            _error "Fix: chmod the path so your user can write to it, or pass --target <writable-path>."
            exit 1
        fi
    else
        if ! mkdir -p "${TARGET_DIR}" 2>/dev/null; then
            _error "Cannot create target directory: ${TARGET_DIR}"
            _error "The parent path is likely read-only or you lack permission."
            _error "Fix: pick a writable --target path (default is ~/cerebro-brain), or chmod the parent."
            exit 1
        fi
    fi
fi

# Backup existing Brain (Reversibility #5) — before any mutation.
# Only fire when the target existed before pre-flight (otherwise we'd be
# backing up an empty directory the pre-flight just created).
# Use pwd -P to resolve symlinks (macOS /tmp → /private/tmp).
if [[ $DRY_RUN -eq 0 && $TARGET_EXISTED_BEFORE_PREFLIGHT -eq 1 ]]; then
    BACKUP_TS=$(date -u +"%Y-%m-%dT%H%M%SZ")
    _TARGET_SLUG="$(basename "${TARGET_DIR}")"
    _PARENT_REAL="$(cd "${TARGET_DIR%/*}" 2>/dev/null && pwd -P)" || _PARENT_REAL="${TARGET_DIR%/*}"
    BACKUP_DIR="${_PARENT_REAL}/.libro-backup-${_TARGET_SLUG}-${BACKUP_TS}"
    _info "Backup: ${TARGET_DIR} → ${BACKUP_DIR}"
    cp -r "${TARGET_DIR}" "${BACKUP_DIR}"
fi

# Install each profile in chain order (libro-core first, then vertical additions)
for profile in "${PROFILE_CHAIN[@]}"; do
    manifest="${MANIFESTS_DIR}/${profile}.json"
    _info "--- Installing profile: ${profile} ---"

    # Extract skills and scaffold from manifest via python3
    skills_json=$(python3 -c "
import json, sys
d = json.load(open('${manifest}'))
mods = d.get('additive_modules', {})
print(json.dumps(mods.get('skills', [])))
" 2>/dev/null || echo "[]")

    scaffold_json=$(python3 -c "
import json, sys
d = json.load(open('${manifest}'))
mods = d.get('additive_modules', {})
print(json.dumps(mods.get('brain_scaffold', [])))
" 2>/dev/null || echo "[]")

    host_deps=$(python3 -c "
import json, sys
d = json.load(open('${manifest}'))
deps = d.get('host_provided_dependencies', [])
print(json.dumps([dep['skill'] for dep in deps]))
" 2>/dev/null || echo "[]")

    # Parse arrays and install skills
    while IFS= read -r skill; do
        skill=$(echo "$skill" | tr -d '"')
        [[ -z "$skill" ]] && continue
        # Skip host-provided skills (they ship with the Claude host platform, not with Libro)
        if echo "${host_deps}" | python3 -c "import json,sys; deps=json.load(sys.stdin); s='${skill}'; sys.exit(0 if s in deps else 1)" 2>/dev/null; then
            _info "  SKIP (host-provided): ${skill}"
            continue
        fi
        _install_skill "${skill}"
    done < <(python3 -c "import json,sys; [print(s) for s in json.loads('${skills_json}')]" 2>/dev/null || true)

    # Install brain scaffold files
    while IFS= read -r scaffold_path; do
        scaffold_path=$(echo "$scaffold_path" | tr -d '"')
        [[ -z "$scaffold_path" ]] && continue
        _install_scaffold_file "${scaffold_path}"
    done < <(python3 -c "import json,sys; [print(s) for s in json.loads('${scaffold_json}')]" 2>/dev/null || true)

    # Install fleet-dispatch template (libro-core only)
    if [[ "${profile}" == "libro-core" ]]; then
        _install_template_file "fleet-dispatch.template.json" "master-brain/state/fleet-dispatch.template.json"
    fi

    _info "--- Profile ${profile}: done ---"
done

# ---------------------------------------------------------------------------
# Installed-manifest writeback (W1 closure — H22 port)
# ---------------------------------------------------------------------------
#
# Records what was actually installed at TARGET_DIR so:
#   - cerebro-doctor can verify post-install state against the manifest
#   - rollback can compare prior state vs current
#   - re-runs can short-circuit when current state matches manifest
#
# Skipped on --dry-run because nothing was actually installed.
# Non-fatal: if the writeback errors (e.g., target unwritable), we warn but
# do not undo the install — the bytes are already on disk.

if [[ $DRY_RUN -eq 0 ]]; then
    _info "=== Writing installed manifest (.libro-manifest.json) ==="
    helper="${LIB_DIR}/distribution.py"
    if [[ ! -f "${helper}" ]]; then
        _warn "Distribution helper missing: ${helper}. Skipping writeback."
    else
        # Bash 3.2 (macOS default) needs the +"…" expansion for empty arrays
        # under `set -u`. Both lists may legitimately be empty on a fully
        # idempotent re-run where every skill was SKIP.
        skills_str="${INSTALLED_SKILLS[*]+"${INSTALLED_SKILLS[*]}"}"
        scaffold_str="${INSTALLED_SCAFFOLD[*]+"${INSTALLED_SCAFFOLD[*]}"}"
        # Build optional args list (bash 3.2 compatible — no declare -a with +=)
        bundle_sha_args=()
        [[ -n "${BUNDLE_SHA}" ]] && bundle_sha_args=("--bundle-sha" "${BUNDLE_SHA}")
        if python3 "${helper}" writeback \
                --target "${TARGET_DIR}" \
                --manifests-dir "${MANIFESTS_DIR}" \
                --profile "${PROFILE}" \
                --installed-skills "${skills_str}" \
                --installed-scaffold "${scaffold_str}" \
                --source-root "${SOURCE_ROOT}" \
                "${bundle_sha_args[@]+"${bundle_sha_args[@]}"}" \
                > /dev/null; then
            _info "  Wrote ${TARGET_DIR}/.libro-manifest.json"
        else
            _warn "Manifest writeback failed (non-fatal). Install bytes are on disk."
        fi
    fi
fi

# Post-install doctor check
_info "=== Post-install health check ==="
if ! do_doctor; then
    _warn "Install completed with health check warnings. Review above."
else
    _info "=== Libro install complete: ${PROFILE} → ${TARGET_DIR} ==="
fi
