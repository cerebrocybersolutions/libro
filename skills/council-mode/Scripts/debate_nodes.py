"""
debate_nodes.py — Debater node factories for adversarial debate sub-graphs.

TradingAgents adversarial debate pattern port (§3 of 4).
Source: tools/trading-agents/tradingagents/agents/researchers/ +
        tools/trading-agents/tradingagents/agents/risk_mgmt/
Decision: decisions/2026-04-29-adversarial-debate-pattern.md
Pre-wiring tag: pre-adversarial-debate-wiring

Factory functions return graph-node callables (state: dict) → dict.
Each node calls an LLM via the cloud client (Anthropic) and updates state in-place.

Cerebro persona mapping (from decision doc):
  Advocate      ← Bull Researcher (opportunity-side)
  Skeptic       ← Bear Researcher (risk-side)
  Chief Advisor ← Research Manager (synthesis, deep model)
  Opportunist   ← Aggressive Debater
  Guardian      ← Conservative Debater
  Pragmatist    ← Neutral Debater
  Principal     ← Portfolio Manager (final decision, deep model)

Principles: Governance #1 · Observability #6 · Reproducibility #8
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional


# ── LLM dispatch helper ───────────────────────────────────────────────────────

_COUNCIL_SYSTEM = (
    "You are an advisor for the operator's organization. "
    "Respond directly and concretely. State assumptions if needed."
)
# NOTE: operator identity (company, CAGE/UEI/registration IDs, sector) should be
# loaded from the operator profile (~/.cerebro/profile.yaml) and prepended to
# this prompt at runtime, not hardcoded here.


def _call_llm(
    prompt: str,
    system_suffix: str = "",
    client: Any = None,
    model: str = "claude-sonnet-4-6",
    dry_run: bool = False,
    tag: str = "",
) -> str:
    """
    Call Anthropic LLM. Returns response text or dry-run placeholder.
    Falls back to a stub if client unavailable and dry_run=False.
    """
    if dry_run:
        return f"[DRY RUN] {tag}: {prompt[:60]}..."

    system = _COUNCIL_SYSTEM
    if system_suffix:
        system = f"{system}\n\n{system_suffix}"

    t0 = time.time()
    try:
        if client is None:
            import anthropic as _anth
            client = _anth.Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        elapsed = time.time() - t0
        sys.stderr.write(
            f"[debate_nodes] {tag}: {len(text)} chars in {elapsed:.1f}s\n"
        )
        return text
    except Exception as e:
        sys.stderr.write(f"[debate_nodes] {tag} error: {e}\n")
        return f"[ERROR: {e}]"


# ── 2-way Advocate / Skeptic nodes ───────────────────────────────────────────

def create_advocate(
    client: Any = None,
    model: str = "claude-sonnet-4-6",
    dry_run: bool = False,
):
    """Return node function for the Advocate (opportunity-side) debater."""

    def _node(state: dict) -> dict:
        task = state.get("task", "")
        history = state.get("history", "")
        skeptic_latest = state.get("current_response", "")

        prompt_parts = [
            f"TASK: {task}",
            "",
            "You are the Advocate. Your role is to make the strongest possible "
            "case FOR proceeding with or adopting this recommendation. "
            "Identify opportunities, strengths, and reasons to move forward.",
            "",
        ]
        if history:
            prompt_parts += [
                "DEBATE HISTORY SO FAR:",
                history,
                "",
            ]
        if skeptic_latest.startswith("Skeptic:"):
            prompt_parts += [
                "SKEPTIC'S LATEST ARGUMENT:",
                skeptic_latest[len("Skeptic:"):].strip(),
                "",
                "Rebut the Skeptic's concerns and reinforce the opportunity case.",
            ]
        else:
            prompt_parts.append(
                "Make the opening case for the opportunity. Be specific and concrete."
            )

        response_text = _call_llm(
            "\n".join(prompt_parts),
            client=client,
            model=model,
            dry_run=dry_run,
            tag="Advocate",
        )
        tagged = f"Advocate: {response_text}"

        state["advocate_history"] = (
            (state.get("advocate_history", "") + "\n\n" + tagged).strip()
        )
        state["history"] = (
            (state.get("history", "") + "\n\n" + tagged).strip()
        )
        state["current_response"] = tagged
        state["count"] = state.get("count", 0) + 1
        sys.stderr.write(
            f"[debate_nodes] Advocate turn complete (count={state['count']})\n"
        )
        return state

    return _node


def create_skeptic(
    client: Any = None,
    model: str = "claude-sonnet-4-6",
    dry_run: bool = False,
):
    """Return node function for the Skeptic (risk-side) debater."""

    def _node(state: dict) -> dict:
        task = state.get("task", "")
        history = state.get("history", "")
        advocate_latest = state.get("current_response", "")

        prompt_parts = [
            f"TASK: {task}",
            "",
            "You are the Skeptic. Your role is to challenge the recommendation "
            "rigorously. Identify risks, weaknesses, edge cases, and reasons "
            "for caution or rejection. Be adversarial but grounded in facts.",
            "",
        ]
        if history:
            prompt_parts += [
                "DEBATE HISTORY SO FAR:",
                history,
                "",
            ]
        if advocate_latest.startswith("Advocate:"):
            prompt_parts += [
                "ADVOCATE'S LATEST ARGUMENT:",
                advocate_latest[len("Advocate:"):].strip(),
                "",
                "Counter the Advocate's case with specific risks and concerns.",
            ]
        else:
            prompt_parts.append(
                "Raise your initial concerns about the proposal. Be specific."
            )

        response_text = _call_llm(
            "\n".join(prompt_parts),
            client=client,
            model=model,
            dry_run=dry_run,
            tag="Skeptic",
        )
        tagged = f"Skeptic: {response_text}"

        state["skeptic_history"] = (
            (state.get("skeptic_history", "") + "\n\n" + tagged).strip()
        )
        state["history"] = (
            (state.get("history", "") + "\n\n" + tagged).strip()
        )
        state["current_response"] = tagged
        state["count"] = state.get("count", 0) + 1
        sys.stderr.write(
            f"[debate_nodes] Skeptic turn complete (count={state['count']})\n"
        )
        return state

    return _node


def create_chief_advisor(
    client: Any = None,
    model: str = "claude-opus-4-7",
    dry_run: bool = False,
):
    """Return node function for Chief Advisor (advocacy debate judge/synthesizer)."""

    def _node(state: dict) -> dict:
        task = state.get("task", "")
        history = state.get("history", "")

        prompt = (
            f"TASK: {task}\n\n"
            "DEBATE TRANSCRIPT:\n"
            f"{history}\n\n"
            "You are the Chief Advisor. You have read the full Advocate/Skeptic debate. "
            "Synthesize both perspectives into a concrete recommendation for the operator.\n\n"
            "Structure your response as:\n"
            "SYNTHESIS: (1–2 sentences on the core tension)\n"
            "RECOMMENDATION: (PROCEED | DEFER | DECLINE | WATCH) — and why\n"
            "CONDITIONS: (any conditions or guardrails on the recommendation)\n"
            "DISSENTING NOTE: (strongest surviving concern from the Skeptic, if any)"
        )

        synthesis = _call_llm(
            prompt,
            client=client,
            model=model,
            dry_run=dry_run,
            tag="ChiefAdvisor",
        )
        state["judge_decision"] = synthesis
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        sys.stderr.write("[debate_nodes] ChiefAdvisor synthesis complete\n")
        return state

    return _node


# ── 3-way Opportunist / Guardian / Pragmatist nodes ──────────────────────────

def _build_risk_context(state: dict, speaker: str) -> str:
    """Build prompt for a 3-way risk debate turn."""
    task = state.get("task", "")
    history = state.get("history", "")
    opp = state.get("current_opportunist_response", "")
    grd = state.get("current_guardian_response", "")
    prg = state.get("current_pragmatist_response", "")

    role_prompts = {
        "opportunist": (
            "You are the Opportunist. Argue for the aggressive, high-upside path. "
            "Emphasize speed, market position, and asymmetric opportunity."
        ),
        "guardian": (
            "You are the Guardian. Argue for the conservative, risk-minimizing path. "
            "Emphasize downside protection, compliance, and reversibility."
        ),
        "pragmatist": (
            "You are the Pragmatist. Balance the Opportunist and Guardian perspectives. "
            "Identify the practical middle path that captures key upside while "
            "managing the most critical risks."
        ),
    }

    parts = [f"TASK: {task}", "", role_prompts[speaker], ""]

    if history:
        parts += ["DEBATE HISTORY:", history, ""]

    # Each debater reads all three current responses
    if opp:
        parts += ["CURRENT OPPORTUNIST POSITION:", opp, ""]
    if grd:
        parts += ["CURRENT GUARDIAN POSITION:", grd, ""]
    if prg:
        parts += ["CURRENT PRAGMATIST POSITION:", prg, ""]

    parts.append("Present your position, addressing the other two views directly.")
    return "\n".join(parts)


def create_opportunist(
    client: Any = None,
    model: str = "claude-sonnet-4-6",
    dry_run: bool = False,
):
    """Return node function for the Opportunist (aggressive) debater."""

    def _node(state: dict) -> dict:
        prompt = _build_risk_context(state, "opportunist")
        response = _call_llm(
            prompt, client=client, model=model, dry_run=dry_run, tag="Opportunist"
        )
        state["current_opportunist_response"] = response
        tagged = f"Opportunist: {response}"
        state["opportunist_history"] = (
            (state.get("opportunist_history", "") + "\n\n" + tagged).strip()
        )
        state["history"] = (
            (state.get("history", "") + "\n\n" + tagged).strip()
        )
        state["latest_speaker"] = "opportunist"
        state["count"] = state.get("count", 0) + 1
        sys.stderr.write(
            f"[debate_nodes] Opportunist turn complete (count={state['count']})\n"
        )
        return state

    return _node


def create_guardian(
    client: Any = None,
    model: str = "claude-sonnet-4-6",
    dry_run: bool = False,
):
    """Return node function for the Guardian (conservative) debater."""

    def _node(state: dict) -> dict:
        prompt = _build_risk_context(state, "guardian")
        response = _call_llm(
            prompt, client=client, model=model, dry_run=dry_run, tag="Guardian"
        )
        state["current_guardian_response"] = response
        tagged = f"Guardian: {response}"
        state["guardian_history"] = (
            (state.get("guardian_history", "") + "\n\n" + tagged).strip()
        )
        state["history"] = (
            (state.get("history", "") + "\n\n" + tagged).strip()
        )
        state["latest_speaker"] = "guardian"
        state["count"] = state.get("count", 0) + 1
        sys.stderr.write(
            f"[debate_nodes] Guardian turn complete (count={state['count']})\n"
        )
        return state

    return _node


def create_pragmatist(
    client: Any = None,
    model: str = "claude-sonnet-4-6",
    dry_run: bool = False,
):
    """Return node function for the Pragmatist (neutral) debater."""

    def _node(state: dict) -> dict:
        prompt = _build_risk_context(state, "pragmatist")
        response = _call_llm(
            prompt, client=client, model=model, dry_run=dry_run, tag="Pragmatist"
        )
        state["current_pragmatist_response"] = response
        tagged = f"Pragmatist: {response}"
        state["pragmatist_history"] = (
            (state.get("pragmatist_history", "") + "\n\n" + tagged).strip()
        )
        state["history"] = (
            (state.get("history", "") + "\n\n" + tagged).strip()
        )
        state["latest_speaker"] = "pragmatist"
        state["count"] = state.get("count", 0) + 1
        sys.stderr.write(
            f"[debate_nodes] Pragmatist turn complete (count={state['count']})\n"
        )
        return state

    return _node


def create_principal_advisor(
    client: Any = None,
    model: str = "claude-opus-4-7",
    dry_run: bool = False,
):
    """Return node function for Principal Advisor (risk debate judge/synthesizer)."""

    def _node(state: dict) -> dict:
        task = state.get("task", "")
        history = state.get("history", "")

        prompt = (
            f"TASK: {task}\n\n"
            "RISK DEBATE TRANSCRIPT:\n"
            f"{history}\n\n"
            "You are the Principal Advisor. You have read the full "
            "Opportunist/Guardian/Pragmatist risk debate. "
            "Make the final risk-adjusted recommendation for the operator.\n\n"
            "Structure your response as:\n"
            "RISK ASSESSMENT: (key risks identified, ranked by severity)\n"
            "OPPORTUNITY ASSESSMENT: (key upside factors)\n"
            "RECOMMENDATION: (PROCEED | DEFER | DECLINE | WATCH) — and why\n"
            "CONDITIONS: (mandatory risk mitigations if PROCEED)\n"
            "CONFIDENCE: (HIGH | MEDIUM | LOW) — and what would shift it"
        )

        synthesis = _call_llm(
            prompt,
            client=client,
            model=model,
            dry_run=dry_run,
            tag="PrincipalAdvisor",
        )
        state["judge_decision"] = synthesis
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        sys.stderr.write("[debate_nodes] PrincipalAdvisor synthesis complete\n")
        return state

    return _node


# ── High-level runners (used by council_graph integration) ────────────────────

def run_advocacy_debate(
    task: str,
    max_debate_rounds: int = 1,
    client: Any = None,
    dry_run: bool = False,
) -> dict:
    """
    Run full 2-way advocacy debate. Returns final AdvocacyDebateState dict.

    Sequence (1 round, max_debate_rounds=1):
      Advocate(0) → Skeptic(1) → ChiefAdvisor
    """
    state: dict = {
        "task": task,
        "advocate_history": "",
        "skeptic_history": "",
        "history": "",
        "current_response": "",
        "judge_decision": "",
        "count": 0,
        "max_debate_rounds": max_debate_rounds,
    }

    from debate_logic import advocacy_next_speaker

    advocate_fn = create_advocate(client=client, dry_run=dry_run)
    skeptic_fn = create_skeptic(client=client, dry_run=dry_run)
    judge_fn = create_chief_advisor(client=client, dry_run=dry_run)

    sys.stderr.write(
        f"[debate_nodes] Starting advocacy debate: task={task[:60]!r} "
        f"rounds={max_debate_rounds}\n"
    )

    while True:
        next_node = advocacy_next_speaker(state)
        if next_node == "judge":
            break
        elif next_node == "advocate":
            state = advocate_fn(state)
        elif next_node == "skeptic":
            state = skeptic_fn(state)

    state = judge_fn(state)
    sys.stderr.write(
        f"[debate_nodes] Advocacy debate complete: "
        f"{state['count']} turns, judge_decision={len(state['judge_decision'])} chars\n"
    )
    return state


def run_risk_debate(
    task: str,
    max_risk_discuss_rounds: int = 1,
    client: Any = None,
    dry_run: bool = False,
) -> dict:
    """
    Run full 3-way risk debate. Returns final RiskDebateState dict.

    Sequence (1 round, max_risk_discuss_rounds=1):
      Opportunist(0) → Guardian(1) → Pragmatist(2) → PrincipalAdvisor
    """
    state: dict = {
        "task": task,
        "opportunist_history": "",
        "guardian_history": "",
        "pragmatist_history": "",
        "history": "",
        "latest_speaker": "",
        "current_opportunist_response": "",
        "current_guardian_response": "",
        "current_pragmatist_response": "",
        "judge_decision": "",
        "count": 0,
        "max_risk_discuss_rounds": max_risk_discuss_rounds,
    }

    from debate_logic import risk_next_speaker

    opportunist_fn = create_opportunist(client=client, dry_run=dry_run)
    guardian_fn = create_guardian(client=client, dry_run=dry_run)
    pragmatist_fn = create_pragmatist(client=client, dry_run=dry_run)
    judge_fn = create_principal_advisor(client=client, dry_run=dry_run)

    sys.stderr.write(
        f"[debate_nodes] Starting risk debate: task={task[:60]!r} "
        f"rounds={max_risk_discuss_rounds}\n"
    )

    while True:
        next_node = risk_next_speaker(state)
        if next_node == "judge":
            break
        elif next_node == "opportunist":
            state = opportunist_fn(state)
        elif next_node == "guardian":
            state = guardian_fn(state)
        elif next_node == "pragmatist":
            state = pragmatist_fn(state)

    state = judge_fn(state)
    sys.stderr.write(
        f"[debate_nodes] Risk debate complete: "
        f"{state['count']} turns, judge_decision={len(state['judge_decision'])} chars\n"
    )
    return state
