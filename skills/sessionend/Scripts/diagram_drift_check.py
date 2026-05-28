#!/usr/bin/env python3
"""
diagram_drift_check.py — scan diagram tiles + decision docs for drift.

Closes:
  - 2026-05-19 ops session open loop "Diagram drift-tag automation — sessionend
    probe stale last_verified on touched components"
  - 2026-05-21 Phase 2 F8 (t_11e7f21a) — Diagram-First Doctrine #14 inline
    diagram presence check on decision docs

Two checks:

  CHECK 1 — Tile staleness (original):
    - Iterate master-brain/diagrams/tiles/*.html
    - Parse `Last verified: YYYY-MM-DD` from header span
    - Extract referenced source file paths from <code>...</code> blocks
    - For each existing referenced file, check mtime vs last_verified date
    - If any referenced file mtime > last_verified date → tile is drifted

  CHECK 2 — Decision-doc inline diagram (Phase 2 F8, 2026-05-21):
    - Iterate master-brain/decisions/*.md (recent N days only — capped to reduce noise)
    - Probe each for inline diagram block under '## Why' (ASCII block / mermaid /
      <img>) per Diagram-First Doctrine #14
    - Skip single-file change docs (heuristic: doc body < 60 lines)
    - Emit WARN count per missing-diagram finding

Output (always stdout, exit 0):
  [DRIFT] diagram-tags:  OK | N drifted (tile-stale=X decision-no-diagram=Y)

  Verbose mode (--verbose):
    list each drifted item + reason

Stdlib only. Exit 0 always — advisory, never blocks sessionend.

Reversibility #5: pure read-only probe. No mutations.
Observability #6: emits [M/N] heartbeat when scanning >50 decisions.
"""
import argparse
import re
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
TILES_DIR = WORKSPACE / "master-brain" / "diagrams" / "tiles"
DECISIONS_DIR = WORKSPACE / "master-brain" / "decisions"

# Doctrine #14 default scan window: 30 days back (configurable via --decision-days).
# Older decisions are accepted as-is (legacy pre-doctrine — Reversibility #5 protects them).
DEFAULT_DECISION_DAYS = 30

# Heuristic: doc body shorter than this = single-file change, exempt from Doctrine #14.
SINGLE_CHANGE_LINE_THRESHOLD = 60

# Inline diagram detection: ASCII box-drawing chars / mermaid fence / SVG / image embed.
DIAGRAM_PATTERNS = (
    re.compile(r"```(?:mermaid|ascii|diagram|d2)", re.IGNORECASE),
    re.compile(r"[│┌┐└┘├┤┬┴┼─━┃┏┓┗┛┣┫┳┻╋]"),  # box-drawing
    re.compile(r"<img\s+[^>]*src=", re.IGNORECASE),
    re.compile(r"<svg\b", re.IGNORECASE),
    re.compile(r"!\[[^\]]*\]\([^)]+\.(png|jpg|jpeg|svg|gif)\)", re.IGNORECASE),
)

