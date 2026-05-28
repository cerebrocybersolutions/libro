#!/usr/bin/env python3
"""
budget_tracker.py — Advisor Dispatch — Budget Monitor

Reads daily_usage.md and reports advisor call usage vs. daily budget.
Run at any time to check status. Run at end of week for pattern review.

Usage:
  python budget_tracker.py                    # Today's status
  python budget_tracker.py --week             # Last 7 days summary
  python budget_tracker.py --date 2026-04-15  # Specific date
  python budget_tracker.py --patterns         # Show escalation patterns

Requirements: No API key needed — reads local log files only.
"""

import argparse
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Auto-detect from script location; override with CEREBRO_BRAIN_ROOT env var if needed.
# Script lives at: <BRAIN_ROOT>/skills/advisor-dispatch/Scripts/budget_tracker.py → parents[3] = <BRAIN_ROOT>
BRAIN_ROOT = Path(os.environ.get("CEREBRO_BRAIN_ROOT") or str(Path(__file__).resolve().parents[3]))
LOG_FILE   = BRAIN_ROOT / "skills" / "advisor-dispatch" / "logs" / "daily_usage.md"
DAILY_BUDGET = 20


def parse_log(target_date: str = None) -> list[dict]:
    """Parse daily_usage.md and return dispatch records."""
    if not LOG_FILE.exists():
        return []

    records = []
    current_date = None
    in_table = False

    with open(LOG_FILE) as f:
        for line in f:
            # Date header
            date_match = re.match(r"## (\d{4}-\d{2}-\d{2}) Usage Log", line)
            if date_match:
                current_date = date_match.group(1)
                in_table = False
                continue

            # Skip if filtering by date
            if target_date and current_date != target_date:
                continue

            # Table header row
            if line.startswith("| Time |"):
                in_table = True
                continue

            # Separator row
            if line.startswith("|---|"):
                continue

            # Data row
            if in_table and line.startswith("|") and current_date:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    advisor_raw = parts[5]
                    try:
                        advisor_calls = int(advisor_raw)
                    except ValueError:
                        advisor_calls = 0

                    cost_raw = parts[6].replace("$", "").replace("~", "")
                    try:
                        est_cost = float(cost_raw)
                    except ValueError:
                        est_cost = 0.0

                    records.append({
                        "date":          current_date,
                        "time":          parts[1],
                        "task":          parts[2],
                        "tier":          parts[3],
                        "model":         parts[4],
                        "advisor_calls": advisor_calls,
                        "est_cost":      est_cost,
                        "notes":         parts[7] if len(parts) > 7 else "",
                    })

    return records


def report_day(date: str) -> None:
    """Print usage report for a single day."""
    records = parse_log(date)
    if not records:
        print(f"\nNo dispatch records found for {date}.")
        return

    total_advisor = sum(r["advisor_calls"] for r in records)
    total_cost    = sum(r["est_cost"] for r in records)
    tier_counts   = defaultdict(int)
    for r in records:
        tier_counts[r["tier"]] += 1

    pct = (total_advisor / DAILY_BUDGET) * 100
    if pct >= 100:
        budget_indicator = "🚫 EXHAUSTED"
    elif pct >= 90:
        budget_indicator = "🔴 90%+"
    elif pct >= 75:
        budget_indicator = "⚠️  75%+"
    else:
        budget_indicator = "🟢 OK"

    print(f"\n{'='*55}")
    print(f"  CEREBRO ADVISOR DISPATCH — Daily Report")
    print(f"  Date: {date}")
    print(f"{'='*55}")
    print(f"\n  Advisor budget:  {total_advisor}/{DAILY_BUDGET} calls used  {budget_indicator}")
    print(f"  Remaining:       {DAILY_BUDGET - total_advisor} calls")
    print(f"  Est. total cost: ${total_cost:.4f}")
    print(f"\n  Tier breakdown:")
    for tier in ["C", "B", "A", "A+"]:
        count = tier_counts.get(tier, 0)
        if count:
            print(f"    Tier {tier}: {count} dispatches")

    print(f"\n  Dispatch log:")
    for r in records:
        advisor_str = f"{r['advisor_calls']} advisor calls" if r["advisor_calls"] else "no advisor"
        note_str    = f"  [{r['notes']}]" if r["notes"] else ""
        print(f"    {r['time']}  [{r['tier']}]  {r['task'][:35]}  ({advisor_str}){note_str}")

    # Flags
    escalations = [r for r in records if "ESCALATED" in r.get("notes", "")]
    max_hits    = [r for r in records if "max_uses hit" in r.get("notes", "")]
    if escalations:
        print(f"\n  ⚠️  Escalations today: {len(escalations)}")
        for e in escalations:
            print(f"    - {e['task'][:50]}: {e['notes']}")
    if max_hits:
        print(f"\n  ⚠️  max_uses exhausted: {len(max_hits)} tasks hit the call cap")


def report_week() -> None:
    """Print 7-day rolling summary."""
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]

    print(f"\n{'='*55}")
    print(f"  CEREBRO ADVISOR DISPATCH — 7-Day Summary")
    print(f"{'='*55}")
    print(f"\n  {'Date':<14} {'Dispatches':<12} {'Advisor calls':<16} {'Est. cost':<12}")
    print(f"  {'-'*50}")

    for date in dates:
        records = parse_log(date)
        if not records:
            print(f"  {date:<14} {'—':<12} {'—':<16} {'—':<12}")
            continue
        total_advisor = sum(r["advisor_calls"] for r in records)
        total_cost    = sum(r["est_cost"] for r in records)
        pct_str       = f"({int(total_advisor/DAILY_BUDGET*100)}%)" if total_advisor else ""
        print(f"  {date:<14} {len(records):<12} {total_advisor:<8}{pct_str:<8} ${total_cost:<11.4f}")


def report_patterns() -> None:
    """Show escalation patterns and reclassification candidates."""
    all_records = parse_log()
    if not all_records:
        print("\nNo records to analyze.")
        return

    escalations_by_task_type = defaultdict(list)
    for r in all_records:
        if "ESCALATED" in r.get("notes", ""):
            escalations_by_task_type[r["task"][:30]].append(r)

    print(f"\n{'='*55}")
    print(f"  CEREBRO ADVISOR DISPATCH — Pattern Report")
    print(f"{'='*55}")

    if not escalations_by_task_type:
        print("\n  No escalations recorded. Classification is holding.")
        return

    print(f"\n  Escalation patterns (reclassification candidates):")
    for task_type, records in escalations_by_task_type.items():
        if len(records) >= 2:
            print(f"\n  ⚠️  '{task_type}' — escalated {len(records)} times")
            print(f"     → Consider permanently reclassifying this task type upward")
            print(f"     → Update stage1_classify.md Fast-Track rules")


def main():
    parser = argparse.ArgumentParser(
        description="Cerebro Advisor Dispatch — Budget Monitor"
    )
    parser.add_argument("--week",     action="store_true", help="Show 7-day summary")
    parser.add_argument("--patterns", action="store_true", help="Show escalation patterns")
    parser.add_argument("--date",     help="Report for specific date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.week:
        report_week()
    elif args.patterns:
        report_patterns()
    else:
        target = args.date or datetime.now().strftime("%Y-%m-%d")
        report_day(target)

    print()


if __name__ == "__main__":
    main()
