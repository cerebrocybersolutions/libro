#!/usr/bin/env python3
"""
doctor.py — customer-facing health check for an installed Libro target.

Auto-detects the install target by walking up from this script's location to
find `.libro-manifest.json`. For each skill + scaffold path declared in the
manifest, verifies presence on disk. Reports `cerebro-doctor: HEALTHY` if all
checks pass; lists deltas otherwise.

This is the stable customer entry point documented in README, CONTRIBUTING.md,
the install-smoke workflow, and the issue templates. Source-tree auditing
(reachability, DRY overlap, canonical drift) lives in the sibling scripts
`check_resolvable.py` + `check_canonical_drift.py` and is run by maintainers,
not customers.

Exit codes:
  0 = HEALTHY
  1 = missing skill(s) or scaffold file(s)
  2 = cannot locate `.libro-manifest.json` (not an installed target)
  3 = manifest unreadable or malformed

Override target detection with `LIBRO_TARGET=/path/to/target`.

Scope contract: read-only. Python stdlib only. No network.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def find_target() -> Path | None:
    """Locate the install target by env override, then by walking up from this
    script looking for `.libro-manifest.json` at increasing parent depths."""
    env = os.environ.get("LIBRO_TARGET")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / ".libro-manifest.json").exists():
            return p
        return None
    here = Path(__file__).resolve()
    # Installed layout: <target>/.claude/skills/cerebro-doctor/Scripts/doctor.py
    # parents[0]=Scripts, [1]=cerebro-doctor, [2]=skills, [3]=.claude, [4]=<target>
    for parent in here.parents:
        if (parent / ".libro-manifest.json").exists():
            return parent
    return None


def check(target: Path) -> tuple[int, list[str]]:
    """Read manifest, verify every declared skill + scaffold path exists.
    Returns (exit_code, [error_lines])."""
    manifest_path = target / ".libro-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return 3, [f"manifest read failed: {exc}"]

    errors: list[str] = []
    skills_dir = target / ".claude" / "skills"
    skill_count = 0
    for skill_name in manifest.get("installed_skills") or manifest.get("skills") or []:
        skill_count += 1
        path = skills_dir / skill_name
        if not path.exists():
            errors.append(f"missing skill: {skill_name}")
        elif not (path / "SKILL.md").exists():
            errors.append(f"skill has no SKILL.md: {skill_name}")

    scaffold_count = 0
    for rel in manifest.get("installed_scaffold") or manifest.get("scaffold_files") or []:
        scaffold_count += 1
        path = target / rel
        if not path.exists():
            errors.append(f"missing scaffold file: {rel}")

    if errors:
        return 1, errors
    return 0, [f"skills={skill_count} scaffold={scaffold_count}"]


def main() -> int:
    target = find_target()
    if target is None:
        print(
            "cerebro-doctor: cannot locate .libro-manifest.json. "
            "Run from an installed target, or set LIBRO_TARGET=/path/to/target.",
            file=sys.stderr,
        )
        return 2
    rc, lines = check(target)
    if rc == 0:
        stat = lines[0] if lines else ""
        print(f"cerebro-doctor: HEALTHY ({stat})")
    else:
        print(f"cerebro-doctor: DRIFT ({len(lines)} issue(s)) in {target}", file=sys.stderr)
        for line in lines:
            print(f"  - {line}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
