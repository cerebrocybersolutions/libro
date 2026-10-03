#!/usr/bin/env bash
# install-failure-paths.sh: acceptance tests for the installer's failure branches.
#
# The happy path is covered by the install-smoke workflow. This file proves the
# other side: when the install record cannot be written, is missing, empty, or
# stale, or a profile would install an excluded path, the installer and both
# doctors refuse or say NOT VERIFIED instead of reporting HEALTHY. It also proves
# a dry run writes nothing, not even the log, and that a stale Scripts/ layout is
# caught and then migrated.
#
# Every case runs in a throwaway root with HOME and TMPDIR pointed inside it, so
# nothing outside that root is touched.
#
# Usage: bash tests/install-failure-paths.sh      (exit 0 = all cases pass)

set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(mktemp -d)"
ROOT="$(cd "${ROOT}" && pwd -P)"
export HOME="${ROOT}/home"
export TMPDIR="${ROOT}/tmp"
mkdir -p "${HOME}" "${TMPDIR}"
PASS=0
FAIL=0

ok()   { echo "PASS  $*"; PASS=$((PASS + 1)); }
bad()  { echo "FAIL  $*"; FAIL=$((FAIL + 1)); }
run_install() { bash "${REPO}/install.sh" "$@" > "${ROOT}/last.out" 2>&1; echo $?; }
doctor_py()   { python3 "$1/.claude/skills/cerebro-doctor/scripts/doctor.py" > "${ROOT}/doctor.out" 2>&1; echo $?; }
doctor_sh()   { bash "${REPO}/install.sh" --doctor --target "$1" > "${ROOT}/doctor.out" 2>&1; echo $?; }
mentions()    { grep -q -- "$1" "$2"; }

echo "# libro install failure-path tests (root: ${ROOT})"

# --- T1 positive control: fresh libro-starter install is HEALTHY -----------------
T="${ROOT}/t1/brain"
rc="$(run_install --profile libro-starter --target "${T}")"
if [ "${rc}" = "0" ] && [ "$(doctor_py "${T}")" = "0" ] && mentions "HEALTHY" "${ROOT}/doctor.out"; then
    ok "T1 fresh libro-starter install exits 0 and doctor.py is HEALTHY"
else
    bad "T1 fresh install: install rc=${rc}"; cat "${ROOT}/last.out" "${ROOT}/doctor.out"
fi

# --- T2 missing install record is never HEALTHY ---------------------------------
cp -R "${ROOT}/t1" "${ROOT}/t2"; T="${ROOT}/t2/brain"
rm -f "${T}/.libro-manifest.json"
d1="$(doctor_py "${T}")"; d2="$(doctor_sh "${T}")"
if [ "${d1}" != "0" ] && [ "${d2}" != "0" ] && mentions "MISSING install record" "${ROOT}/doctor.out"; then
    ok "T2 missing record: doctor.py exit ${d1}, install.sh --doctor exit ${d2} (MISSING install record)"
else
    bad "T2 missing record: doctor.py=${d1} install.sh --doctor=${d2}"; cat "${ROOT}/doctor.out"
fi

# --- T3 empty install record is never HEALTHY -----------------------------------
cp -R "${ROOT}/t1" "${ROOT}/t3"; T="${ROOT}/t3/brain"
echo '{"profile": "libro-starter", "version": "0.3.0-alpha", "installed_skills": []}' > "${T}/.libro-manifest.json"
d1="$(doctor_py "${T}")"; d2="$(doctor_sh "${T}")"
if [ "${d1}" = "3" ] && [ "${d2}" != "0" ] && mentions "lists no installed skills" "${ROOT}/doctor.out"; then
    ok "T3 empty record: doctor.py exit 3 (NOT VERIFIED), install.sh --doctor exit ${d2}"
else
    bad "T3 empty record: doctor.py=${d1} install.sh --doctor=${d2}"; cat "${ROOT}/doctor.out"
fi

# --- T4 failed manifest write: install says INSTALL INCOMPLETE and exits non-zero --
T="${ROOT}/t4/brain"
mkdir -p "${T}/.libro-manifest.json"     # a directory where the record file must go: the write fails
rc="$(run_install --profile libro-core --target "${T}")"
d1="$(doctor_py "${T}")"; d2="$(doctor_sh "${T}")"
if [ "${rc}" = "3" ] && mentions "INSTALL INCOMPLETE" "${ROOT}/last.out" && [ "${d1}" != "0" ] && [ "${d2}" != "0" ]; then
    ok "T4 failed record write: install exit 3 (INSTALL INCOMPLETE); doctor.py exit ${d1}; install.sh --doctor exit ${d2}"
else
    bad "T4 failed record write: install=${rc} doctor.py=${d1} install.sh --doctor=${d2}"; cat "${ROOT}/last.out"
fi

# --- T5 excluded path in a profile: refused before anything is written ------------
R5="${ROOT}/t5-repo"
mkdir -p "${R5}"
(cd "${REPO}" && tar -cf - --exclude=.git .) | (cd "${R5}" && tar -xf -)
mkdir -p "${R5}/scaffold/tools"
echo "should never ship" > "${R5}/scaffold/tools/leak.md"
python3 - "${R5}/manifests" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
m = json.loads((d / "libro-ops.json").read_text())
m["name"] = "libro-exclusiontest"
m["additive_modules"]["brain_scaffold"] = ["tools/leak.md"]
(d / "libro-exclusiontest.json").write_text(json.dumps(m, indent=2))
PY
T="${ROOT}/t5/brain"
bash "${R5}/install.sh" --profile libro-exclusiontest --target "${T}" > "${ROOT}/last.out" 2>&1; rc=$?
if [ "${rc}" != "0" ] && mentions "EXCLUSION VIOLATION" "${ROOT}/last.out" && [ ! -e "${T}" ]; then
    ok "T5a profile installing tools/leak.md: refused (exit ${rc}, EXCLUSION VIOLATION), target never created"
