#!/usr/bin/env bash
# Libro pre-commit lint — operator-side secret + PII guard.
#
# Scans STAGED changes for credentials and personally-identifying data before
# they enter your git history. Libro scaffolds a brain you will likely version
# in git; this hook keeps your own API keys, private keys, and home paths from
# being committed by accident.
#
# This is operator-facing and fully generic: it ships zero Cerebro-specific
# values. It protects YOU, the Libro operator, not the Libro maintainers.
#
# Usage:
#   bash scripts/pre-commit-lint.sh            # scan staged changes (hook mode)
#   bash scripts/pre-commit-lint.sh --all      # scan the whole working tree
#   LIBRO_SKIP_LINT=1 git commit ...           # one-off bypass (also: git commit --no-verify)
#
# Exit: 0 = clean, 1 = findings (commit blocked in hook mode).
#
# No external dependencies (bash + git + grep only). Secrets are masked in
# output — the matched value is never reprinted in full.

set -uo pipefail

MODE="staged"
[[ "${1:-}" == "--all" ]] && MODE="all"

# Honor explicit bypass.
if [[ "${LIBRO_SKIP_LINT:-0}" == "1" ]]; then
  echo "[libro-lint] LIBRO_SKIP_LINT=1 — skipping scan" >&2
  exit 0
fi

# Colors (TTY only).
if [[ -t 2 ]]; then C_RED=$'\033[0;31m'; C_YEL=$'\033[0;33m'; C_GRN=$'\033[0;32m'; C_OFF=$'\033[0m'
else C_RED=''; C_YEL=''; C_GRN=''; C_OFF=''; fi

# --- Collect target files --------------------------------------------------
files=()
if [[ "$MODE" == "all" ]]; then
  while IFS= read -r -d '' f; do files+=("$f"); done \
    < <(git ls-files -z 2>/dev/null)
else
  # Added/copied/modified staged files only (skip deletions).
  while IFS= read -r -d '' f; do files+=("$f"); done \
    < <(git diff --cached --name-only --diff-filter=ACM -z 2>/dev/null)
fi

[[ ${#files[@]} -eq 0 ]] && exit 0

# --- Allowlist (example/template files carry placeholder secrets by design) -
_is_allowlisted() {
  case "$1" in
    *.example|*.example.*|*.template|*.sample|*.dist) return 0 ;;
    *.example.json|*.example.yaml|*.example.yml)      return 0 ;;
    profile.yaml.template|*.md.example)               return 0 ;;
  esac
  return 1
}

# Lines with obvious placeholders are not real secrets.
_is_placeholder() {
  printf '%s' "$1" | grep -qiE '\{\{|<[a-z_]+>|YOUR[_-]|CHANGE[_-]?ME|EXAMPLE|REDACTED|XXXXXX|placeholder|\bdummy\b|\bfake\b|0{8,}|x{8,}'
}

_mask() {
  # Show first 4 chars of the matched token, mask the rest.
  local s="$1"
  if [[ ${#s} -le 8 ]]; then printf '%s' "****"; else printf '%s…%s' "${s:0:4}" "[masked]"; fi
}

# --- Secret patterns (FAIL — block commit) ---------------------------------
# name|regex   — regex is grep -E (POSIX ERE).
SECRET_PATTERNS=(
  "Private key block|-----BEGIN [A-Z ]*PRIVATE KEY-----"
  "Anthropic API key|sk-ant-[A-Za-z0-9_-]{20,}"
  "OpenAI project key|sk-proj-[A-Za-z0-9_-]{20,}"
  "OpenAI key|sk-[A-Za-z0-9]{32,}"
  "AWS access key id|AKIA[0-9A-Z]{16}"
  "GitHub token|gh[pousr]_[A-Za-z0-9]{36,}"
  "Slack token|xox[baprs]-[A-Za-z0-9-]{10,}"
  "Google API key|AIza[0-9A-Za-z_-]{35}"
  "Generic secret assignment|(API[_-]?KEY|SECRET|ACCESS[_-]?TOKEN|AUTH[_-]?TOKEN|PASSWORD|PASSWD|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET)[\"' ]*[:=][\"' ]*[A-Za-z0-9_./+-]{16,}"
)

# --- PII / leakage patterns (WARN — surfaced, does not block) --------------
PII_PATTERNS=(
  "Absolute home path (leaks username)|/(Users|home)/[A-Za-z0-9._-]+/"
  "Tailscale/CGNAT IP|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}"
  "Email address|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

# --- Credential filenames staged (FAIL) ------------------------------------
_is_credential_filename() {
  local base; base="$(basename "$1")"
  case "$base" in
    .env|.env.*) [[ "$base" == *.example || "$base" == *.template || "$base" == *.sample ]] && return 1; return 0 ;;
    *.pem|*.key|*.p12|*.pfx|id_rsa|id_dsa|id_ecdsa|id_ed25519|.netrc|*.keystore) return 0 ;;
    *credential*|*credentials*) return 0 ;;
  esac
  return 1
}

fail=0
warn=0

for f in "${files[@]}"; do
  [[ -f "$f" ]] || continue

  # Credential filename gate (independent of content).
  if _is_credential_filename "$f"; then
    echo "${C_RED}[FAIL]${C_OFF} credential file staged: $f" >&2
    fail=$((fail + 1))
    continue
  fi

  _is_allowlisted "$f" && continue

  # Skip binary files.
  grep -Iq . "$f" 2>/dev/null || continue

  # Secret scan (FAIL).
  for entry in "${SECRET_PATTERNS[@]}"; do
    name="${entry%%|*}"; rx="${entry#*|}"
    while IFS= read -r hit; do
      [[ -z "$hit" ]] && continue
      lineno="${hit%%:*}"; rest="${hit#*:}"
      _is_placeholder "$rest" && continue
      token="$(printf '%s' "$rest" | grep -oE -e "$rx" | head -1)"
      echo "${C_RED}[FAIL]${C_OFF} ${name}: $f:${lineno} ($(_mask "$token"))" >&2
      fail=$((fail + 1))
    done < <(grep -nE -e "$rx" "$f" 2>/dev/null)
  done

  # PII scan (WARN).
  for entry in "${PII_PATTERNS[@]}"; do
    name="${entry%%|*}"; rx="${entry#*|}"
    while IFS= read -r hit; do
      [[ -z "$hit" ]] && continue
      lineno="${hit%%:*}"
      echo "${C_YEL}[WARN]${C_OFF} ${name}: $f:${lineno}" >&2
      warn=$((warn + 1))
    done < <(grep -nE -e "$rx" "$f" 2>/dev/null)
  done
done

echo >&2
if [[ $fail -gt 0 ]]; then
  echo "${C_RED}[libro-lint] BLOCKED:${C_OFF} ${fail} secret/credential finding(s), ${warn} PII warning(s)." >&2
  echo "  Remove the secret, or move it to ~/.cerebro/profile.yaml / an env var / a .env file (already gitignored)." >&2
  echo "  Intentional? Bypass once with:  LIBRO_SKIP_LINT=1 git commit ...   (or git commit --no-verify)" >&2
  exit 1
fi

if [[ $warn -gt 0 ]]; then
  echo "${C_YEL}[libro-lint] ${warn} PII warning(s)${C_OFF} — review above; commit allowed." >&2
else
  echo "${C_GRN}[libro-lint] clean${C_OFF} — no secrets or PII detected in scan." >&2
fi
exit 0
