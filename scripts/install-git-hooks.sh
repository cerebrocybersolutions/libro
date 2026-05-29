#!/usr/bin/env bash
# install-git-hooks.sh — wire the Libro pre-commit secret/PII guard into a repo.
#
# Run this from the root of the git repo you want protected (typically the brain
# repo Libro scaffolded for you). It installs a pre-commit hook that runs
# scripts/pre-commit-lint.sh on every commit.
#
# Usage:
#   bash scripts/install-git-hooks.sh            # install into ./.git/hooks
#   bash scripts/install-git-hooks.sh --force    # overwrite an existing hook
#
# The installed hook is a thin shim: it execs scripts/pre-commit-lint.sh from the
# repo root, so updates to the lint script take effect with no re-install.

set -uo pipefail

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "[ERROR] not inside a git repository. cd into your brain repo first, then re-run." >&2
  echo "  Fix: git init  (if this brain isn't a repo yet), then bash scripts/install-git-hooks.sh" >&2
  exit 1
}

LINT_SCRIPT="${REPO_ROOT}/scripts/pre-commit-lint.sh"
if [[ ! -f "$LINT_SCRIPT" ]]; then
  echo "[ERROR] scripts/pre-commit-lint.sh not found at repo root (${REPO_ROOT})." >&2
  echo "  Run this from the repo where Libro is installed." >&2
  exit 1
fi
chmod +x "$LINT_SCRIPT" 2>/dev/null || true

HOOK_DIR="${REPO_ROOT}/.git/hooks"
HOOK="${HOOK_DIR}/pre-commit"
mkdir -p "$HOOK_DIR"

if [[ -e "$HOOK" && $FORCE -eq 0 ]]; then
  if grep -q 'pre-commit-lint.sh' "$HOOK" 2>/dev/null; then
    echo "[OK] Libro pre-commit hook already installed at ${HOOK}"
    exit 0
  fi
  echo "[ERROR] a pre-commit hook already exists at ${HOOK}." >&2
  echo "  It is NOT a Libro hook. Re-run with --force to overwrite, or merge manually." >&2
  exit 1
fi

cat > "$HOOK" <<'HOOKEOF'
#!/usr/bin/env bash
# Libro pre-commit hook (installed by scripts/install-git-hooks.sh).
# Thin shim — real logic lives in scripts/pre-commit-lint.sh (single source of truth).
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
LINT="${REPO_ROOT}/scripts/pre-commit-lint.sh"
[[ -x "$LINT" ]] || { echo "[libro-lint] scripts/pre-commit-lint.sh missing — skipping" >&2; exit 0; }
exec bash "$LINT"
HOOKEOF
chmod +x "$HOOK"

echo "[OK] Libro pre-commit guard installed → ${HOOK}"
echo "     It scans staged changes for secrets + PII on every commit."
echo "     Bypass once: LIBRO_SKIP_LINT=1 git commit ...   (or git commit --no-verify)"
