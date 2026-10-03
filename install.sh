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
#   ./install.sh --target ~/cerebro-brain          # upgrade: re-run the profile recorded
#                                                  # in the target's .libro-manifest.json
#
# Behavior:
#   - Creates .libro-backup-<ISO8601>/ snapshot of existing Brain folder before
#     mutating (Reversibility #5 — --rollback restores from latest)
#   - Re-running a profile install is a no-op if Brain state matches manifest
#   - Upgrade: an installed skill whose files differ from this checkout (names
#     as stored on disk, bytes, exec bit) is replaced as a whole folder, so a
#     case-only rename such as 0.3.0-alpha's Scripts/ to scripts/ lands on
#     case-insensitive filesystems too. Scaffold files you edited are never
#     overwritten. See UPGRADING.md.
#   - Outside --target (default: ~/cerebro-brain) a real run writes exactly two
#     things: the log at ~/.cerebro-install.log and the .libro-backup-* folder
#     beside the target. --dry-run writes neither; it only reads, plus temp
#     files it deletes before exiting.
#   - Exits non-zero unless the install record (.libro-manifest.json) was
#     written and the post-install health check is HEALTHY
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
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        # A dry run writes nothing anywhere, the log file included.
        echo "${ts} [${level}] ${msg}"
    else
        echo "${ts} [${level}] ${msg}" | tee -a "${LOG_FILE}"
    fi
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
  --profile <name>       Profile to install (libro-core | libro-starter | libro-govcon | libro-creator | libro-ops | libro-full).
                         Optional when upgrading: if omitted and the target already has a
                         .libro-manifest.json, the profile recorded there is re-installed.
  --target <path>        Install path (default: ~/cerebro-brain)
  --dry-run              Plan only; do not write any files
  --rollback             Restore Brain from the most recent .libro-backup-* snapshot
  --doctor               Run cerebro-doctor health check only (no install)
  --strict               Treat doctor warnings as errors (exit non-zero on any warning)
  --bundle-sha <sha256>  Optional source/archive SHA256; recorded in .libro-manifest.json extra
  --help                 Show this help

Examples:
  $(basename "$0") --profile libro-core
  $(basename "$0") --profile libro-starter
  $(basename "$0") --target ~/cerebro-brain        # upgrade an existing install in place
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

# Upgrade convenience: with no --profile, re-install the profile the target
# already records, so an upgrade cannot silently shrink to a smaller profile.
if [[ $DOCTOR_ONLY -eq 0 && -z "${PROFILE}" && -f "${TARGET_DIR}/.libro-manifest.json" ]]; then
    PROFILE="$(python3 -c "
import json, sys
try:
    print(json.load(open(sys.argv[1])).get('profile', ''))
except Exception:
    print('')
" "${TARGET_DIR}/.libro-manifest.json")"
    if [[ -n "${PROFILE}" ]]; then
        _info "No --profile given; upgrading the recorded profile: ${PROFILE}"
    fi
fi

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
        # Idempotency: skip only if the whole installed folder matches this
        # checkout. The comparison uses names as stored on disk, so a folder
        # stored as Scripts/ never matches a source scripts/ folder, even on a
        # case-insensitive filesystem where both names open the same folder.
        if python3 "${LIB_DIR}/distribution.py" tree-equal \
                --src "${source_skill}" --dst "${dest_skill}" >/dev/null 2>&1; then
            # Still record as installed-on-disk so .libro-manifest.json
            # reflects the FULL installed state, not just this run's delta.
            INSTALLED_SKILLS+=("${skill_name}")
            _info "  SKIP (already installed, up-to-date): ${skill_name}"
            return 0
        fi

        if [[ $DRY_RUN -eq 1 ]]; then
            _info "  DRY-RUN: would update skill: ${skill_name}"
            python3 "${LIB_DIR}/distribution.py" tree-equal --verbose \
                --src "${source_skill}" --dst "${dest_skill}" 2>/dev/null \
                | sed 's/^/      /' || true
            return 0
        fi

        # Upgrade: replace the folder as a whole. Removing it first is what makes
        # a case-only rename (0.3.0-alpha: Scripts/ to scripts/) take effect on
        # case-insensitive filesystems; copying over the old folder would keep the
        # old stored name. The previous copy is in the backup taken above.
        rm -rf "${dest_skill}"
        cp -R "${source_skill}" "${dest_skill}"
        INSTALLED_SKILLS+=("${skill_name}")
        _info "  UPDATED skill: ${skill_name} (previous copy kept in the backup)"
        return 0
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        _info "  DRY-RUN: would install skill: ${skill_name}"
        return 0
    fi

    mkdir -p "$(dirname "${dest_skill}")"
    cp -R "${source_skill}" "${dest_skill}"
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

    # Stale folder layout: an installed skill that still holds a folder stored
    # under an older name than this checkout ships (0.3.0-alpha: Scripts/ became
    # scripts/ for four skills). Stored names are read with os.listdir, so this
    # works on case-insensitive filesystems too.
    if [[ -d "${TARGET_DIR}/.claude/skills" && -d "${SKILLS_SRC_DIR}" ]]; then
        local stale
        stale="$(python3 -c "
