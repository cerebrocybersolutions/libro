"""
council_state.py — council-mode v2 Pydantic typed sub-states
TradingAgents §4+§5 port

Defines all typed state schemas for the council-mode v2 LangGraph backbone.
Standalone — no LangGraph import here, just Pydantic schemas.

Schema hierarchy:
  TierDispatchState        — per-tier output (one per participant)
  DisagreementSurfaceState — Stage 3 diff aggregate
  ReviewState              — Stage 4 santa-method verdicts
  CouncilRunState          — full run; checkpoint root

Wired: 2026-04-30 per decisions/2026-04-30-council-mode-v2-langgraph-typed-substates.md
Snapshot tag: pre-council-mode-v2-langgraph-2026-04-30
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Tier dispatch ─────────────────────────────────────────────────────────────

class TierDispatchState(BaseModel):
    """State for a single tier's dispatch leg in Stage 2."""
    tier: Literal["A+", "A", "B", "C"]
    model: str                              # e.g. "claude-opus-4-7", "gemma4:31b-instruct-q5_K_M"
    surface: Literal[
        "cloud",
        "fleet-node-a",
        "fleet-node-b",
        "fleet-node-c",
        "local",
    ]
    prompt: str                             # full prompt sent to model
    output: Optional[str] = None           # model output (None if not yet dispatched)
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None            # error string if dispatch failed
    completed_at: Optional[datetime] = None


# ── Disagreement surface ──────────────────────────────────────────────────────

class DisagreementSurfaceState(BaseModel):
    """Stage 3 — diff aggregate of tier outputs."""
    tier_outputs: list[TierDispatchState] = Field(default_factory=list)
    diff_summary: Optional[str] = None     # natural-language diff (produced by Stage 3)
    consensus: Optional[bool] = None       # True if outputs substantially agree


# ── Review (santa-method) ─────────────────────────────────────────────────────

class ReviewState(BaseModel):
    """Stage 4 — santa-method dual-reviewer verdicts."""
    correctness_verdict: Literal["PASS", "FAIL", "PENDING"] = "PENDING"
    correctness_reason: Optional[str] = None
    correctness_severity: Optional[Literal["low", "med", "high"]] = None

    doctrine_verdict: Literal["PASS", "FAIL", "PENDING"] = "PENDING"
    doctrine_reason: Optional[str] = None
    doctrine_severity: Optional[Literal["low", "med", "high"]] = None

    aggregate: Optional[Literal["SHIP", "ESCALATE_TIER", "HALT_TO_OPERATOR"]] = None
    review_cost_usd: Optional[float] = None
    review_elapsed_s: Optional[float] = None


# ── Full run ──────────────────────────────────────────────────────────────────

class CouncilRunState(BaseModel):
    """
    Root checkpoint state. Serialized to state/council-runs/<run_id>.json.
    A run with final_outcome=None is in-flight (sessionstart surfaces these).
    """
    run_id: str = Field(default_factory=lambda: f"council-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}")
    task: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    gated: bool = False                    # True if --gated (santa-method Stage 4 fires)

    # Stage 2
    tier_dispatches: list[TierDispatchState] = Field(default_factory=list)

    # Stage 3
    disagreement: Optional[DisagreementSurfaceState] = None

    # Stage 4 (only populated when gated=True)
    review: Optional[ReviewState] = None

    # Terminal
    final_outcome: Optional[Literal["SHIP", "ESCALATE_TIER", "HALT_TO_OPERATOR", "ERROR"]] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

    def is_complete(self) -> bool:
        return self.final_outcome is not None

    def stage_summary(self) -> str:
        """One-liner for sessionstart in-flight surfacing."""
        if self.is_complete():
            return f"{self.run_id}: {self.final_outcome}"
        completed = [d.tier for d in self.tier_dispatches if d.completed_at is not None]
        return (
            f"{self.run_id}: IN-FLIGHT "
            f"(started {self.started_at.strftime('%H:%M')}, "
            f"tiers done: {', '.join(completed) or 'none'})"
        )
