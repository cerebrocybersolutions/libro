#!/usr/bin/env python3
"""
classify_task.py — Advisor Dispatch — Task Classifier

Classifies a task description into Tier C/B/A/A+ using the decision matrix
from stage1_classify.md. Uses Haiku to do the classification (fast + cheap).

Usage:
  python classify_task.py --task "Should we pursue SAMPLE-2026-00001?"
  python classify_task.py --task "Format this vendor email as a table"
  python classify_task.py --task "Design the cross-dept-sync skill architecture"
  python classify_task.py --task "Full audit of all 6 departments" --verbose

Requirements:
  pip install anthropic
  export ANTHROPIC_API_KEY=your_key_here
"""

import argparse
import os
import sys

CLASSIFIER_SYSTEM_PROMPT = """
You are a task classifier for the operator's advisor-mode system.

Your job: classify the given task into the correct tier using the scoring matrix below.
Output ONLY the structured classification block. No preamble. No commentary outside the block.

SCORING MATRIX:

Factor 1 — Complexity
  0: Single step, single output, no judgment
  1: 2-3 steps, some structure, light judgment
  2: Multi-step, synthesis required, significant judgment
  3: Architecture-level, cross-system, novel problem

Factor 2 — Reversibility
  0: Completely reversible (draft, lookup, brainstorm)
  1: Partially reversible (file written, email drafted)
  2: Difficult to reverse (decision logged, sent externally)
  3: Irreversible or high-consequence (submitted, published, financial)

Factor 3 — Cross-Department Impact
  0: Affects one task/output only
  1: Affects one department
  2: Affects 2+ departments or a skill used across all sessions
  3: Affects company direction or is architectural infrastructure

Factor 4 — Stakes
  0: Low (no financial, legal, or reputational risk)
  1: Medium ($100-$1K at stake or reputational if wrong)
  2: High ($1K-$10K at stake or significant direction risk)
  3: Critical ($10K+ at stake or sets a wrong trajectory for months)

TIER ASSIGNMENT:
  0-2  total → Tier C (Haiku 4.5)
  3-5  total → Tier B (Sonnet 4.6)
  6-9  total → Tier A (Sonnet 4.6 + Opus advisor)
  10-12 total → Tier A+ (Opus 4.7 solo — flag for the operator approval)

FAST-TRACK RULES (classify immediately if matched):
  Fast C: "format", "look up", "what is", "spell check", "convert to", "summarize this paragraph"
  Fast B: "write a proposal", "analyze this", "draft an email about", "create a plan for"
  Fast A: "should we pursue", "architect", "strategy for", "affects multiple departments", "irreversible"
  Fast A+: "full architecture review", "should we pivot", "review all departments"

CONFLICT RULE: When unsure between adjacent tiers, assign the HIGHER tier.

OUTPUT FORMAT (output this exact structure, no deviations):
TASK CLASSIFICATION
───────────────────
Task: [one-line summary]

Scoring:
  Complexity:     [score]/3 — [one-line reasoning]
  Reversibility:  [score]/3 — [one-line reasoning]
  Cross-dept:     [score]/3 — [one-line reasoning]
  Stakes:         [score]/3 — [one-line reasoning]
  Total:          [X]/12

Assigned Tier:    [C / B / A / A+]
Model:            [Haiku 4.5 / Sonnet 4.6 / Sonnet 4.6 + Opus advisor / Opus 4.7]
Advisor budget:   [N/A or "max_uses = 3 (default)"]
Reasoning:        [1-2 sentences explaining the tier decision]

Fast-track:       [Yes — matched "[rule]" / No — scored manually]
Next step:        [Proceed to dispatch / Awaiting the operator approval (A+ only)]
"""


def check_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("\n❌ ANTHROPIC_API_KEY is not set.")
        print("Set it with: export ANTHROPIC_API_KEY=your_key_here\n")
        sys.exit(1)
    return key


def classify(task: str, verbose: bool = False) -> str:
    """Classify a task using Haiku. Returns the classification block as a string."""
    api_key = check_api_key()

    try:
        import anthropic
    except ImportError:
        print("\n❌ anthropic package not installed.")
        print("Install: pip install anthropic --break-system-packages\n")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    if verbose:
        print(f"\nClassifying: {task[:80]}...")
        print("Using Haiku 4.5 (fast + cheap for classification)\n")

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=CLASSIFIER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Classify this task:\n\n{task}"}],
    )

    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(
        description="Classify a task into the correct advisor-mode tier"
    )
    parser.add_argument("--task",    required=True, help="Task description to classify")
    parser.add_argument("--verbose", action="store_true",
                        help="Show additional context during classification")
    args = parser.parse_args()

    result = classify(args.task, verbose=args.verbose)
    print(result)

    # Extract tier for exit code signaling (useful in shell scripts)
    if "Assigned Tier:    C" in result:
        sys.exit(10)   # Convention: exit 10 = Tier C
    elif "Assigned Tier:    B" in result:
        sys.exit(11)
    elif "Assigned Tier:    A+" in result:
        sys.exit(13)   # A+ before A to avoid partial match
    elif "Assigned Tier:    A" in result:
        sys.exit(12)


if __name__ == "__main__":
    main()
