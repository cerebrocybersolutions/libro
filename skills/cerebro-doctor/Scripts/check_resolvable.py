#!/usr/bin/env python3
"""
check_resolvable.py — Cerebro skill-system meta-audit.

Three checks:
  1. Reachability    — every active SKILL.md has at least one AGENTS.md row
  2. Orphan phrases  — every AGENTS.md row points at an existing (non-archived) skill
  3. DRY overlap     — no two active skills claim the same trigger substring

Exit codes:
  0 = clean
  1 = reachability drift (unreachable skill or orphan phrase)
  2 = DRY overlap found
  3 = both reachability + DRY drift

Workflow-as-product adoption helper. See operator's decision log for parent context.

Scope contract: read-only. Python stdlib only. No network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable


# ---------- root detection ----------

def find_brain_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or this file) until we find a master-brain dir."""
    env = os.environ.get("CEREBRO_BRAIN_ROOT") or os.environ.get("CEREBRO_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "master-brain").exists():
            return p / "master-brain"
        if p.name == "master-brain":
            return p
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        candidate = parent / "master-brain"
        if candidate.exists() and (candidate / "AGENTS.md").exists():
            return candidate
        if parent.name == "master-brain" and (parent / "AGENTS.md").exists():
            return parent
    raise SystemExit("could not locate master-brain/ — set CEREBRO_BRAIN_ROOT")


# ---------- SKILL.md parsing ----------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_skill(skill_md: Path) -> dict:
    """Parse SKILL.md frontmatter into a shallow dict. No YAML dep; handles the
    subset Cerebro actually uses (single-line and folded '>') description)."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        return {"__parse_error__": f"read failed: {e}"}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {"__parse_error__": "no frontmatter block"}
    raw = m.group(1)
    out: dict = {}
    key = None
    buf: list[str] = []
    for line in raw.splitlines():
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_\-]*:", line):
            if key is not None:
                out[key] = " ".join(s.strip() for s in buf).strip()
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest in ("", ">", ">-", "|", "|-"):
                buf = []
            else:
                buf = [rest]
        else:
            buf.append(line.strip())
    if key is not None:
        out[key] = " ".join(s.strip() for s in buf).strip()
    out["__path__"] = str(skill_md)
    return out


# ---------- AGENTS.md parsing ----------

def load_agents(agents_md: Path) -> list[dict]:
    """Parse the resolver table block. Pipe-separated rows inside ``` fences.
    Ignores comments and lines outside code fences."""
    try:
        text = agents_md.read_text(encoding="utf-8")
    except Exception as e:
        raise SystemExit(f"AGENTS.md read failed: {e}")
    rows: list[dict] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        if not stripped or stripped.startswith("#"):
            continue
        parts = [p.strip() for p in stripped.split("|")]
        if len(parts) < 4:
            continue
        phrase, skill = parts[0], parts[1]
        # Skip format-doc placeholders like <intent-phrase>|<skill-name>|...
        if phrase.startswith("<") or skill.startswith("<"):
            continue
        rows.append({
            "phrase": phrase,
            "skill": skill,
            "scope": parts[2],
            "why": "|".join(parts[3:]),
        })
    return rows


# ---------- trigger extraction ----------

TRIGGER_HINT_RE = re.compile(
    r"(?:trigger(?:s)? on|try(?::)?|use when|activates on|fires on|invoke when)[:\s]+",
    re.IGNORECASE,
)


def extract_candidate_triggers(description: str) -> list[str]:
    """Pull quoted phrases OR phrases after Trigger-hint verbs from a
    description string. Multi-word only (>= 2 words) to dampen false positives."""
    if not description:
        return []
    phrases: list[str] = []
    for m in re.finditer(r'"([^"]{4,80})"', description):
        phrases.append(m.group(1).lower().strip())
    for m in re.finditer(r"'([^']{4,80})'", description):
        phrases.append(m.group(1).lower().strip())
    hint = TRIGGER_HINT_RE.search(description)
    if hint:
        tail = description[hint.end():]
        for chunk in re.split(r"[.;]", tail[:400]):
            chunk = chunk.strip().lower()
            if len(chunk.split()) >= 2 and len(chunk) <= 80:
                phrases.append(chunk)
    return [p for p in phrases if len(p.split()) >= 2]


# ---------- checks ----------

def run_checks(brain_root: Path) -> dict:
    skills_dir = brain_root / "skills"
    agents_md = brain_root / "AGENTS.md"
    archive_dir = skills_dir / "_archive"

    active_skills: dict[str, dict] = {}
    parse_errors: list[dict] = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        if name.startswith("_") or name.startswith("."):
            continue
        parsed = load_skill(skill_md)
        if "__parse_error__" in parsed:
            parse_errors.append({"skill": name, "error": parsed["__parse_error__"]})
            continue
        active_skills[name] = parsed

    archived: set[str] = set()
    if archive_dir.exists():
        for p in archive_dir.glob("*"):
            if p.is_dir():
                archived.add(p.name)

    agents_rows = load_agents(agents_md)
    referenced_skills = {r["skill"] for r in agents_rows}
    rows_by_skill: dict[str, list[dict]] = {}
    for r in agents_rows:
        rows_by_skill.setdefault(r["skill"], []).append(r)

    unreachable = [s for s in active_skills if s not in referenced_skills]
    orphan_rows = [
        r for r in agents_rows
        if r["skill"] not in active_skills and r["skill"] not in archived
    ]
    archived_rows = [r for r in agents_rows if r["skill"] in archived]

    phrase_owners: dict[str, list[str]] = {}
    for name, parsed in active_skills.items():
        desc = parsed.get("description", "")
        for phrase in set(extract_candidate_triggers(desc)):
            phrase_owners.setdefault(phrase, []).append(name)
    dry_overlap = [
        {"phrase": p, "skills": sorted(set(owners))}
        for p, owners in phrase_owners.items()
        if len(set(owners)) > 1
    ]

    return {
        "brain_root": str(brain_root),
        "active_skill_count": len(active_skills),
        "agents_row_count": len(agents_rows),
        "unreachable_skills": sorted(unreachable),
        "orphan_rows": orphan_rows,
        "archived_rows": archived_rows,
        "dry_overlap": dry_overlap,
        "parse_errors": parse_errors,
    }


# ---------- reporting ----------

def print_human(report: dict, quiet: bool = False) -> None:
    root = report["brain_root"]
    reach_drift = bool(report["unreachable_skills"]) or bool(report["orphan_rows"])
    dry_drift = bool(report["dry_overlap"])
    parse_drift = bool(report["parse_errors"])

    if quiet and not (reach_drift or dry_drift or parse_drift):
        return

    print(f"cerebro-doctor — {root}")
    print(f"  active skills: {report['active_skill_count']}   "
          f"AGENTS.md rows: {report['agents_row_count']}")
    print()

    if report["parse_errors"]:
        print("PARSE ERRORS:")
        for e in report["parse_errors"]:
            print(f"  - {e['skill']}: {e['error']}")
        print()

    print("Check 1 — Reachability")
    if report["unreachable_skills"]:
        print(f"  FAIL — {len(report['unreachable_skills'])} skill(s) have no AGENTS.md row:")
        for s in report["unreachable_skills"]:
            print(f"    - {s}")
    else:
        print("  PASS")
    print()

    print("Check 2 — Orphan phrases")
    if report["orphan_rows"]:
        print(f"  FAIL — {len(report['orphan_rows'])} row(s) point at missing skills:")
        for r in report["orphan_rows"]:
            print(f"    - '{r['phrase']}' → {r['skill']}  (does not exist)")
    else:
        print("  PASS")
    if report["archived_rows"]:
        print(f"  INFO — {len(report['archived_rows'])} row(s) point at _archive/ skills (not a fail, but stale):")
        for r in report["archived_rows"]:
            print(f"    - '{r['phrase']}' → {r['skill']}  (archived)")
    print()

    print("Check 3 — DRY overlap")
    if report["dry_overlap"]:
        print(f"  FAIL — {len(report['dry_overlap'])} phrase(s) claimed by multiple skills:")
        for row in report["dry_overlap"]:
            print(f"    - '{row['phrase']}' → {', '.join(row['skills'])}")
        print("    Fix: add discriminator row in AGENTS.md (Known DRY pairs), or narrow SKILL.md descriptions.")
    else:
        print("  PASS")
    print()

    verdict = "CLEAN"
    if reach_drift and dry_drift:
        verdict = "DRIFT (reachability + DRY)"
    elif reach_drift:
        verdict = "DRIFT (reachability)"
    elif dry_drift:
        verdict = "DRIFT (DRY)"
    print(f"Verdict: {verdict}")


def exit_code(report: dict) -> int:
    reach = bool(report["unreachable_skills"]) or bool(report["orphan_rows"])
    dry = bool(report["dry_overlap"])
    if reach and dry:
        return 3
    if reach:
        return 1
    if dry:
        return 2
    return 0


# ---------- CLI ----------

def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cerebro skill-system meta-audit")
    parser.add_argument("--root", type=Path, default=None,
                        help="path to master-brain/ (default: auto-detect via CEREBRO_BRAIN_ROOT or script location)")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress output when verdict is CLEAN")
    args = parser.parse_args(argv)

    brain_root = args.root or find_brain_root()
    if not (brain_root / "AGENTS.md").exists():
        raise SystemExit(f"AGENTS.md not found under {brain_root} — is Phase 2 Block 2 landed?")

    report = run_checks(brain_root)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print_human(report, quiet=args.quiet)

    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
