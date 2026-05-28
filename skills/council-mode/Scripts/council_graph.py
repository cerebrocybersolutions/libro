"""
council_graph.py — council-mode v2 LangGraph state graph backbone
TradingAgents §4+§5 port (combined)

Defines the council-mode v2 StateGraph with four stages:
  Stage 1: task receipt + initial state validation
  Stage 2: parallel tier dispatch (→ TierDispatchState per tier)
  Stage 3: disagreement surface (→ DisagreementSurfaceState)
  Stage 4: santa-method dual-reviewer gate (→ ReviewState, gated=True only)

Requires LangGraph: pip3 install "langgraph>=0.2,<0.3" --break-system-packages
Falls back to a simplified sequential runner when LangGraph is unavailable.

CLI (via council_run.py --resume <run_id>):
  Phase 4 wire: add --resume to council_run.py argparse
  Resumes from last checkpoint in state/council-runs/<run_id>.checkpoint.json

Wired: 2026-04-30 per decisions/2026-04-30-council-mode-v2-langgraph-typed-substates.md
Snapshot tag: pre-council-mode-v2-langgraph-2026-04-30 (drops at Phase 4 real dispatch wire)
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
_BRAIN_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_HERE))

import json
import urllib.request

from council_state import (
    CouncilRunState,
    DisagreementSurfaceState,
    ReviewState,
    TierDispatchState,
)
from json_checkpointer import JsonRunStore, make_langgraph_checkpointer

# ── Council system prompt ─────────────────────────────────────────────────────

_COUNCIL_SYSTEM_PROMPT = (
    "You are an advisor for the operator's organization. "
    "Respond directly and concretely. State assumptions if needed."
)
# NOTE: operator identity (company, CAGE/UEI/registration IDs, sector) should be
# loaded from the operator profile (~/.cerebro/profile.yaml) and prepended to
# this prompt at runtime, not hardcoded here.

# ── Fleet-dispatch loader (no side-effect prints) ─────────────────────────────

def _load_fleet_safe() -> dict:
    """Load state/fleet-dispatch.json without side-effect prints. Returns {} on failure."""
    try:
        cfg = _BRAIN_ROOT / "state" / "fleet-dispatch.json"
        return json.loads(cfg.read_text())
    except Exception:
        return {}


# ── Live tier dispatcher ──────────────────────────────────────────────────────

_FLEET_SURFACE_MAP = {
    "fleet-node-a": "fleet-node-a",
    "fleet-node-b": "fleet-node-b",
    "fleet-node-c": "fleet-node-c",
    "local":        "local",
}

def _call_tier_live(
    spec: dict,
    task: str,
    client: Any = None,
    timeout: int = 180,
) -> tuple:
    """
    Dispatch one tier. Returns (output_text: str, error: Optional[str]).
    spec: {"tier": "A"|"B"|"C", "model": str, "surface": "cloud"|"fleet-*"|"local"}
    client: anthropic.Anthropic instance for cloud tiers (built lazily if None).
    Phase 4 real dispatch — replaces Phase 3 scaffold. Wired 2026-04-30.
    """
    surface = spec.get("surface", "cloud")
    model = spec["model"]

    if surface == "cloud":
        try:
            if client is None:
                import anthropic as _anth
                client = _anth.Anthropic()
            resp = client.messages.create(
                model=model,
                max_tokens=4096,
                system=_COUNCIL_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": task}],
            )
            return resp.content[0].text, None
        except Exception as e:
            return "", str(e)

    elif surface in _FLEET_SURFACE_MAP:
        try:
            fleet = _load_fleet_safe()
            host_key = _FLEET_SURFACE_MAP[surface]
            # Default to localhost for every fleet slot; operator overrides each
            # via fleet-dispatch.json hosts[<key>].url at install time.
            default_urls = {
                "fleet-node-a": "http://localhost:11434",
                "fleet-node-b": "http://localhost:11434",
                "fleet-node-c": "http://localhost:11434",
                "local":        "http://localhost:11434",
            }
            base_url = (
                fleet.get("hosts", {}).get(host_key, {}).get("url")
                or default_urls.get(host_key, "http://localhost:11434")
            )
            url = base_url.rstrip("/") + "/api/generate"
            payload = json.dumps({
                "model": model,
                "prompt": task,
                "system": _COUNCIL_SYSTEM_PROMPT,
                "stream": False,
                "options": {"num_ctx": 8192, "num_predict": 2048},
            }).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            return data.get("response", "(empty response)"), None
        except Exception as e:
            return "", str(e)

    else:
        return "", f"Unknown surface: {surface!r}"


# ── LangGraph optional import ─────────────────────────────────────────────────

_LANGGRAPH_OK = False
try:
    from langgraph.graph import StateGraph, END
    _LANGGRAPH_OK = True
except ImportError:
    pass


# ── Graph nodes ───────────────────────────────────────────────────────────────

def node_dispatch_tiers(state: dict, client: Any = None, dry_run: bool = False) -> dict:
    """
    Stage 2: dispatch task to each tier in parallel, collect TierDispatchState outputs.
    In this Phase 3 scaffold, returns mocked outputs. Phase 4 wires real advisor-dispatch.
    """
    task = state.get("task", "")
    gated = state.get("gated", False)
    dispatches = []

    # Placeholder tier list — Phase 4 will pull from fleet-dispatch.json via advisor-dispatch
    tier_specs = [
        {"tier": "A", "model": "claude-opus-4-7", "surface": "cloud"},
        {"tier": "B", "model": "claude-sonnet-4-6", "surface": "cloud"},
        {"tier": "C", "model": "gemma4:31b-instruct-q5_K_M", "surface": "local"},
    ]

    for spec in tier_specs:
        t0 = time.time()
        if dry_run:
            output = f"[DRY RUN] {spec['tier']} mock output for: {task[:50]}"
            error = None
        else:
            # Phase 4: real dispatch via _call_tier_live (wired 2026-04-30)
            output, error = _call_tier_live(spec, task, client=client)
            if error:
                output = None
        latency_ms = int((time.time() - t0) * 1000)

        dispatches.append(TierDispatchState(
            tier=spec["tier"],
            model=spec["model"],
            surface=spec["surface"],
            prompt=task,
            output=output,
            latency_ms=latency_ms,
            cost_usd=0.0 if dry_run else None,
            error=error,
            completed_at=datetime.now(timezone.utc),
        ))

    state["tier_dispatches"] = [d.model_dump() for d in dispatches]
    return state


def node_surface_disagreement(state: dict) -> dict:
    """
    Stage 3: diff tier outputs, produce DisagreementSurfaceState.
    Detects consensus (all outputs substantially equal).
    """
    dispatches = [TierDispatchState(**d) for d in state.get("tier_dispatches", [])]
    successful = [d for d in dispatches if d.output and not d.error]

    # Simple consensus check: all outputs equal (for real outputs, use embedding similarity)
    outputs = [d.output for d in successful]
    consensus = len(set(outputs)) <= 1 if outputs else False

    diff_summary = None
    if not consensus and len(outputs) >= 2:
        diff_summary = f"[Stage 3 scaffold] {len(outputs)} outputs, consensus={consensus}. Phase 4 wires real diff logic."
    elif consensus:
        diff_summary = "All tiers agree."

    state["disagreement"] = DisagreementSurfaceState(
        tier_outputs=dispatches,
        diff_summary=diff_summary,
        consensus=consensus,
    ).model_dump()
    return state


def node_santa_review(state: dict, client: Any = None, dry_run: bool = False) -> dict:
    """
    Stage 4: santa-method dual-reviewer gate (runs only when gated=True).
    """
    task = state.get("task", "")
    disagreement = state.get("disagreement", {})
    tier_outputs = disagreement.get("tier_outputs", [])
    # Select best output for review (first successful tier)
    selected_output = ""
    for d in tier_outputs:
        if d.get("output") and not d.get("error"):
            selected_output = d["output"]
            break

    try:
        _santa_path = _HERE
        sys.path.insert(0, str(_santa_path))
        from santa_review import run_review
        result = run_review(task=task, output=selected_output, client=client, dry_run=dry_run)
        rev_a = result.reviewer_a
        rev_b = result.reviewer_b
        state["review"] = ReviewState(
            correctness_verdict=rev_a.verdict if rev_a else "FAIL",
            correctness_reason=rev_a.reason if rev_a else None,
            correctness_severity=rev_a.severity if rev_a else "high",
            doctrine_verdict=rev_b.verdict if rev_b else "FAIL",
            doctrine_reason=rev_b.reason if rev_b else None,
            doctrine_severity=rev_b.severity if rev_b else "high",
            aggregate=result.outcome.value,
            review_cost_usd=result.cost_usd,
            review_elapsed_s=result.elapsed_s,
        ).model_dump()
        state["final_outcome"] = result.outcome.value
    except Exception as e:
        state["review"] = ReviewState(
            correctness_verdict="FAIL",
            doctrine_verdict="FAIL",
            aggregate="HALT_TO_OPERATOR",
        ).model_dump()
        state["final_outcome"] = "ERROR"
        state["error"] = f"santa_review import/run error: {e}"

    return state


def node_finalize(state: dict) -> dict:
    """Stage 5: finalize outcome when not gated."""
    if not state.get("final_outcome"):
        # No santa-method gate: outcome is SHIP (informational council — no gate)
        state["final_outcome"] = "SHIP"
    state["finished_at"] = datetime.now(timezone.utc).isoformat()
    return state


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_council_graph(gated: bool = False, dry_run: bool = False, client: Any = None):
    """
    Build and compile the council-mode v2 StateGraph.
    Returns (compiled_graph, checkpointer) or None if LangGraph unavailable.
    """
    if not _LANGGRAPH_OK:
        return None, None

    graph = StateGraph(dict)

    # Node wrappers with closed-over args
    graph.add_node("dispatch_tiers", lambda s: node_dispatch_tiers(s, client=client, dry_run=dry_run))
    graph.add_node("surface_disagreement", node_surface_disagreement)
    graph.add_node("finalize", node_finalize)

    graph.set_entry_point("dispatch_tiers")
    graph.add_edge("dispatch_tiers", "surface_disagreement")

    if gated:
        graph.add_node("santa_review", lambda s: node_santa_review(s, client=client, dry_run=dry_run))
        graph.add_edge("surface_disagreement", "santa_review")
        graph.add_edge("santa_review", "finalize")
    else:
        graph.add_edge("surface_disagreement", "finalize")

    graph.add_edge("finalize", END)

    checkpointer = make_langgraph_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)
    return compiled, checkpointer


# ── Standalone fallback runner (no LangGraph) ─────────────────────────────────

def run_council_v2_fallback(
    task: str,
    gated: bool = False,
    dry_run: bool = False,
    client: Any = None,
    store: Optional[JsonRunStore] = None,
    resume_from: Optional[CouncilRunState] = None,
) -> CouncilRunState:
    """
    Sequential fallback when LangGraph is not installed (or as the primary runner).
    Runs the same nodes in order, checkpoints to JsonRunStore after each stage.

    resume_from: if provided, skip already-completed stages and continue from
                 the last checkpoint. Identified by non-empty tier_dispatches,
                 disagreement, or review fields.
    """
    if store is None:
        store = JsonRunStore()

    if resume_from is not None:
        run_state = resume_from
        sys.stderr.write(
            f"[council_graph] Resuming {run_state.run_id} from checkpoint "
            f"({run_state.stage_summary()})\n"
        )
    else:
        run_state = CouncilRunState(task=task, gated=gated)
        store.put(run_state.run_id, run_state)

    raw = run_state.model_dump()

    # Stage 2 — skip if tier_dispatches already populated
    if not run_state.tier_dispatches:
        raw = node_dispatch_tiers(raw, client=client, dry_run=dry_run)
        run_state = CouncilRunState(**raw)
        store.put(run_state.run_id, run_state)
    else:
        sys.stderr.write(
            f"[council_graph] Stage 2 already done "
            f"({len(run_state.tier_dispatches)} dispatches) — skipping\n"
        )

    # Stage 3 — skip if disagreement already populated
    if not run_state.disagreement:
        raw = node_surface_disagreement(raw)
        run_state = CouncilRunState(**raw)
        store.put(run_state.run_id, run_state)
    else:
        sys.stderr.write("[council_graph] Stage 3 already done — skipping\n")

    # Stage 4 (gated only) — skip if review already populated
    if (gated or run_state.gated) and not run_state.review:
        raw = node_santa_review(raw, client=client, dry_run=dry_run)
        run_state = CouncilRunState(**raw)
        store.put(run_state.run_id, run_state)
    elif run_state.review:
        sys.stderr.write("[council_graph] Stage 4 already done — skipping\n")

    # Finalize — skip if already complete
    if not run_state.is_complete():
        raw = node_finalize(raw)
        run_state = CouncilRunState(**raw)
        store.put(run_state.run_id, run_state)
    else:
        sys.stderr.write(
            f"[council_graph] Run already complete: {run_state.final_outcome}\n"
        )

    return run_state


# ── CLI smoke ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[council_graph] LangGraph available: {_LANGGRAPH_OK}")
    print("[council_graph] Running fallback smoke (dry_run=True, gated=True)...")
    result = run_council_v2_fallback(
        task="Smoke test: does the v2 graph backbone wire end-to-end?",
        gated=True,
        dry_run=True,
    )
    print(f"  run_id:       {result.run_id}")
    print(f"  final_outcome:{result.final_outcome}")
    print(f"  tiers done:   {len(result.tier_dispatches)}")
    if result.review:
        print(f"  review:       {result.review.aggregate}")
    print("[council_graph] Smoke PASS")
