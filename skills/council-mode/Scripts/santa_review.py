"""
santa_review.py — Santa-method dual-reviewer Stage 4

Spawns two parallel reviewer agents post-execution:
  Reviewer-A: Correctness lens (Sonnet 4.6)
  Reviewer-B: Doctrine lens (Opus 4.6)

Aggregates verdicts → SHIP | ESCALATE_TIER | HALT_TO_OPERATOR
Returns structured ReviewResult with both verdicts, outcome, and cost.

Activated via council_run.py --gated flag (opt-in; default council-mode behavior unchanged).
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ValidationError

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
_SKILL_ROOT = _HERE.parent
_BRAIN_ROOT = _SKILL_ROOT.parent.parent
_REFERENCES = _SKILL_ROOT / "references"
_STATE_DIR = _BRAIN_ROOT / "state"
_HALTS_LOG = _STATE_DIR / "council-halts.jsonl"

# ── Reviewer models ───────────────────────────────────────────────────────────

REVIEWER_A_MODEL = "claude-sonnet-4-6"   # Correctness — fast, structural
REVIEWER_B_MODEL = "claude-opus-4-7"     # Doctrine — principle-carrying capacity (frontier; 4-6 routable as frontier_prior)


# ── Schema ───────────────────────────────────────────────────────────────────

class ReviewVerdict(BaseModel):
    verdict: str    # "PASS" | "FAIL"
    reason: str
    severity: str   # "low" | "med" | "high"


class Outcome(str, Enum):
    SHIP = "SHIP"
    ESCALATE_TIER = "ESCALATE_TIER"
    HALT_TO_OPERATOR = "HALT_TO_OPERATOR"


@dataclass
class ReviewResult:
    outcome: Outcome
    reviewer_a: Optional[ReviewVerdict]
    reviewer_b: Optional[ReviewVerdict]
    cost_usd: float
    elapsed_s: float
    error: Optional[str] = None


# ── Verdict aggregation ───────────────────────────────────────────────────────

def aggregate(rev_a: ReviewVerdict, rev_b: ReviewVerdict) -> Outcome:
    """
    Both PASS → SHIP
    Both FAIL → HALT_TO_OPERATOR
    Disagreement + high severity → HALT_TO_OPERATOR
    Disagreement + low/med severity → ESCALATE_TIER
    """
    a_pass = rev_a.verdict.upper() == "PASS"
    b_pass = rev_b.verdict.upper() == "PASS"

    if a_pass and b_pass:
        return Outcome.SHIP
    if not a_pass and not b_pass:
        return Outcome.HALT_TO_OPERATOR
    # Disagreement path
    if rev_a.severity == "high" or rev_b.severity == "high":
        return Outcome.HALT_TO_OPERATOR
    return Outcome.ESCALATE_TIER


# ── Prompt loading + template injection ───────────────────────────────────────

def _load_doctrine_summary() -> str:
    doctrine_path = _BRAIN_ROOT / "doctrine.md"
    try:
        text = doctrine_path.read_text(errors="ignore")
        # Truncate to ~3KB to stay within prompt budget
        return text[:3000].strip()
    except Exception:
        return "(doctrine.md not found — evaluate against Cerebro principles from memory)"


def _build_reviewer_a_prompt(task: str, output: str) -> str:
    template_path = _REFERENCES / "reviewer_a_correctness.md"
    try:
        template = template_path.read_text(errors="ignore")
    except Exception:
        template = "Review the output for correctness. Return JSON {verdict, reason, severity}.\n\nTask: {TASK}\nOutput: {OUTPUT}"
    return template.replace("{TASK}", task).replace("{OUTPUT}", output[:4000])


def _build_reviewer_b_prompt(task: str, output: str) -> str:
    template_path = _REFERENCES / "reviewer_b_doctrine.md"
    doctrine = _load_doctrine_summary()
    try:
        template = template_path.read_text(errors="ignore")
    except Exception:
        template = "Review the output for Cerebro doctrine compliance. Return JSON {verdict, reason, severity}.\n\nTask: {TASK}\nOutput: {OUTPUT}"
    return (
        template
        .replace("{DOCTRINE_SUMMARY}", doctrine)
        .replace("{TASK}", task)
        .replace("{OUTPUT}", output[:4000])
    )


# ── Single reviewer call ──────────────────────────────────────────────────────

def _call_reviewer(
    label: str,
    prompt: str,
    model: str,
    client: object,
    structured_fallback,
) -> tuple[Optional[ReviewVerdict], float, float]:
    """
    Call one reviewer. Returns (verdict, cost_usd, elapsed_s).
    Uses request_structured() for 4-tier fallback.
    """
    t0 = time.time()
    # Cost estimate: Sonnet ~$0.005/call, Opus ~$0.05/call (rough)
    cost_map = {REVIEWER_A_MODEL: 0.005, REVIEWER_B_MODEL: 0.05}
    cost = cost_map.get(model, 0.01)

    if structured_fallback is not None:
        result = structured_fallback(
            schema=ReviewVerdict,
            prompt=prompt,
            model=model,
            caller_skill="santa-method",
            litellm_client=client,
        )
        elapsed = time.time() - t0
        if result.success:
            return result.value, cost, elapsed
        sys.stderr.write(
            f"[santa-method] {label} reviewer FAIL at tier {result.final_tier_reached}: "
            f"{result.attempts[-1].error if result.attempts else 'unknown'}\n"
        )
        return None, cost, elapsed
    else:
        # Fallback: direct API call with ad-hoc parse
        elapsed = time.time() - t0
        return None, cost, elapsed


# ── Halt log ─────────────────────────────────────────────────────────────────

def _log_halt(task: str, result: ReviewResult) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "task_preview": task[:200],
            "outcome": result.outcome.value,
            "reviewer_a": result.reviewer_a.model_dump() if result.reviewer_a else None,
            "reviewer_b": result.reviewer_b.model_dump() if result.reviewer_b else None,
        }
        with open(_HALTS_LOG, "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:
        sys.stderr.write(f"[santa-method] WARN: could not write halt log: {e}\n")


# ── Main entry ────────────────────────────────────────────────────────────────

def run_review(
    task: str,
    output: str,
    *,
    client: object = None,
    dry_run: bool = False,
) -> ReviewResult:
    """
    Run the santa-method dual-reviewer gate on `output` (result of council-mode Stage 3).

    Args:
        task:      Original task description
        output:    Council-mode's selected/aggregated output to gate
        client:    LiteLLM or Anthropic client (reuse council-mode's client)
        dry_run:   If True, skip API calls and return synthetic PASS

    Returns:
        ReviewResult with .outcome, .reviewer_a, .reviewer_b, .cost_usd, .elapsed_s
    """
    if dry_run:
        syn_a = ReviewVerdict(verdict="PASS", reason="[DRY RUN — synthetic verdict]", severity="low")
        syn_b = ReviewVerdict(verdict="PASS", reason="[DRY RUN — synthetic verdict]", severity="low")
        return ReviewResult(
            outcome=Outcome.SHIP,
            reviewer_a=syn_a,
            reviewer_b=syn_b,
            cost_usd=0.0,
            elapsed_s=0.0,
        )

    # Lazy-import structured_output from _shared
    structured_fallback = None
    try:
        _shared = _BRAIN_ROOT / "skills" / "_shared"
        sys.path.insert(0, str(_shared))
        from structured_output import request_structured
        structured_fallback = request_structured
    except ImportError:
        sys.stderr.write("[santa-method] WARN: _shared/structured_output not available — reviewers will fail gracefully\n")

    prompt_a = _build_reviewer_a_prompt(task, output)
    prompt_b = _build_reviewer_b_prompt(task, output)

    t_start = time.time()
    rev_a = rev_b = None
    cost_a = cost_b = 0.0

    # Parallel dispatch
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(_call_reviewer, "A", prompt_a, REVIEWER_A_MODEL, client, structured_fallback)
        fut_b = pool.submit(_call_reviewer, "B", prompt_b, REVIEWER_B_MODEL, client, structured_fallback)
        rev_a, cost_a, _ = fut_a.result()
        rev_b, cost_b, _ = fut_b.result()

    elapsed = time.time() - t_start
    total_cost = cost_a + cost_b

    # If either reviewer failed to parse, treat as HALT
    if rev_a is None or rev_b is None:
        null_verdict = ReviewVerdict(verdict="FAIL", reason="[reviewer parse failure — see structured-output-failures.jsonl]", severity="high")
        rev_a = rev_a or null_verdict
        rev_b = rev_b or null_verdict

    outcome = aggregate(rev_a, rev_b)
    result = ReviewResult(
        outcome=outcome,
        reviewer_a=rev_a,
        reviewer_b=rev_b,
        cost_usd=total_cost,
        elapsed_s=elapsed,
    )

    if outcome == Outcome.HALT_TO_OPERATOR:
        _log_halt(task, result)

    return result


# ── CLI smoke ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick smoke test
    print("[santa_review] Smoke test — dry_run=True")
    r = run_review("Test task", "Test output", dry_run=True)
    print(f"  outcome:    {r.outcome}")
    print(f"  reviewer_a: {r.reviewer_a}")
    print(f"  reviewer_b: {r.reviewer_b}")
    print(f"  cost:       ${r.cost_usd:.4f}")
    print("[santa_review] Smoke PASS")
