"""
debate_logic.py — Turn gate functions for adversarial debate sub-graphs.

TradingAgents adversarial debate pattern port (§2 of 4).
Source: tools/trading-agents/tradingagents/graph/conditional_logic.py
Decision: decisions/2026-04-29-adversarial-debate-pattern.md
Pre-wiring tag: pre-adversarial-debate-wiring

Two gate functions — one per sub-graph.
Both return the next speaker token used as a graph edge condition.

Principles: Observability #6 · Reproducibility #8
"""

from __future__ import annotations

import sys


# ── 2-way gate (Advocate ↔ Skeptic → Judge) ─────────────────────────────────

def advocacy_next_speaker(state: dict) -> str:
    """
    Decide who speaks next in the 2-way advocacy debate.

    Returns: "advocate" | "skeptic" | "judge"

    Exit condition: count >= 2 * max_debate_rounds → "judge"
    Turn alternation:
      If latest response starts with "Advocate:" → Skeptic speaks next
      Otherwise (first turn or latest was Skeptic) → Advocate speaks next
    """
    count = state.get("count", 0)
    max_rounds = state.get("max_debate_rounds", 1)

    if count >= 2 * max_rounds:
        sys.stderr.write(
            f"[debate_logic] advocacy_next_speaker: count={count} "
            f">= 2×{max_rounds} rounds → judge\n"
        )
        return "judge"

    current = state.get("current_response", "")
    if current.startswith("Advocate:"):
        next_speaker = "skeptic"
    else:
        next_speaker = "advocate"

    sys.stderr.write(
        f"[debate_logic] advocacy_next_speaker: "
        f"turn {count}, latest={current[:30]!r} → {next_speaker}\n"
    )
    return next_speaker


def advocacy_should_continue(state: dict) -> bool:
    """
    Boolean convenience — True if debate not yet complete.
    Use advocacy_next_speaker for graph edge routing.
    """
    count = state.get("count", 0)
    max_rounds = state.get("max_debate_rounds", 1)
    return count < 2 * max_rounds


# ── 3-way gate (Opportunist → Guardian → Pragmatist → Principal) ─────────────

_RISK_ORDER = ["opportunist", "guardian", "pragmatist"]


def risk_next_speaker(state: dict) -> str:
    """
    Decide who speaks next in the 3-way risk discussion.

    Returns: "opportunist" | "guardian" | "pragmatist" | "judge"

    Exit condition: count >= 3 * max_risk_discuss_rounds → "judge"
    Turn order cycles: opportunist → guardian → pragmatist → opportunist ...
    latest_speaker is used as authority over count if populated (resume-safe).
    """
    count = state.get("count", 0)
    max_rounds = state.get("max_risk_discuss_rounds", 1)

    if count >= 3 * max_rounds:
        sys.stderr.write(
            f"[debate_logic] risk_next_speaker: count={count} "
            f">= 3×{max_rounds} rounds → judge\n"
        )
        return "judge"

    # Resume-safe: derive next from latest_speaker if set
    latest = state.get("latest_speaker", "")
    if latest in _RISK_ORDER:
        next_idx = (_RISK_ORDER.index(latest) + 1) % 3
    else:
        next_idx = 0  # First turn → Opportunist

    next_speaker = _RISK_ORDER[next_idx]
    sys.stderr.write(
        f"[debate_logic] risk_next_speaker: "
        f"turn {count}, latest={latest!r} → {next_speaker}\n"
    )
    return next_speaker


def risk_should_continue(state: dict) -> bool:
    """Boolean convenience for risk debate."""
    count = state.get("count", 0)
    max_rounds = state.get("max_risk_discuss_rounds", 1)
    return count < 3 * max_rounds
