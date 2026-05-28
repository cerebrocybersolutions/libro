"""
debate_states.py — Pydantic state schemas for adversarial debate sub-graphs.

TradingAgents adversarial debate pattern port (§1 of 4).
Source: tools/trading-agents/tradingagents/agents/researchers/ +
        tools/trading-agents/tradingagents/agents/risk_mgmt/
Decision: decisions/2026-04-29-adversarial-debate-pattern.md
Pre-wiring tag: pre-adversarial-debate-wiring

Two sub-graphs share no state — run independently or in sequence:
  AdvocacyDebateState — 2-way Advocate / Skeptic → Chief Advisor
  RiskDebateState     — 3-way Opportunist / Guardian / Pragmatist → Principal Advisor

Principles: Governance #1 · Observability #6 · Reproducibility #8
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ── 2-way advocacy debate ─────────────────────────────────────────────────────

class AdvocacyDebateState(BaseModel):
    """
    State for the Advocate ↔ Skeptic debate cycle.

    Turn numbering:
      count=0       → first Advocate turn
      count=1       → first Skeptic turn
      count=2       → second Advocate turn (if max_debate_rounds > 1)
      count=2*N     → exits to Chief Advisor (judge)

    current_response always reflects the most recent argument, prefixed with
    "Advocate:" or "Skeptic:" so the turn gate can identify the speaker.
    """
    task: str

    # Per-side transcripts (for clean side-specific context injection)
    advocate_history: str = ""
    skeptic_history: str = ""

    # Full combined transcript (for Chief Advisor synthesis prompt)
    history: str = ""

    # Latest argument (prefixed with "Advocate:" or "Skeptic:")
    current_response: str = ""

    # Chief Advisor synthesis output
    judge_decision: str = ""

    # Round tracking
    count: int = 0
    max_debate_rounds: int = 1

    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: Optional[datetime] = None

    def is_complete(self) -> bool:
        return bool(self.judge_decision)

    def round_summary(self) -> str:
        """One-liner for logging."""
        if self.is_complete():
            return f"COMPLETE after {self.count} turns ({self.max_debate_rounds} round(s))"
        speaker = "Advocate" if self.count % 2 == 0 else "Skeptic"
        return f"turn {self.count}/{2 * self.max_debate_rounds} — awaiting {speaker}"


# ── 3-way risk debate ─────────────────────────────────────────────────────────

class RiskDebateState(BaseModel):
    """
    State for the Opportunist ↔ Guardian ↔ Pragmatist risk discussion.

    Turn order cycles: Opportunist → Guardian → Pragmatist → Opportunist ...
    Exit condition: count >= 3 * max_risk_discuss_rounds → Principal Advisor.

    Each debater reads ALL three current_*_response fields before responding,
    so every agent counters the other two on every turn.

    latest_speaker is set to "opportunist" | "guardian" | "pragmatist" after
    each turn — the gate uses this to decide who speaks next.
    """
    task: str

    # Per-role transcripts
    opportunist_history: str = ""
    guardian_history: str = ""
    pragmatist_history: str = ""

    # Full combined transcript (for Principal Advisor synthesis)
    history: str = ""

    # Latest speaker tag (prevents double-invocation on resume)
    latest_speaker: str = ""

    # Current response per role
    current_opportunist_response: str = ""
    current_guardian_response: str = ""
    current_pragmatist_response: str = ""

    # Principal Advisor synthesis output
    judge_decision: str = ""

    count: int = 0
    max_risk_discuss_rounds: int = 1

    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: Optional[datetime] = None

    def is_complete(self) -> bool:
        return bool(self.judge_decision)

    def round_summary(self) -> str:
        """One-liner for logging."""
        if self.is_complete():
            return f"COMPLETE after {self.count} turns ({self.max_risk_discuss_rounds} round(s))"
        order = ["opportunist", "guardian", "pragmatist"]
        next_idx = self.count % 3
        return (
            f"turn {self.count}/{3 * self.max_risk_discuss_rounds} "
            f"— awaiting {order[next_idx]}"
        )


# ── Config defaults ───────────────────────────────────────────────────────────

DEFAULT_DEBATE_CONFIG: dict = {
    "debate_mode": "sequential",        # "sequential" | "adversarial"
    "max_debate_rounds": 1,             # Advocate/Skeptic back-and-forth rounds
    "max_risk_discuss_rounds": 1,       # 3-way risk discussion rounds
    "run_risk_debate": False,           # Enable 3-way risk stage after advocacy
}