# Date regex: matches "Last verified: 2026-05-19" inside <span> or text
DATE_RE = re.compile(r"Last verified:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)

# Code block regex: captures inside <code>...</code>
CODE_RE = re.compile(r"<code[^>]*>([^<]+)</code>")

# Path heuristic: must contain '/' and either dot-extension or no spaces
PATH_HEURISTIC = re.compile(r"^[a-zA-Z0-9_./\-]+/[a-zA-Z0-9_./\-]+$")


def parse_tile(tile_path: Path):
    """Return (last_verified_date or None, list of referenced paths)."""
    try:
        text = tile_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None, []

    m = DATE_RE.search(text)
    last_verified = None
    if m:
        try:
            last_verified = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            last_verified = None

    refs = []
    for code_content in CODE_RE.findall(text):
        candidate = code_content.strip()
        # Strip leading slash for workspace-relative paths
        if candidate.startswith("/"):
            continue  # absolute paths skipped (likely runtime, not source)
        if PATH_HEURISTIC.match(candidate) and "." in candidate:
            refs.append(candidate)
    return last_verified, refs


def check_tile(tile_path: Path):
    """Return None if tile is OK, else dict describing drift."""
    last_verified, refs = parse_tile(tile_path)
    if last_verified is None:
        return None  # no date claim, can't compare

    newest_ref_mtime = None
    triggering_ref = None
    for ref in refs:
        # Try workspace-root then master-brain/-relative (tiles use both styles)
        candidates = [WORKSPACE / ref, WORKSPACE / "master-brain" / ref]
        ref_path = next((c for c in candidates if c.exists()), None)
        if ref_path is None:
            continue
        mtime = date.fromtimestamp(ref_path.stat().st_mtime)
        if newest_ref_mtime is None or mtime > newest_ref_mtime:
            newest_ref_mtime = mtime
            triggering_ref = ref

    if newest_ref_mtime and newest_ref_mtime > last_verified:
        return {
            "tile": tile_path.name,
            "last_verified": last_verified.isoformat(),
            "newest_ref": triggering_ref,
            "newest_ref_mtime": newest_ref_mtime.isoformat(),
        }
    return None


def check_decision_inline_diagram(decision_path: Path):
    """Return None if doc OK, else dict describing missing-diagram drift."""
    try:
        text = decision_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    # Exempt: single-file change docs (heuristic = body line count)
    line_count = text.count("\n")
    if line_count < SINGLE_CHANGE_LINE_THRESHOLD:
        return None

    # Probe for any diagram pattern anywhere in doc
    for pat in DIAGRAM_PATTERNS:
        if pat.search(text):
            return None  # diagram present

    return {
        "decision": decision_path.name,
        "line_count": line_count,
        "reason": "no inline diagram (Doctrine #14 — ASCII/mermaid/svg/img expected)",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--decision-days", type=int, default=DEFAULT_DECISION_DAYS,
                    help="Look back N days for decision-doc diagram check (default: 30)")
    args = ap.parse_args()

    # CHECK 1 — tile staleness (original)
    tile_drifted = []
    if TILES_DIR.exists():
        tiles = sorted(TILES_DIR.glob("*.html"))
        for tile in tiles:
            result = check_tile(tile)
            if result:
                tile_drifted.append(result)
    # else: silently skip — tiles dir optional

    # CHECK 2 — Doctrine #14 inline diagram presence on recent decisions (Phase 2 F8)
    decision_drifted = []
    if DECISIONS_DIR.exists():
        cutoff_ts = (datetime.now() - timedelta(days=args.decision_days)).timestamp()
        recent_decisions = sorted(
            [d for d in DECISIONS_DIR.glob("*.md")
             if d.stat().st_mtime >= cutoff_ts and d.name != "decisions.md"]
        )
        # Heartbeat per Observability #6 for batches >50
        emit_progress = len(recent_decisions) > 50
        for idx, decision in enumerate(recent_decisions, start=1):
            if emit_progress and idx % 10 == 0:
                print(f"  [progress] decisions {idx}/{len(recent_decisions)}", file=sys.stderr)
            result = check_decision_inline_diagram(decision)
            if result:
                decision_drifted.append(result)

    total_drift = len(tile_drifted) + len(decision_drifted)
    if total_drift > 0:
        breakdown = f"tile-stale={len(tile_drifted)} decision-no-diagram={len(decision_drifted)}"
        print(f"[DRIFT] diagram-tags:  {total_drift} drifted ({breakdown})")
        if args.verbose:
            for d in tile_drifted:
                print(f"  - tile {d['tile']}: verified {d['last_verified']}, "
                      f"{d['newest_ref']} touched {d['newest_ref_mtime']}")
            for d in decision_drifted:
                print(f"  - decision {d['decision']}: {d['reason']} ({d['line_count']} lines)")
    else:
        print("[DRIFT] diagram-tags:  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
