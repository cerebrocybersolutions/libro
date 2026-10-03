#!/usr/bin/env python3
"""
backfill.py — bulk-backfill memory files with 8-key F5+M1 attribution.

Scans Claude Code + workspace memory dirs, injects 8 attribution keys with
conservative defaults (confidence=med, lifecycle=active,
source_path=backfill-2026-05-21).
Preserves existing frontmatter (name/description/type). Idempotent — skips
already-conformant files.

Usage:
  backfill.py [--dry-run] [--execute]

Defaults to dry-run. Pass --execute to write.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required", file=sys.stderr)
    sys.exit(3)

# Memory dirs scanned — derived from $PWD (workspace root) and Claude Code project encoding.
# Override with MEMORY_DIRS env var (colon-separated list) if your install differs.
def _default_memory_dirs():
    env = os.environ.get("MEMORY_DIRS")
    if env:
        return [Path(p) for p in env.split(":") if p]
    workspace = Path(os.environ.get("WORKSPACE_ROOT") or os.getcwd()).resolve()
    cc_slug = str(workspace).replace("/", "-")
    return [
        Path.home() / ".claude" / "projects" / cc_slug / "memory",
    ]

MEMORY_DIRS = _default_memory_dirs()

# MEMORY.md is the index file, not a memory entry — skip it
SKIP_FILES = {"MEMORY.md"}

REQUIRED_KEYS = [
    "name", "description", "type",
    "source_surface", "host", "tool", "session_id", "written_at_utc",
    "source_path", "confidence", "lifecycle",
]

BACKFILL_TAG = "backfill-2026-05-21"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def derive_surface(path: Path) -> str:
    """Derive source_surface from file path."""
    p = str(path)
    if "/.claude/projects/" in p:
        return "cc"
    return "unknown"


def file_mtime_iso(path: Path) -> str:
    """File mtime as ISO 8601 UTC."""
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except OSError:
        return datetime.now(timezone.utc).isoformat()


def git_first_commit_iso(path: Path) -> str | None:
    """First git commit timestamp for this file (more accurate provenance than mtime)."""
    try:
        result = subprocess.run(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%aI", "--", str(path)],
            capture_output=True, text=True, timeout=10, cwd=path.parent,
        )
        if result.returncode == 0:
            lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            if lines:
                return lines[-1]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def backfill_keys(path: Path) -> dict:
    """Generate 8 backfill keys with conservative defaults."""
    written_at = git_first_commit_iso(path) or file_mtime_iso(path)
    return {
        "source_surface": derive_surface(path),
        "host": socket.gethostname().split(".")[0],
        "tool": BACKFILL_TAG,
        "session_id": BACKFILL_TAG,
        "written_at_utc": written_at,
        "source_path": BACKFILL_TAG,
        "confidence": "med",
        "lifecycle": "active",
    }


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
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
    ordered = {k: fm[k] for k in REQUIRED_KEYS if k in fm}
    for k, v in fm.items():
        if k not in ordered:
            ordered[k] = v
    yaml_str = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{yaml_str}---\n{body}"


def process_file(path: Path, execute: bool) -> dict:
    """Returns report dict for single file."""
    report = {"path": str(path), "action": "skip", "reason": None, "added": []}

    if path.name in SKIP_FILES:
        report["reason"] = "index file"
        return report

    content = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)

    if fm is None:
        report["action"] = "error"
        report["reason"] = "no frontmatter — manual review required"
        return report

    # Legacy migration: old key `surface` → `source_surface`
    if "surface" in fm and "source_surface" not in fm:
        old_surface = fm.pop("surface")
        # Map legacy values to taxonomy
        if old_surface in ("cc-cli-local", "cc"):
            fm["source_surface"] = "cc"
        elif old_surface in ("hermes",):
            fm["source_surface"] = "hermes"
        else:
            fm["source_surface"] = "unknown"

    # Coerce datetime objects to ISO strings (yaml.safe_load auto-parses ISO 8601 to datetime)
    for k in ("written_at_utc",):
        if k in fm and not isinstance(fm[k], str):
            fm[k] = fm[k].isoformat() if hasattr(fm[k], "isoformat") else str(fm[k])

    backfill = backfill_keys(path)
    added = {k: v for k, v in backfill.items() if k not in fm}

    if not added and "surface" not in str(content):
        report["reason"] = "already conformant"
        return report

    for k, v in added.items():
        fm[k] = v

    report["action"] = "backfilled"
    report["added"] = list(added.keys())

    if execute:
        new_content = serialize_frontmatter(fm, body)
        path.write_text(new_content, encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="actually write changes (default is dry-run)")
    parser.add_argument("--json", action="store_true", help="emit JSON report on stderr")
    args = parser.parse_args()

    execute = args.execute

    counts = {"backfilled": 0, "skip": 0, "error": 0}
    reports = []

    for mem_dir in MEMORY_DIRS:
        if not mem_dir.exists():
            print(f"[WARN] memory dir missing: {mem_dir}", file=sys.stderr)
            continue
        for md_path in sorted(mem_dir.glob("*.md")):
            r = process_file(md_path, execute)
            counts[r["action"]] = counts.get(r["action"], 0) + 1
            reports.append(r)

    mode = "EXECUTE" if execute else "DRY-RUN"
    print(f"[{mode}] backfilled={counts.get('backfilled', 0)} skipped={counts.get('skip', 0)} errors={counts.get('error', 0)}")

    # Print errors + first 5 backfills for review
    errors = [r for r in reports if r["action"] == "error"]
    if errors:
        print("\nERRORS (manual review required):")
        for r in errors[:10]:
            print(f"  {r['path']}: {r['reason']}")

    if args.json:
        print(json.dumps(reports, indent=2), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