import os, sys
inst, src = sys.argv[1], sys.argv[2]
for skill in sorted(os.listdir(inst)):
    i, s = os.path.join(inst, skill), os.path.join(src, skill)
    if not (os.path.isdir(i) and os.path.isdir(s)):
        continue
    have, want = set(os.listdir(i)), set(os.listdir(s))
    for name in sorted(have - want):
        if name.lower() in {w.lower() for w in want - have}:
            print(f'{skill}/{name}')
" "${TARGET_DIR}/.claude/skills" "${SKILLS_SRC_DIR}" 2>/dev/null || true)"
        if [[ -z "${stale}" ]]; then
            _info "  ✓ skill folder layout matches this checkout"
        else
            while IFS= read -r s; do
                [[ -z "$s" ]] && continue
                _warn "  ✗ stale folder name: ${s} (re-run ./install.sh to migrate; see UPGRADING.md)"
                warn_count=$((warn_count + 1))
            done <<< "${stale}"
            ok=0
        fi
    fi

    # fleet-dispatch.template.json or fleet-dispatch.json (under master-brain/state/)
    if [[ -f "${TARGET_DIR}/master-brain/state/fleet-dispatch.json" ]] || \
       [[ -f "${TARGET_DIR}/master-brain/state/fleet-dispatch.template.json" ]]; then
        _info "  ✓ master-brain/state/fleet-dispatch.[template.]json present"
    else
        _warn "  ✗ master-brain/state/fleet-dispatch[.template].json missing — run: cerebro-doctor --init-fleet"
        ok=0
    fi

    # Install record (.libro-manifest.json): the only proof of what was
    # installed, and what the upgrade path reads. Missing, unreadable, empty,
    # out of step with disk, or behind this checkout is never HEALTHY.
    local record_out="" record_rc=0
    _info "  Install record check: ${TARGET_DIR}/.libro-manifest.json"
    # `|| record_rc=$?` keeps set -e from ending the run on the expected non-zero exit.
    record_out="$(python3 "${LIB_DIR}/distribution.py" verify-record \
        --target "${TARGET_DIR}" --manifests-dir "${MANIFESTS_DIR}" 2>&1)" || record_rc=$?
    if [[ $record_rc -eq 0 ]]; then
        _info "  ✓ install record present, readable, matches disk and this checkout's version"
    else
        while IFS= read -r line; do
            [[ -z "${line}" ]] && continue
            _warn "  ✗ ${line}"
            warn_count=$((warn_count + 1))
        done <<< "${record_out:-install record check failed to run}"
        ok=0
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
if [[ $DRY_RUN -eq 1 ]]; then
    _info "Log:        none (a dry run writes no log and no files)"
else
    _info "Log:        ${LOG_FILE}"
fi

# Upgrade awareness: read what the target already records so the new
# .libro-manifest.json keeps tracking anything installed earlier (for example a
# skill from a larger profile) that is still on disk. uninstall.sh removes only
# what this file lists.
PRIOR_SKILLS=()
PRIOR_SCAFFOLD=()
if [[ -f "${TARGET_DIR}/.libro-manifest.json" ]]; then
    _prior_json="$(mktemp)"
    if python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print('version', d.get('version', 'unknown'), d.get('profile', 'unknown'))
for s in d.get('installed_skills', []):
    print('skill', s)
for s in d.get('installed_scaffold', []):
    print('scaffold', s)
" "${TARGET_DIR}/.libro-manifest.json" > "${_prior_json}" 2>/dev/null; then
        while read -r kind value rest; do
            case "${kind}" in
                version)  _info "Upgrade:    target records ${rest} at profile version ${value}" ;;
                skill)    PRIOR_SKILLS+=("${value}") ;;
                scaffold) PRIOR_SCAFFOLD+=("${value}") ;;
            esac
        done < "${_prior_json}"
    else
        _warn "Existing .libro-manifest.json is unreadable; it will be rewritten."
    fi
    rm -f "${_prior_json}"
fi

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

# Exclusion gate, before anything is written: refuse a profile that would install
# a path Libro must never ship (lib/distribution.py EXCLUDE_AT_INSTALL_TIME plus
# each manifest's excluded_paths).
EXCL_OUT=""
EXCL_RC=0
EXCL_OUT="$(python3 "${LIB_DIR}/distribution.py" check-exclusions \
    --manifests-dir "${MANIFESTS_DIR}" --profile "${PROFILE}" 2>&1)" || EXCL_RC=$?
if [[ $EXCL_RC -ne 0 ]]; then
    _error "Refusing to install: ${EXCL_OUT}"
    exit 1