else
    bad "T5a exclusion gate: rc=${rc}, target exists: $([ -e "${T}" ] && echo yes || echo no)"; cat "${ROOT}/last.out"
fi
# Second line of defense: the record writer itself refuses (exit 4) and writes nothing.
mkdir -p "${ROOT}/t5b"
python3 "${REPO}/lib/distribution.py" writeback --target "${ROOT}/t5b" --manifests-dir "${REPO}/manifests" \
    --profile libro-core --installed-skills "brain-setup" --installed-scaffold "tools/leak.md" > "${ROOT}/last.out" 2>&1; rc=$?
if [ "${rc}" = "4" ] && [ ! -e "${ROOT}/t5b/.libro-manifest.json" ]; then
    ok "T5b writeback with an excluded path: exit 4, no install record written"
else
    bad "T5b writeback: rc=${rc}"; cat "${ROOT}/last.out"
fi

# --- T6 operator-owned excluded path: left alone, reported, recorded --------------
T="${ROOT}/t6/brain"
mkdir -p "${T}/tools"; echo "mine" > "${T}/tools/mine.txt"
rc="$(run_install --profile libro-core --target "${T}")"
rec="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('user_owned_excluded_paths_present'))" "${T}/.libro-manifest.json" 2>/dev/null)"
if [ "${rc}" = "0" ] && mentions "NOTE: 1 excluded path" "${ROOT}/last.out" && [ "${rec}" = "['tools']" ] \
   && [ "$(cat "${T}/tools/mine.txt")" = "mine" ]; then
    ok "T6 operator-owned tools/: install exit 0, NOTE reported, recorded as user_owned_excluded_paths_present, file untouched"
else
    bad "T6 operator-owned excluded path: rc=${rc} rec=${rec}"; cat "${ROOT}/last.out"
fi

# --- T7 dry run writes nothing: no target, no log, no leftover temp files ---------
T="${ROOT}/t7/brain"
rm -f "${HOME}/.cerebro-install.log"
rm -rf "${TMPDIR:?}"/* "${TMPDIR:?}"/.[!.]* 2>/dev/null
rc="$(run_install --profile libro-starter --target "${T}" --dry-run)"
left="$(find "${TMPDIR}" -mindepth 1 | wc -l | tr -d ' ')"
if [ "${rc}" = "0" ] && [ ! -e "${T}" ] && [ ! -e "${ROOT}/t7" ] && [ ! -e "${HOME}/.cerebro-install.log" ] && [ "${left}" = "0" ]; then
    ok "T7 dry run: exit 0, no target, no ~/.cerebro-install.log, 0 temp files left"
else
    bad "T7 dry run: rc=${rc} target=$([ -e "${T}" ] && echo yes || echo no) log=$([ -e "${HOME}/.cerebro-install.log" ] && echo yes || echo no) tmp_left=${left}"
fi

# --- T8 install record behind this checkout: doctor says so -----------------------
cp -R "${ROOT}/t1" "${ROOT}/t8"; T="${ROOT}/t8/brain"
python3 - "${T}/.libro-manifest.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["version"] = "0.2.0-alpha"; open(p, "w").write(json.dumps(d))
PY
d2="$(doctor_sh "${T}")"
if [ "${d2}" != "0" ] && mentions "BEHIND install record says libro-starter 0.2.0-alpha" "${ROOT}/doctor.out"; then
    ok "T8 record behind checkout: install.sh --doctor exit ${d2} with an upgrade hint"
else
    bad "T8 stale record: install.sh --doctor=${d2}"; cat "${ROOT}/doctor.out"
fi

# --- T9 stale Scripts/ layout: caught by both doctors, then migrated --------------
cp -R "${ROOT}/t1" "${ROOT}/t9"; T="${ROOT}/t9/brain"
S="${T}/.claude/skills/cerebro-doctor"
mv "${S}/scripts" "${S}/scripts-tmp" && mv "${S}/scripts-tmp" "${S}/Scripts"   # two steps: works where case is ignored
d1="$(python3 "${S}/Scripts/doctor.py" > "${ROOT}/doctor.out" 2>&1; echo $?)"
c1="$(grep -c 'stale pre-0.3.0 layout: cerebro-doctor/Scripts' "${ROOT}/doctor.out")"
d2="$(doctor_sh "${T}")"
c2="$(grep -c 'stale folder name: cerebro-doctor/Scripts' "${ROOT}/doctor.out")"
rc="$(run_install --target "${T}")"
names="$(ls "${S}" | tr '\n' ' ')"
d3="$(doctor_py "${T}")"
if [ "${d1}" = "1" ] && [ "${c1}" = "1" ] && [ "${d2}" != "0" ] && [ "${c2}" = "1" ] && [ "${rc}" = "0" ] \
   && ls "${S}" | grep -qx scripts && ! ls "${S}" | grep -qx Scripts && [ "${d3}" = "0" ]; then
    ok "T9 stale Scripts/: doctor.py exit 1 and install.sh --doctor exit ${d2} flag it; re-install migrates (${names}); HEALTHY"
else
    bad "T9 stale layout: doctor.py=${d1}/${c1} install.sh --doctor=${d2}/${c2} reinstall=${rc} names=${names} after=${d3}"
    cat "${ROOT}/last.out"
fi

echo "# ${PASS} passed, ${FAIL} failed"
rm -rf "${ROOT}"
[ "${FAIL}" -eq 0 ]
