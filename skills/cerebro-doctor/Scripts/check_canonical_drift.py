#!/usr/bin/env python3
"""
check_canonical_drift.py — Cerebro canonical-state lint extension for cerebro-doctor.

Three checks:
  1. fleet-dispatch version — DASHBOARD.md + root CLAUDE.md + master-brain/CLAUDE.md
     must all reference the same fleet-dispatch.json version number.
  2. FLEET_ROSTER path — same 3 files must reference the canonical roster path
     (master-brain/hardware-inventory/FLEET_ROSTER.md, not hardware-inventory/FLEET_ROSTER.md).
  3. Skill count — DASHBOARD.md skill-count claim vs actual SKILL.md count on disk.

Exit 0 always (advisory / Cron-able weekly check, never blocks).
Scope contract: read-only. Python stdlib only. No network.

Usage:
  python3 master-brain/skills/cerebro-doctor/Scripts/check_canonical_drift.py
  python3 master-brain/skills/cerebro-doctor/Scripts/check_canonical_drift.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Root detection (mirrors check_resolvable.py pattern)
# ---------------------------------------------------------------------------

def find_workspace_root(start: Path | None = None) -> Path:
    env = os.environ.get("CEREBRO_ROOT") or os.environ.get("CEREBRO_BRAIN_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "master-brain").exists():
            return p
        if p.name == "master-brain":
            return p.parent
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        if (parent / "master-brain").exists() and (parent / "CLAUDE.md").exists():
            return parent
    raise SystemExit("could not locate workspace root — set CEREBRO_ROOT")


# ---------------------------------------------------------------------------
# Check 1 — fleet-dispatch version consistency
# ---------------------------------------------------------------------------

# Match "fleet-dispatch.json v11" — skip version-transition arrows (v10→v11 history refs)
# (?!\d) prevents backtracking to partial digit match (v1 inside v10→)
_DISPATCH_VER_RE = re.compile(r"fleet-dispatch\.json[^v\n]*v(\d+)(?!\d)(?!\s*(?:\u2192|->))", re.IGNORECASE)
_DISPATCH_VER_SHORT_RE = re.compile(r"fleet-dispatch[^v\n]*v(\d+)(?!\d)(?!\s*(?:\u2192|->))", re.IGNORECASE)


def _extract_dispatch_version(text: str) -> str | None:
    m = _DISPATCH_VER_RE.search(text) or _DISPATCH_VER_SHORT_RE.search(text)
    return m.group(1) if m else None


def _get_actual_dispatch_version(state_dir: Path) -> str | None:
    """Read state/fleet-dispatch.json and return its version field."""
    dispatch_file = state_dir / "fleet-dispatch.json"
    if not dispatch_file.exists():
        return None
    try:
        data = json.loads(dispatch_file.read_text(encoding="utf-8"))
        ver = data.get("version") or data.get("v")
        return str(ver).lstrip("v") if ver else None
    except (json.JSONDecodeError, OSError):
        return None


def check_fleet_dispatch_version(workspace: Path) -> list[dict]:
    findings: list[dict] = []

    files_to_check = {
        "DASHBOARD.md": workspace / "master-brain" / "DASHBOARD.md",
        "CLAUDE.md (root)": workspace / "CLAUDE.md",
        "master-brain/CLAUDE.md": workspace / "master-brain" / "CLAUDE.md",
    }
    actual_ver = _get_actual_dispatch_version(workspace / "master-brain" / "state")

    versions: dict[str, str | None] = {}
    for label, path in files_to_check.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        versions[label] = _extract_dispatch_version(text)

    if actual_ver:
        for label, found_ver in versions.items():
            if found_ver is None:
                findings.append({
                    "check": "fleet-dispatch-version",
                    "severity": "WARN",
                    "file": label,
                    "reason": f"fleet-dispatch version reference not found (actual: v{actual_ver})",
                })
            elif found_ver != actual_ver:
                findings.append({
                    "check": "fleet-dispatch-version",
                    "severity": "DRIFT",
                    "file": label,
                    "reason": f"references v{found_ver} but fleet-dispatch.json = v{actual_ver}",
                })
    else:
        # Can't verify — check inter-file consistency instead
        unique_vers = set(v for v in versions.values() if v)
        if len(unique_vers) > 1:
            findings.append({
                "check": "fleet-dispatch-version",
                "severity": "WARN",
                "file": "cross-file",
                "reason": f"version references diverge across files: {sorted(unique_vers)}",
            })

    return findings


# ---------------------------------------------------------------------------
# Check 2 — FLEET_ROSTER path consistency
# ---------------------------------------------------------------------------

_ROSTER_PATH_CANONICAL = "master-brain/hardware-inventory/FLEET_ROSTER.md"
_ROSTER_BARE_RE = re.compile(r"(?<![/\w])hardware-inventory/FLEET_ROSTER\.md")
_ROSTER_CANONICAL_RE = re.compile(re.escape(_ROSTER_PATH_CANONICAL))


def check_fleet_roster_path(workspace: Path) -> list[dict]:
    findings: list[dict] = []
    files_to_check = {
        "DASHBOARD.md": workspace / "master-brain" / "DASHBOARD.md",
        "CLAUDE.md (root)": workspace / "CLAUDE.md",
        "master-brain/CLAUDE.md": workspace / "master-brain" / "CLAUDE.md",
    }
    for label, path in files_to_check.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # Check canonical path IS present
        has_canonical = bool(_ROSTER_CANONICAL_RE.search(text))
        # Check bare (drift) path is NOT present (would be wrong prefix)
        bare_hits = [
            m.group(0) for m in _ROSTER_BARE_RE.finditer(text)
            if not m.group(0).startswith("master-brain/")
        ]
        if not has_canonical:
            findings.append({
                "check": "fleet-roster-path",
                "severity": "WARN",
                "file": label,
                "reason": f"canonical path '{_ROSTER_PATH_CANONICAL}' not found",
            })
        if bare_hits:
            findings.append({
                "check": "fleet-roster-path",
                "severity": "DRIFT",
                "file": label,
                "reason": f"bare path reference 'hardware-inventory/FLEET_ROSTER.md' found (should be prefixed with master-brain/)",
            })
    return findings


# ---------------------------------------------------------------------------
# Check 3 — Skill count in DASHBOARD.md vs disk
# ---------------------------------------------------------------------------

_SKILL_COUNT_RE = re.compile(r"(\d+)\s+SKILL\.md", re.IGNORECASE)


def check_skill_count(workspace: Path) -> list[dict]:
    findings: list[dict] = []

    skills_dir = workspace / "master-brain" / "skills"
    if not skills_dir.exists():
        return findings

    actual_count = len(list(skills_dir.glob("*/SKILL.md")))

    dashboard = workspace / "master-brain" / "DASHBOARD.md"
    if not dashboard.exists():
        return findings

    text = dashboard.read_text(encoding="utf-8", errors="replace")
    m = _SKILL_COUNT_RE.search(text)
    if m:
        claimed = int(m.group(1))
        if claimed != actual_count:
            findings.append({
                "check": "skill-count",
                "severity": "DRIFT",
                "file": "DASHBOARD.md",
                "reason": f"claims {claimed} SKILL.md files but disk has {actual_count}",
            })
    else:
        findings.append({
            "check": "skill-count",
            "severity": "INFO",
            "file": "DASHBOARD.md",
            "reason": f"no skill count reference found in DASHBOARD.md (disk has {actual_count})",
        })

    return findings


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all(workspace: Path) -> list[dict]:
    findings: list[dict] = []
    findings.extend(check_fleet_dispatch_version(workspace))
    findings.extend(check_fleet_roster_path(workspace))
    findings.extend(check_skill_count(workspace))
    return findings


def _format_text(findings: list[dict]) -> str:
    if not findings:
        return "cerebro-doctor canonical-drift: CLEAN — 0 findings"
    d = sum(1 for f in findings if f["severity"] == "DRIFT")
    w = sum(1 for f in findings if f["severity"] == "WARN")
    i = sum(1 for f in findings if f["severity"] == "INFO")
    lines = [
        f"cerebro-doctor canonical-drift: {len(findings)} finding(s) "
        f"[{d} DRIFT / {w} WARN / {i} INFO]"
    ]
    for f in findings:
        lines.append(f"  [{f['severity']}] {f['check']} — {f['file']}: {f['reason']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Canonical-drift lint for cerebro-doctor (fleet-dispatch version, FLEET_ROSTER path, skill count)."
    )
    parser.add_argument(
        "--root", type=Path, default=None,
        help="Workspace root (default: auto-detect via CEREBRO_ROOT or script location)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Emit JSON array of findings to stdout",
    )
    args = parser.parse_args(argv)

    workspace = args.root or find_workspace_root()
    findings = run_all(workspace)

    if args.json_output:
        print(json.dumps(findings, indent=2))
    else:
        print(_format_text(findings))

    return 0  # always exit 0 — advisory


if __name__ == "__main__":
    sys.exit(main())
