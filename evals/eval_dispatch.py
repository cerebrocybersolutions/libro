#!/usr/bin/env python3
"""
eval_dispatch.py — Evaluation harness for the advisor-mode task classifier.

The advisor-mode skill routes each task to a model tier (C/B/A/A+) based on
complexity, reversibility, cross-department impact, and stakes. Routing quality
matters: under-classifying a high-stakes task sends it to a weak/cheap model,
which is the costly failure mode. This harness measures routing quality against
a labeled set of cases.

Two modes:
  --mock   Offline. Uses the documented fast-track keyword rules as a local
           classifier. Deterministic, no API key, runnable in CI.
  (default) Live. Calls skills/advisor-mode/Scripts/classify_task.classify()
           (Claude Haiku). Requires ANTHROPIC_API_KEY.

Metrics:
  - exact accuracy        predicted tier == expected tier
  - adjacent accuracy     prediction within one tier (the classifier's conflict
                          rule says "when unsure, pick the higher tier", so
                          off-by-one-up is tolerable; off-by-one-down is not)
  - under-classification  predicted a LOWER tier than expected (the unsafe error)
  - over-classification   predicted a HIGHER tier than expected (wasteful, safe)
  - per-tier + confusion matrix

Usage:
  python evals/eval_dispatch.py --mock
  python evals/eval_dispatch.py --mock --json
  python evals/eval_dispatch.py                      # live (needs ANTHROPIC_API_KEY)
  python evals/eval_dispatch.py --cases path/to/cases.json --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

TIERS = ("C", "B", "A", "A+")
TIER_RANK = {tier: rank for rank, tier in enumerate(TIERS)}

DEFAULT_CASES = Path(__file__).parent / "cases" / "dispatch_cases.json"


@dataclass(frozen=True)
class EvalCase:
    task: str
    expected: str
    note: str = ""


@dataclass
class CaseResult:
    case: EvalCase
    predicted: Optional[str]

    @property
    def correct(self) -> bool:
        return self.predicted == self.case.expected

    @property
    def delta(self) -> Optional[int]:
        """Predicted rank minus expected rank. None if tier couldn't be parsed."""
        if self.predicted is None:
            return None
        return TIER_RANK[self.predicted] - TIER_RANK[self.case.expected]


@dataclass
class EvalReport:
    results: list[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def parsed(self) -> list[CaseResult]:
        return [r for r in self.results if r.predicted is not None]

    @property
    def exact(self) -> int:
        return sum(1 for r in self.results if r.correct)

    @property
    def adjacent(self) -> int:
        # within one tier, in either direction
        return sum(1 for r in self.parsed if abs(r.delta) <= 1)

    @property
    def under(self) -> int:
        # predicted a weaker tier than required — the unsafe error
        return sum(1 for r in self.parsed if r.delta is not None and r.delta < 0)

    @property
    def over(self) -> int:
        return sum(1 for r in self.parsed if r.delta is not None and r.delta > 0)

    @property
    def unparsed(self) -> int:
        return sum(1 for r in self.results if r.predicted is None)

    def _pct(self, n: int) -> str:
        return f"{(100.0 * n / self.total):5.1f}%" if self.total else "  n/a"

    def confusion(self) -> dict[str, dict[str, int]]:
        matrix = {e: {p: 0 for p in TIERS} for e in TIERS}
        for r in self.parsed:
            matrix[r.case.expected][r.predicted] += 1
        return matrix

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "exact_accuracy": round(self.exact / self.total, 4) if self.total else None,
            "adjacent_accuracy": round(self.adjacent / self.total, 4) if self.total else None,
            "under_classified": self.under,
            "over_classified": self.over,
            "unparsed": self.unparsed,
            "confusion": self.confusion(),
            "misses": [
                {"task": r.case.task, "expected": r.case.expected, "predicted": r.predicted}
                for r in self.results
                if not r.correct
            ],
        }

    def render(self) -> str:
        lines = []
        lines.append("Advisor-Dispatch Eval")
        lines.append("=" * 60)
        lines.append(f"cases:              {self.total}")
        lines.append(f"exact accuracy:     {self.exact}/{self.total}  ({self._pct(self.exact)})")
        lines.append(f"adjacent (+/-1):    {self.adjacent}/{self.total}  ({self._pct(self.adjacent)})")
        lines.append(f"under-classified:   {self.under}   (unsafe: routed too weak)")
        lines.append(f"over-classified:    {self.over}   (wasteful but safe)")
        if self.unparsed:
            lines.append(f"unparsed:           {self.unparsed}   (tier not found in output)")
        lines.append("")
        lines.append("confusion (rows=expected, cols=predicted):")
        header = "        " + "".join(f"{p:>5}" for p in TIERS)
        lines.append(header)
        matrix = self.confusion()
        for e in TIERS:
            row = f"  {e:<5} " + "".join(f"{matrix[e][p]:>5}" for p in TIERS)
            lines.append(row)
        misses = [r for r in self.results if not r.correct]
        if misses:
            lines.append("")
            lines.append("misses:")
            for r in misses:
                pred = r.predicted if r.predicted is not None else "?"
                flag = " [UNDER]" if (r.delta is not None and r.delta < 0) else ""
                lines.append(f"  expected {r.case.expected:<2} got {pred:<2}{flag}  {r.case.task[:60]}")
        return "\n".join(lines)


