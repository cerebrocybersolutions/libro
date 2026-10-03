#!/usr/bin/env python3
"""
lint.py — memory frontmatter attribution validator + auto-injector.

Enforces 11-key provenance contract on memory `.md` files per F5+M1 fix from
Codex head-to-toe audit 2026-05-21.

Exit codes:
  0 — pass (already conformant, no changes)
  1 — blocked (required keys missing, cannot auto-derive)
  2 — auto-injected (derivable keys filled in, write proceeds)
  3 — error (parse failure, file unreadable)

Usage:
  lint.py [--dry-run] [--quiet] <file.md>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print(json.dumps({"error": "PyYAML not installed", "exit": 3}), file=sys.stderr)
    sys.exit(3)

REQUIRED_KEYS = [
    "name",
    "description",
    "type",
    "source_surface",
    "host",
    "tool",
    "session_id",
    "written_at_utc",
    "source_path",
    "confidence",
    "lifecycle",
]

AUTO_DERIVABLE = {"source_surface", "host", "tool", "session_id", "written_at_utc"}
AUTHOR_REQUIRED = {"name", "description", "type", "source_path", "confidence", "lifecycle"}

VALID_TYPE = {"user", "feedback", "project", "reference"}
# Writer surface taxonomy:
#   - INTERACTIVE writers: cc, hermes, codex, claude-desktop
#   - AUTOMATED writers: pulsar, curator-cron, sessionend, hub-services
#   - unknown: legacy backfills with unrecoverable provenance
# Trust distinction (automated vs interactive) is first-class via the `automated`
# bool key (see VALID_AUTOMATED below).
VALID_SURFACE = {
    "cc", "hermes", "codex", "claude-desktop",
    "pulsar", "curator-cron", "sessionend", "hub-services",
    "unknown",
}
AUTOMATED_SURFACES = {"pulsar", "curator-cron", "sessionend", "hub-services"}
VALID_CONFIDENCE = {"high", "med", "low"}
LIFECYCLE_PATTERN = re.compile(r"^(permanent|pinned|active|archived|closed|superseded|stale-by:\d{4}-\d{2}-\d{2})$")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def derive_values() -> dict:
    """Auto-derive 5 environment-sourced keys."""
    return {
        "source_surface": os.environ.get("CLAUDE_SURFACE", "unknown"),
        "host": socket.gethostname().split(".")[0],
        "tool": os.environ.get("CLAUDE_TOOL", "unknown"),
        "session_id": os.environ.get("CLAUDE_SESSION_ID", "unknown"),
        "written_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """Returns (frontmatter_dict, body). frontmatter_dict=None if no frontmatter."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None, content
    try:
        fm = yaml.safe_load(m.group(1)) or {}
        if not isinstance(fm, dict):
            return None, content
        return fm, m.group(2)
    except yaml.YAMLError:
        return None, content


def serialize_frontmatter(fm: dict, body: str) -> str:
    """Reconstruct file with ordered frontmatter."""
    ordered = {k: fm[k] for k in REQUIRED_KEYS if k in fm}
    # Preserve any extra keys author added
    for k, v in fm.items():
        if k not in ordered:
            ordered[k] = v
    yaml_str = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{yaml_str}---\n{body}"


def validate_values(fm: dict) -> list[str]:
    """Return list of validation errors (empty if all valid)."""
    errors = []
    if fm.get("type") and fm["type"] not in VALID_TYPE:
        errors.append(f"type='{fm['type']}' not in {sorted(VALID_TYPE)}")
    if fm.get("source_surface") and fm["source_surface"] not in VALID_SURFACE:
        errors.append(f"source_surface='{fm['source_surface']}' not in {sorted(VALID_SURFACE)}")
    if fm.get("confidence") and fm["confidence"] not in VALID_CONFIDENCE:
        errors.append(f"confidence='{fm['confidence']}' not in {sorted(VALID_CONFIDENCE)}")
    if fm.get("lifecycle") and not LIFECYCLE_PATTERN.match(str(fm["lifecycle"])):
        errors.append(f"lifecycle='{fm['lifecycle']}' must match permanent|active|stale-by:YYYY-MM-DD")
    return errors


def lint_file(path: Path, dry_run: bool) -> tuple[int, dict]:
    """Lint single file. Returns (exit_code, report_dict)."""
    report = {"path": str(path), "action": None, "missing": [], "injected": [], "errors": []}

    if not path.exists():
        report["errors"].append("file not found")
        report["action"] = "error"
        return 3, report

    content = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    if fm is None:
        # No frontmatter — cannot auto-inject author-required keys
        report["missing"] = sorted(AUTHOR_REQUIRED)
        report["action"] = "blocked"
        report["errors"].append("no frontmatter present; author must provide name/description/type/source_path/confidence/lifecycle")
        return 1, report

    missing_author = sorted(AUTHOR_REQUIRED - set(fm.keys()))
    if missing_author:
        report["missing"] = missing_author
        report["action"] = "blocked"
        report["errors"].append(f"author-required keys missing: {missing_author}")
        return 1, report

    # All author keys present — auto-inject derivable
    missing_auto = AUTO_DERIVABLE - set(fm.keys())
    derived = derive_values()
    injected = {}
    for k in missing_auto:
        fm[k] = derived[k]
        injected[k] = derived[k]

    # Validate values
    validation_errors = validate_values(fm)
    if validation_errors:
        report["errors"] = validation_errors
        report["action"] = "blocked"
        return 1, report

    if not injected:
        report["action"] = "pass"
        return 0, report

    report["injected"] = list(injected.keys())
    report["action"] = "injected"

    if not dry_run:
        new_content = serialize_frontmatter(fm, body)
        path.write_text(new_content, encoding="utf-8")

    return 2, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="markdown file to lint")
    parser.add_argument("--dry-run", action="store_true", help="report only, no writes")
    parser.add_argument("--quiet", action="store_true", help="suppress stdout on pass")
    parser.add_argument("--json", action="store_true", help="emit JSON report on stderr")
    args = parser.parse_args()

    path = Path(args.file).resolve()
    exit_code, report = lint_file(path, args.dry_run)

    if args.json:
        print(json.dumps(report), file=sys.stderr)
    elif exit_code == 0 and args.quiet:
        pass
    else:
        status = {0: "[PASS]", 1: "[BLOCKED]", 2: "[INJECTED]", 3: "[ERROR]"}[exit_code]
        print(f"{status} {path.name}")
        if report["missing"]:
            print(f"  missing: {report['missing']}")
        if report["injected"]:
            print(f"  injected: {report['injected']}")
        if report["errors"]:
            for e in report["errors"]:
                print(f"  error: {e}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