fi

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

# Carry forward earlier install records that are still on disk (see PRIOR_* above).
for s in "${PRIOR_SKILLS[@]+"${PRIOR_SKILLS[@]}"}"; do
    if [[ -d "${TARGET_DIR}/.claude/skills/${s}" ]]; then
        INSTALLED_SKILLS+=("${s}")
    fi
done
for s in "${PRIOR_SCAFFOLD[@]+"${PRIOR_SCAFFOLD[@]}"}"; do
    if [[ -f "${TARGET_DIR}/${s}" ]]; then
        INSTALLED_SCAFFOLD+=("${s}")
    fi
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
# A failed writeback is FATAL to the run's result: the skill bytes stay on disk
# (the backup can restore the prior state), but without a current record nothing
# proves what was installed, so the run exits non-zero and the health check
# below cannot report HEALTHY.

INSTALL_INCOMPLETE=0
_set_record_aside() {
    # A record that no longer describes the target must not vouch for it. Move it
    # aside (best effort; an unwritable target keeps it, and the version check in
    # the health check still flags a stale one).
    local rec="${TARGET_DIR}/.libro-manifest.json"
    if [[ -f "${rec}" ]]; then
        mv -f "${rec}" "${rec}.incomplete" 2>/dev/null \
            && _warn "  Previous install record moved aside to .libro-manifest.json.incomplete"
    fi
    return 0
}

if [[ $DRY_RUN -eq 0 ]]; then
    _info "=== Writing installed manifest (.libro-manifest.json) ==="
    helper="${LIB_DIR}/distribution.py"
    if [[ ! -f "${helper}" ]]; then
        _error "INSTALL INCOMPLETE: distribution helper missing (${helper}); no install record written."
        INSTALL_INCOMPLETE=1
        _set_record_aside
    else
        # Bash 3.2 (macOS default) needs the +"…" expansion for empty arrays
        # under `set -u`. Both lists may legitimately be empty on a fully
        # idempotent re-run where every skill was SKIP.
        skills_str="${INSTALLED_SKILLS[*]+"${INSTALLED_SKILLS[*]}"}"
        scaffold_str="${INSTALLED_SCAFFOLD[*]+"${INSTALLED_SCAFFOLD[*]}"}"
        # Build optional args list (bash 3.2 compatible — no declare -a with +=)
        bundle_sha_args=()
        [[ -n "${BUNDLE_SHA}" ]] && bundle_sha_args=("--bundle-sha" "${BUNDLE_SHA}")
        WB_ERR="$(mktemp)"
        WB_RC=0
        python3 "${helper}" writeback \
                --target "${TARGET_DIR}" \
                --manifests-dir "${MANIFESTS_DIR}" \
                --profile "${PROFILE}" \
                --installed-skills "${skills_str}" \
                --installed-scaffold "${scaffold_str}" \
                --source-root "${SOURCE_ROOT}" \
                "${bundle_sha_args[@]+"${bundle_sha_args[@]}"}" \
                > /dev/null 2> "${WB_ERR}" || WB_RC=$?
        while IFS= read -r line; do
            [[ -z "${line}" ]] && continue
            if [[ $WB_RC -eq 0 ]]; then _info "  ${line}"; else _error "  ${line}"; fi
        done < "${WB_ERR}"
        rm -f "${WB_ERR}"
        if [[ $WB_RC -eq 0 ]]; then
            _info "  Wrote ${TARGET_DIR}/.libro-manifest.json"
        else
            _error "INSTALL INCOMPLETE: install record not written (writeback exit ${WB_RC}). Skill files are on disk;"
            _error "  nothing proves what was installed. Fix the cause and re-run, or --rollback to the backup."
            INSTALL_INCOMPLETE=1
            _set_record_aside
        fi
    fi
fi

if [[ $DRY_RUN -eq 1 ]]; then
    # Nothing was written, so there is nothing new to verify. Show the target's
    # CURRENT state so the dry run says what an upgrade would fix.
    _info "=== Current-state health check (dry run; nothing was written) ==="
    do_doctor || true
    _info "=== DRY-RUN complete: no files and no log written ==="
    exit 0
fi

# Post-install doctor check. The run's exit status is the verdict: 0 only when
# the record was written and the health check is HEALTHY.
_info "=== Post-install health check ==="
DOCTOR_RC=0
do_doctor || DOCTOR_RC=$?
if [[ $INSTALL_INCOMPLETE -eq 1 ]]; then
    _error "=== Libro install INCOMPLETE: ${PROFILE} → ${TARGET_DIR} (no install record) ==="
    exit 3
elif [[ $DOCTOR_RC -ne 0 ]]; then
    _error "=== Libro install finished with a failing health check: review the warnings above ==="
    exit 2
else
    _info "=== Libro install complete: ${PROFILE} → ${TARGET_DIR} ==="
fi