def parse_tier(output: str) -> Optional[str]:
    """Extract the assigned tier from a classifier output block. A+ before A."""
    for line in output.splitlines():
        if "Assigned Tier:" in line:
            value = line.split("Assigned Tier:", 1)[1].strip()
            if value.startswith("A+"):
                return "A+"
            for tier in ("A+", "A", "B", "C"):
                if value.startswith(tier):
                    return tier
    # Fallback: scan whole text for the marker phrasing.
    if "Assigned Tier:    A+" in output:
        return "A+"
    for tier in ("A+", "A", "B", "C"):
        if f"Assigned Tier:    {tier}" in output:
            return tier
    return None


# --- classifiers -----------------------------------------------------------

FAST_RULES: list[tuple[str, list[str]]] = [
    ("A+", ["full architecture review", "should we pivot", "review all departments"]),
    ("A",  ["should we pursue", "architect", "strategy for", "affects multiple departments", "irreversible"]),
    ("B",  ["write a proposal", "analyze this", "draft an email about", "create a plan for"]),
    ("C",  ["format", "look up", "what is", "spell check", "convert to", "summarize this paragraph"]),
]


def mock_classify(task: str) -> str:
    """
    Offline classifier implementing the documented fast-track keyword rules.
    Deterministic baseline — lets the eval run in CI without an API key.
    Order: A+ -> A -> B -> C (highest match wins, matching the 'pick higher' rule).
    Defaults to B when nothing matches (conservative middle).
    """
    low = task.lower()
    for tier, keywords in FAST_RULES:
        if any(kw in low for kw in keywords):
            return f"Assigned Tier:    {tier}\nFast-track:       Yes (mock keyword rule)"
    return "Assigned Tier:    B\nFast-track:       No (mock default)"


def live_classify(task: str) -> str:
    """Call the real advisor-mode classifier (Claude Haiku)."""
    scripts = Path(__file__).resolve().parents[1] / "skills" / "advisor-mode" / "Scripts"
    sys.path.insert(0, str(scripts))
    import classify_task  # noqa: E402  (path injected above)
    return classify_task.classify(task)


# --- runner ----------------------------------------------------------------

def load_cases(path: Path) -> list[EvalCase]:
    data = json.loads(path.read_text())
    cases = [EvalCase(**row) for row in data]
    for c in cases:
        if c.expected not in TIER_RANK:
            raise ValueError(f"bad expected tier {c.expected!r} for task: {c.task[:50]}")
    return cases


def run_eval(cases: list[EvalCase], classify_fn: Callable[[str], str],
             verbose: bool = False) -> EvalReport:
    report = EvalReport()
    for i, case in enumerate(cases, 1):
        output = classify_fn(case.task)
        predicted = parse_tier(output)
        report.results.append(CaseResult(case=case, predicted=predicted))
        if verbose:
            mark = "ok " if predicted == case.expected else "MISS"
            print(f"[{i}/{len(cases)}] {mark}  exp={case.expected} got={predicted}  {case.task[:50]}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES,
                        help="JSON file of labeled cases (default: evals/cases/dispatch_cases.json)")
    parser.add_argument("--mock", action="store_true",
                        help="Offline mode: keyword classifier, no API key needed")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--verbose", action="store_true", help="Per-case output")
    parser.add_argument("--min-adjacent", type=float, default=None,
                        help="Fail (exit 1) if adjacent accuracy is below this fraction (e.g. 0.9)")
    parser.add_argument("--max-under", type=int, default=None,
                        help="Fail (exit 1) if under-classified count exceeds this")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    classify_fn = mock_classify if args.mock else live_classify
    report = run_eval(cases, classify_fn, verbose=args.verbose)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.render())

    # Optional gates for CI.
    failed = False
    if args.min_adjacent is not None and report.total:
        if (report.adjacent / report.total) < args.min_adjacent:
            print(f"\nFAIL: adjacent accuracy below {args.min_adjacent}", file=sys.stderr)
            failed = True
    if args.max_under is not None and report.under > args.max_under:
        print(f"\nFAIL: {report.under} under-classified (> {args.max_under})", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
