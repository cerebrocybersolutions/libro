#!/usr/bin/env python3
"""
council_run.py — Council Mode — Adversarial Parallel Comparison

Runs the same task across multiple model tiers and/or providers (Claude + Ollama)
in parallel, then produces a diff report surfacing disagreements and failure modes.

The purpose is NOT consensus. The purpose is to show where each model FAILS so
routing can avoid known failure modes.

Usage:
  python3 council_run.py --task "Should we pursue this opportunity?" --dry-run
  python3 council_run.py --task "Draft a vendor quote request"
  python3 council_run.py --task "..." --participants C-claude,B-claude,C-local
  python3 council_run.py --task "..." --participants full
  python3 council_run.py --task "..." --diff-question "Will any model catch the qualifying constraint?"

Requirements:
  pip3 install anthropic requests  (--break-system-packages on macOS)
  export ANTHROPIC_API_KEY=your_key_here
  Ollama running at http://localhost:11434 (if local participants selected)
"""

import argparse
import os
import sys
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yaml  # used for aggregator config; graceful degradation if missing
    _YAML_OK = True
except ImportError:
    _YAML_OK = False

# Heartbeat + persona loader live next to this script. Imports are
# local-relative so the council skill can be moved without breaking.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from heartbeat import Heartbeat  # noqa: E402
try:
    from persona_loader import PersonaLoader  # noqa: E402
except ImportError:
    PersonaLoader = None  # Graceful degradation: neutral runs still work.

# MemoryWriter context fencing (Phase +2 wiring point)
# fence()/unfence() wrap recalled memory injected into prompts so it can be
# stripped before surfacing to the user. No active recall injection here yet —
# import now, use when Phase +2 lands. Graceful degradation if mw unavailable.
try:
    _mw_path = str(Path(__file__).resolve().parents[1] / "memory-writer" / "memory_writer.py")
    import importlib.util as _ilu
    _mw_spec = _ilu.spec_from_file_location("memory_writer", _mw_path)
    _mw_mod = _ilu.module_from_spec(_mw_spec)
    _mw_spec.loader.exec_module(_mw_mod)  # type: ignore[union-attr]
    from memory_writer import fence as _mw_fence, unfence as _mw_unfence  # type: ignore
    _MW_FENCE_OK = True
except Exception:
    _MW_FENCE_OK = False
    def _mw_fence(content, **_kw): return content      # type: ignore[misc]
    def _mw_unfence(text): return text                  # type: ignore[misc]

# ── Configuration ────────────────────────────────────────────────────────────

# Auto-detect from script location; override with CEREBRO_BRAIN_ROOT env var if needed.
# Workspace layout:  <BRAIN_ROOT>/skills/<x>/Scripts/this.py     → parents[3] = <BRAIN_ROOT>
# Installed layout:  <target>/.claude/skills/<x>/Scripts/this.py → parents[3] = <target>/.claude
#                    (Brain root for installed targets is the sibling master-brain/ dir.)
def _resolve_brain_root() -> Path:
    env = os.environ.get("CEREBRO_BRAIN_ROOT") or os.environ.get("CEREBRO_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    p = Path(__file__).resolve().parents[3]
    if p.name == ".claude" and (p.parent / "master-brain").exists():
        return p.parent / "master-brain"
    return p

BRAIN_ROOT = _resolve_brain_root()
SKILL_ROOT = BRAIN_ROOT / "skills" / "council-mode"
LOG_DIR    = SKILL_ROOT / "logs"
DIFF_DIR   = LOG_DIR / "diffs"
RUN_LOG    = LOG_DIR / "council_runs.md"
SHARED_LOG = BRAIN_ROOT / "skills" / "advisor-dispatch" / "logs" / "daily_usage.md"

# --- fleet-dispatch config load (lazy) --------------------------------------
# Loaded on first call to fleet_url / fleet_model — keeps --help and cloud-only
# runs working even when no local fleet config is installed yet.
_FLEET_CACHE = None

def _load_fleet_dispatch():
    global _FLEET_CACHE
    if _FLEET_CACHE is not None:
        return _FLEET_CACHE
    brain_root = _resolve_brain_root()
    # Try installed path first, fall back to template (operator has not yet
    # populated their local fleet config), fall back to None (cloud-only mode).
    candidates = [
        brain_root / "state" / "fleet-dispatch.json",
        brain_root / "state" / "fleet-dispatch.template.json",
        brain_root / "fleet-dispatch.template.json",
    ]
    data = None
    for cfg in candidates:
        if cfg.exists():
            with cfg.open() as f:
                data = json.load(f)
            break
    if data is None:
        _FLEET_CACHE = ({}, None)
        return _FLEET_CACHE
    env_override_key = data.get("env_override")
    env_override = os.environ.get(env_override_key) if isinstance(env_override_key, str) else None
    _FLEET_CACHE = (data, env_override)
    return _FLEET_CACHE

def fleet_url(tier_slot: str, prefer_fallback: bool = False) -> str:
    fleet, env_override = _load_fleet_dispatch()
    if env_override:
        return env_override
    if not fleet:
        raise RuntimeError("fleet-dispatch config not installed; cannot resolve local tier. "
                           "Run install.sh to populate state/fleet-dispatch.json or use cloud-only tiers.")
    route = fleet["routing"].get(tier_slot) or {}
    host_key = route.get("fallback" if prefer_fallback else "primary")
    if not host_key:
        raise ValueError(f"fleet-dispatch: no host for tier slot {tier_slot!r}")
    return fleet["hosts"][host_key]["url"]

def fleet_model(tier_slot: str) -> str:
    fleet, _ = _load_fleet_dispatch()
    if not fleet:
        raise RuntimeError("fleet-dispatch config not installed; cannot resolve model for "
                           f"tier slot {tier_slot!r}. Run install.sh or use cloud-only tiers.")
    route = fleet["routing"].get(tier_slot) or {}
    model = route.get("model")
    if not model:
        raise ValueError(f"fleet-dispatch: no model for tier slot {tier_slot!r}")
    return model
# --- end fleet-dispatch config load -----------------------------------------

# Canonical host + model bindings: master-brain/state/fleet-dispatch.json
OLLAMA_URL = fleet_url("C-local") + "/api/generate"

# Participant roster — US-only lock applied 2026-04-21 per fleet-dispatch.json.
# B-local retargeted from qwen2.5:14b (Chinese origin — excluded) to phi4:14b (US/Microsoft).
# B-alt removed — now redundant with B-local (same model, same host).
#   C-local  = llama3.1:8b  (Meta,      ~5GB Q4_K_M)  — fast daily driver
#   B-local  = phi4:14b     (Microsoft, ~9GB Q4_K_M)  — Team Lead tier, US-origin
# SHIPPED (GovCon OS) defaults are US+EU only per fleet-dispatch.json routing.
PARTICIPANTS = {
    "C-claude":  {"provider": "claude", "model": "claude-haiku-4-5",    "tier": "C",  "cost_tier": "haiku"},
    "B-claude":  {"provider": "claude", "model": "claude-sonnet-4-6",   "tier": "B",  "cost_tier": "sonnet"},
    "A-claude":  {"provider": "claude", "model": "claude-sonnet-4-6",   "tier": "A",  "cost_tier": "sonnet", "advisor": "claude-opus-4-7"},
    "A+-claude": {"provider": "claude", "model": "claude-opus-4-7",     "tier": "A+", "cost_tier": "opus"},
    "C-local":   {"provider": "ollama", "model": fleet_model("C-local"), "tier": "C",  "cost_tier": "local"},
    "B-local":   {"provider": "ollama", "model": fleet_model("B-local"), "tier": "B",  "cost_tier": "local"},
}

FULL_ROSTER = ["C-claude", "B-claude", "A-claude", "A+-claude", "C-local", "B-local"]

# LEAN_ROSTER: executive-stack pattern — 5 slots matching "one lead + 2-3 specialist
# advisors + one executor + one final arbiter."
#   A+-claude  → lead (chief strategist, Opus solo)
#   A-claude   → final arbiter (Sonnet + Opus advisor on demand)
#   B-claude   → specialist (Director/Manager, Sonnet solo)
#   C-claude   → specialist (Analyst, Haiku)
#   C-local    → executor / second-opinion (local model, free, fast)
# Rationale: never burn 6 models on fake consensus. Lean catches disagreement faster
# and leaves budget for deeper comparisons via `--participants full`.
LEAN_ROSTER = ["A+-claude", "A-claude", "B-claude", "C-claude", "C-local"]

COST_RATES = {  # per 1M tokens (input, output)
    "haiku":  (0.80, 4.00),
    "sonnet": (3.00, 15.00),
    "opus":   (15.00, 75.00),
    "local":  (0.0, 0.0),
}

TIMEOUT_SEC = 120
MAX_CLAUDE_CONCURRENCY = 3

# Heartbeat cadence — how often the background thread emits a "running"
# summary line while slots are in-flight. 30s matches the feedback-memory
# baseline (2026-04-17). Bump via CEREBRO_HEARTBEAT_SEC env var if desired.
HEARTBEAT_CADENCE_SEC = int(os.environ.get("CEREBRO_HEARTBEAT_SEC", "30"))

SYSTEM_PROMPT = (
    "You are an operator assistant for the operator's organization. "
    "Respond directly and concretely. State assumptions if needed."
)
# NOTE: operator identity (company, CAGE/UEI/registration IDs, sector) should be
# loaded from the operator profile (~/.cerebro/profile.yaml) and prepended to
# this prompt at runtime, not hardcoded here.


def compose_system_prompt(base: str, persona_prompt: Optional[str]) -> str:
    """
    Compose the system prompt for a council slot. If a persona prompt is
    attached, the operator context goes first (so the model knows the business
    constraints) and the persona voice layer goes second (so it shapes the
    output). Separated by a clear divider to keep the layers legible if the
    prompt is logged.
    """
    if not persona_prompt:
        return base
    return (
        f"{base}\n\n"
        f"---\n\n"
        f"## Voice / role for this response\n\n"
        f"{persona_prompt.strip()}\n"
    )


# ── Participant dispatch ──────────────────────────────────────────────────────

def run_claude_participant(client, slot: str, task: str,
                           system_prompt: str = SYSTEM_PROMPT) -> dict:
    """Run a single Claude-tier participant. Returns a result dict."""
    cfg = PARTICIPANTS[slot]
    start = time.time()
    try:
        if cfg["tier"] == "A":
            # Tier A uses the advisor tool
            resp = client.beta.messages.create(
                model=cfg["model"],
                max_tokens=8096,
                system=system_prompt,
                tools=[{"type": "advisor_20260301", "name": "advisor", "model": "claude-opus-4-7", "max_uses": 3}],
                messages=[{"role": "user", "content": task}],
                betas=["advisor-tool-2026-03-01"],
            )
            advisor_calls = sum(
                1 for b in resp.content
                if hasattr(b, "type") and b.type == "tool_use" and b.name == "advisor"
            )
            text = " ".join(b.text for b in resp.content if hasattr(b, "text"))
        elif cfg["tier"] == "A+":
            # Minimal-change fix 2026-04-17: prior config was
            # {"type": "adaptive", "effort": "medium"} which returned
            # 400 "thinking.adaptive.effort: Extra inputs are not
            # permitted" on the live council run. The `effort` key is
            # not valid under adaptive thinking.
            #
            # Do NOT swap to {"type": "enabled", "budget_tokens": N} —
            # advisor-dispatch SKILL.md and stage2_configure.md both
            # document that `type=enabled` returns 400 on Opus 4.7 and
            # adaptive is required. Minimal fix: drop `effort` only.
            resp = client.beta.messages.create(
                model=cfg["model"],
                max_tokens=16000,
                system=system_prompt,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": task}],
                betas=["interleaved-thinking-2025-05-14"],
            )
            advisor_calls = 0
            text = " ".join(
                b.text for b in resp.content
                if hasattr(b, "text") and getattr(b, "type", None) == "text"
            )
        else:
            resp = client.messages.create(
                model=cfg["model"],
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": task}],
            )
            advisor_calls = 0
            text = resp.content[0].text

        elapsed = time.time() - start
        in_rate, out_rate = COST_RATES[cfg["cost_tier"]]
        cost = (resp.usage.input_tokens / 1_000_000 * in_rate +
                resp.usage.output_tokens / 1_000_000 * out_rate)
        if advisor_calls:
            # Opus advisor ~500 in + 500 out per call
            cost += advisor_calls * (500 / 1_000_000 * COST_RATES["opus"][0] +
                                     500 / 1_000_000 * COST_RATES["opus"][1])
        return {
            "slot": slot, "status": "ok", "text": text,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "advisor_calls": advisor_calls, "cost": cost, "elapsed": elapsed,
        }
    except Exception as e:
        return {
            "slot": slot, "status": "failed", "text": "",
            "input_tokens": 0, "output_tokens": 0,
            "advisor_calls": 0, "cost": 0.0,
            "elapsed": time.time() - start, "error": str(e),
        }


def run_ollama_participant(slot: str, task: str,
                           system_prompt: str = SYSTEM_PROMPT) -> dict:
    """Run a single Ollama local participant. Returns a result dict."""
    import requests
    cfg = PARTICIPANTS[slot]
    start = time.time()
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": cfg["model"],
                "system": system_prompt,
                "prompt": task,
                "stream": False,
            },
            timeout=TIMEOUT_SEC,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "")
        elapsed = time.time() - start
        return {
            "slot": slot, "status": "ok", "text": text,
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "advisor_calls": 0, "cost": 0.0, "elapsed": elapsed,
        }
    except Exception as e:
        return {
            "slot": slot, "status": "failed", "text": "",
            "input_tokens": 0, "output_tokens": 0,
            "advisor_calls": 0, "cost": 0.0,
            "elapsed": time.time() - start, "error": str(e),
        }


# ── Orchestration ─────────────────────────────────────────────────────────────

def run_council(participants: list, task: str, dry_run: bool, client,
                personas_enabled: bool = True) -> list:
    """
    Dispatch to all selected participants. Returns list of result dicts.

    personas_enabled (default True): if the persona map loads cleanly, each
    slot's system prompt is composed as `SYSTEM_PROMPT + persona.system_prompt`
    and heartbeat gets the persona voice banks. Set False (or pass
    --no-personas on the CLI) for neutral runs.
    """
    # Load persona map once. If it's missing or opt-out, we fall back to
    # neutral behavior cleanly — no code path needs a special case later.
    loader = None
    if personas_enabled and PersonaLoader is not None:
        try:
            candidate = PersonaLoader()
            if candidate.enabled:
                loader = candidate
        except Exception:
            loader = None

    def system_prompt_for(slot: str) -> str:
        if loader is None:
            return SYSTEM_PROMPT
        return compose_system_prompt(SYSTEM_PROMPT, loader.system_prompt_for(slot))

    if dry_run:
        print(f"\n[DRY RUN] Would dispatch to {len(participants)} participants:")
        for slot in participants:
            cfg = PARTICIPANTS[slot]
            persona_name = loader.persona_name_for(slot) if loader else None
            persona_tag = f" [voice: {persona_name}]" if persona_name else ""
            print(f"  - {slot:<12} {cfg['provider']:<7} {cfg['model']}{persona_tag}")
        persona_state = loader.version if loader else "off"
        print(f"  (heartbeat cadence: {HEARTBEAT_CADENCE_SEC}s, personas: {persona_state})")
        return [
            {"slot": s, "status": "dry-run", "text": "[dry run]",
             "input_tokens": 0, "output_tokens": 0, "advisor_calls": 0,
             "cost": 0.0, "elapsed": 0.0}
            for s in participants
        ]

    results = []

    # Split by provider — run Claude in parallel (capped), Ollama sequential on single-GPU rigs
    claude_slots = [s for s in participants if PARTICIPANTS[s]["provider"] == "claude"]
    ollama_slots = [s for s in participants if PARTICIPANTS[s]["provider"] == "ollama"]

    # Heartbeat — kills silent waits. Voice banks attach via the persona
    # loader when enabled. If no loader, neutral messages still fire.
    persona_banks = loader.persona_banks_for(participants) if loader else {}
    hb = Heartbeat(
        slots=participants,
        cadence_sec=HEARTBEAT_CADENCE_SEC,
        personas=persona_banks,
    )
    hb.start()

    try:
        # Claude — thread-pooled. slot_started fires INSIDE the worker so
        # it reflects actual start (pool may queue some slots past
        # MAX_CLAUDE_CONCURRENCY).
        if claude_slots:
            def _claude_worker(slot):
                hb.slot_started(slot)
                return run_claude_participant(
                    client, slot, task, system_prompt=system_prompt_for(slot)
                )

            with ThreadPoolExecutor(max_workers=MAX_CLAUDE_CONCURRENCY) as pool:
                futures = {pool.submit(_claude_worker, s): s for s in claude_slots}
                for fut in as_completed(futures):
                    r = fut.result()
                    hb.slot_completed(r["slot"], r["elapsed"], r["status"])
                    results.append(r)

        # Ollama — sequential to avoid GPU contention
        for slot in ollama_slots:
            hb.slot_started(slot)
            r = run_ollama_participant(slot, task,
                                       system_prompt=system_prompt_for(slot))
            hb.slot_completed(r["slot"], r["elapsed"], r["status"])
            results.append(r)
    finally:
        hb.stop()

    # Sort results to original participant order
    order = {s: i for i, s in enumerate(participants)}
    results.sort(key=lambda r: order.get(r["slot"], 99))
    return results


# ── MoA: async fan-out + aggregator ──────────────────────────────────────────

def _load_aggregator_config() -> dict:
    """Load config/aggregator.yaml; return defaults if unavailable."""
    cfg_path = SKILL_ROOT / "config" / "aggregator.yaml"
    defaults = {
        "model": "A-claude",
        "temperature": 0.4,
        "system": (
            "You are the Cerebro Council Aggregator. {N} reference models were given "
            "the same task. Produce a disagreement map with sections: CONSENSUS / "
            "SPLIT / UNIQUE-CALL / FAILURE-MODES / ROUTING-RECOMMENDATION."
        ),
        "user_template": "TASK: {task}\n\nLEG RESULTS ({N} total):\n{legs_block}\n\nProduce the disagreement map.",
    }
    if not _YAML_OK or not cfg_path.exists():
        return defaults
    try:
        with cfg_path.open() as f:
            data = yaml.safe_load(f)
        defaults.update({k: v for k, v in (data or {}).items() if v is not None})
    except Exception:
        pass
    return defaults


def _load_aggregator_persona() -> Optional[str]:
    """Load personas/aggregator.md; return None if unavailable."""
    p = SKILL_ROOT / "personas" / "aggregator.md"
    if p.exists():
        try:
            return p.read_text()
        except Exception:
            pass
    return None


async def _run_participant_async(slot: str, task: str, client,
                                  system_prompt: str = SYSTEM_PROMPT) -> dict:
    """Async wrapper around blocking participant runners."""
    cfg = PARTICIPANTS[slot]
    loop = asyncio.get_event_loop()
    if cfg["provider"] == "claude":
        return await loop.run_in_executor(
            None, run_claude_participant, client, slot, task, system_prompt
        )
    else:
        return await loop.run_in_executor(
            None, run_ollama_participant, slot, task, system_prompt
        )


async def run_council_moa_async(participants: list, task: str, dry_run: bool,
                                 client, aggregator_slot: str,
                                 personas_enabled: bool = True) -> dict:
    """
    MoA: asyncio.gather fan-out at temp=0.6, then single aggregator synthesis
    at temp=0.4. Returns {'legs': [...], 'aggregator': {...}}.
    """
    # Persona setup (same as legacy path)
    loader = None
    if personas_enabled and PersonaLoader is not None:
        try:
            candidate = PersonaLoader()
            if candidate.enabled:
                loader = candidate
        except Exception:
            pass

    def system_prompt_for(slot: str) -> str:
        if loader is None:
            return SYSTEM_PROMPT
        return compose_system_prompt(SYSTEM_PROMPT, loader.system_prompt_for(slot))

    if dry_run:
        print(f"\n[DRY RUN / MoA] Would dispatch to {len(participants)} reference legs + 1 aggregator ({aggregator_slot}):")
        for slot in participants:
            cfg = PARTICIPANTS[slot]
            print(f"  ref: {slot:<12} {cfg['provider']:<7} {cfg['model']}")
        agg_cfg = PARTICIPANTS.get(aggregator_slot, {})
        print(f"  agg: {aggregator_slot:<12} {agg_cfg.get('provider','?'):<7} {agg_cfg.get('model','?')} (temp=0.4)")
        print(f"  (temp=0.6 for reference legs)")
        legs = [
            {"slot": s, "status": "dry-run", "text": "[dry run]",
             "input_tokens": 0, "output_tokens": 0, "advisor_calls": 0,
             "cost": 0.0, "elapsed": 0.0}
            for s in participants
        ]
        aggregator_result = {
            "slot": aggregator_slot, "status": "dry-run", "text": "[dry run aggregator]",
            "input_tokens": 0, "output_tokens": 0, "advisor_calls": 0,
            "cost": 0.0, "elapsed": 0.0,
        }
        return {"legs": legs, "aggregator": aggregator_result}

    # Phase 1: Reference fan-out at temp=0.6 via asyncio.gather
    # (existing runners are sync; we wrap them with run_in_executor)
    wall_start = time.time()

    async def _run_leg(slot):
        cfg = PARTICIPANTS[slot]
        loop = asyncio.get_event_loop()
        if cfg["provider"] == "claude":
            return await loop.run_in_executor(
                None, run_claude_participant, client, slot, task, system_prompt_for(slot)
            )
        else:
            return await loop.run_in_executor(
                None, run_ollama_participant, slot, task, system_prompt_for(slot)
            )

    hb = Heartbeat(
        slots=participants + [f"{aggregator_slot}(agg)"],
        cadence_sec=HEARTBEAT_CADENCE_SEC,
        personas={},
    )
    hb.start()

    try:
        coros = [_run_leg(s) for s in participants]
        leg_results_raw = await asyncio.gather(*coros, return_exceptions=True)

        legs = []
        for i, r in enumerate(leg_results_raw):
            slot = participants[i]
            if isinstance(r, Exception):
                legs.append({
                    "slot": slot, "status": "failed", "text": "",
                    "input_tokens": 0, "output_tokens": 0, "advisor_calls": 0,
                    "cost": 0.0, "elapsed": 0.0, "error": str(r),
                })
            else:
                legs.append(r)
            hb.slot_completed(slot, legs[-1]["elapsed"], legs[-1]["status"])

        # Phase 2: Aggregator synthesis at temp=0.4
        agg_cfg_data = _load_aggregator_config()
        agg_persona = _load_aggregator_persona()

        legs_block = "\n\n".join(
            f"### {r['slot']} ({PARTICIPANTS[r['slot']]['model']})\n"
            f"Status: {r['status']}\n"
            + (r["text"][:3000] if r.get("text") else f"FAILED: {r.get('error','unknown')}")
            for r in legs
        )

        aggregator_user = (
            agg_cfg_data["user_template"]
            .replace("{task}", task)
            .replace("{N}", str(len(legs)))
            .replace("{legs_block}", legs_block)
        )

        aggregator_system = agg_cfg_data["system"].replace("{N}", str(len(legs)))
        if agg_persona:
            aggregator_system = f"{aggregator_system}\n\n---\n\n{agg_persona.strip()}"

        hb.slot_started(f"{aggregator_slot}(agg)")

        # Run aggregator synchronously (single call, sequential by design)
        loop = asyncio.get_event_loop()
        aggregator_result = await loop.run_in_executor(
            None, run_claude_participant, client, aggregator_slot, aggregator_user, aggregator_system
        )
        hb.slot_completed(f"{aggregator_slot}(agg)", aggregator_result["elapsed"], aggregator_result["status"])

    finally:
        hb.stop()

    return {"legs": legs, "aggregator": aggregator_result, "wall_elapsed": time.time() - wall_start}


def write_moa_diff_report(task: str, diff_question: str, legs: list,
                          aggregator: dict, aggregator_slot: str) -> Path:
    """Write MoA diff report — extends the legacy format with aggregator section."""
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    out = DIFF_DIR / f"council-moa-{timestamp}.md"

    lines = [f"# Council MoA Diff Report — {timestamp}", "", "## Task", task, ""]
    if diff_question:
        lines += ["## Diff Question", f"> {diff_question}", ""]

    # Participants table
    lines += ["## Reference Legs", "", "| Slot | Model | Status | Latency | Cost |",
              "|---|---|---|---|---|"]
    for r in legs:
        cfg = PARTICIPANTS[r["slot"]]
        status_icon = "✓" if r["status"] == "ok" else ("~" if r["status"] == "dry-run" else "✗")
        lines.append(
            f"| {r['slot']} | {cfg['model']} | {status_icon} {r['status']} | "
            f"{r['elapsed']:.1f}s | ${r['cost']:.4f} |"
        )
    agg_cfg = PARTICIPANTS.get(aggregator_slot, {})
    status_icon = "✓" if aggregator["status"] == "ok" else ("~" if aggregator["status"] == "dry-run" else "✗")
    lines.append(
        f"| {aggregator_slot} (agg) | {agg_cfg.get('model','?')} | {status_icon} {aggregator['status']} | "
        f"{aggregator['elapsed']:.1f}s | ${aggregator['cost']:.4f} |"
    )
    lines.append("")

    # Aggregator output — the structured disagreement map
    lines += ["## Aggregator Disagreement Map", ""]
    if aggregator["status"] == "ok" and aggregator.get("text"):
        lines.append(aggregator["text"].strip())
    elif aggregator["status"] == "dry-run":
        lines.append("_[dry run — no output]_")
    else:
        lines.append(f"**Aggregator FAILED:** {aggregator.get('error', 'unknown')}")
    lines.append("")

    # Full leg outputs
    lines.append("## Full Reference Leg Outputs")
    for r in legs:
        cfg = PARTICIPANTS[r["slot"]]
        lines += ["", f"### {r['slot']} — {cfg['model']}"]
        if r["status"] == "failed":
            lines.append(f"**FAILED:** {r.get('error', 'unknown')}")
        elif r["status"] == "dry-run":
            lines.append("_[dry run — no output]_")
        else:
            lines += ["```", r["text"].strip() or "(empty)", "```"]

    out.write_text("\n".join(lines))
    return out


def append_moa_run_log(task: str, participants: list, legs: list,
                       aggregator: dict, aggregator_slot: str,
                       diff_path: Path, wall_elapsed: float) -> None:
    """Log MoA run to both council_runs.md and shared daily_usage.md (Lockstep #3)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    total_leg_cost = sum(r["cost"] for r in legs)
    agg_cost = aggregator.get("cost", 0.0)
    total_cost = total_leg_cost + agg_cost
    failures = [r["slot"] for r in legs if r["status"] == "failed"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    block = [
        f"\n## {timestamp} — Council MoA run",
        f"**Task:** {task[:80]}{'...' if len(task) > 80 else ''}",
        f"**Legs:** {', '.join(participants)} ({len(participants)} total)",
        f"**Aggregator:** {aggregator_slot}",
        f"**Cost:** ${total_cost:.4f} (legs ${total_leg_cost:.4f} + agg ${agg_cost:.4f})",
        f"**Wall time:** {wall_elapsed:.1f}s",
        f"**Failures:** {', '.join(failures) if failures else 'none'}",
        f"**Diff report:** [{diff_path.name}](diffs/{diff_path.name})",
        "",
    ]
    with open(RUN_LOG, "a") as f:
        f.write("\n".join(block))

    # Lockstep #3: also log to shared advisor-dispatch daily_usage.md
    try:
        SHARED_LOG.parent.mkdir(parents=True, exist_ok=True)
        usage_row = (
            f"| {timestamp} | council-moa | {len(participants)}-leg+aggregator "
            f"| ${total_cost:.4f} total | {wall_elapsed:.1f}s wall |\n"
        )
        with open(SHARED_LOG, "a") as f:
            f.write(usage_row)
    except Exception:
        pass  # non-fatal — observability must not block


# ── Diff report writer ────────────────────────────────────────────────────────

def write_diff_report(task: str, diff_question: str, results: list) -> Path:
    """Writes a structured diff report file. Returns its path."""
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    out = DIFF_DIR / f"council-{timestamp}.md"

    lines = [f"# Council Diff Report — {timestamp}", "", "## Task", task, ""]
    if diff_question:
        lines += ["## Diff Question", f"> {diff_question}", ""]
    else:
        lines += ["## Diff Question", "> (not specified — see Stage 1 of council-mode skill)", ""]

    # Participants table
    lines += ["## Participants", "", "| Slot | Model | Status | Latency | Cost |",
              "|---|---|---|---|---|"]
    for r in results:
        cfg = PARTICIPANTS[r["slot"]]
        status_icon = "✓" if r["status"] == "ok" else ("~" if r["status"] == "dry-run" else "✗")
        lines.append(
            f"| {r['slot']} | {cfg['model']} | {status_icon} {r['status']} | "
            f"{r['elapsed']:.1f}s | ${r['cost']:.4f} |"
        )
    lines.append("")

    # Headline disagreements — placeholder, filled in by human review or future auto-diff
    lines += ["## Headline Disagreements",
              "_Review outputs below and fill in the top 3–5 material disagreements here._",
              "_See `references/stage3_diff.md` for structure guidance._", ""]

    lines += ["## Failure Modes Surfaced",
              "_Name specific failures observed — confabulation, padding, hedge overload, etc._", ""]

    lines += ["## Convergences",
              "_Where all/most agreed — signals the task doesn't exercise model differences on those axes._", ""]

    lines += ["## Router Takeaway",
              "_One paragraph: what did we learn about when to use which model for this task type?_", ""]

    # Full outputs
    lines.append("## Full Outputs")
    for r in results:
        cfg = PARTICIPANTS[r["slot"]]
        lines += ["", f"### {r['slot']} — {cfg['model']}"]
        if r["status"] == "failed":
            lines.append(f"**FAILED:** {r.get('error', 'unknown')}")
        elif r["status"] == "dry-run":
            lines.append("_[dry run — no output]_")
        else:
            lines += ["```", r["text"].strip() or "(empty)", "```"]

    out.write_text("\n".join(lines))
    return out


# ── Run log ───────────────────────────────────────────────────────────────────

def append_run_log(task: str, participants: list, results: list, diff_path: Path) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    total_cost = sum(r["cost"] for r in results)
    total_advisor = sum(r["advisor_calls"] for r in results)
    duration = max(r["elapsed"] for r in results) if results else 0
    failures = [r["slot"] for r in results if r["status"] == "failed"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    block = [
        f"\n## {timestamp} — Council run",
        f"**Task:** {task[:80]}{'...' if len(task) > 80 else ''}",
        f"**Participants:** {', '.join(participants)}",
        f"**Cost:** ${total_cost:.4f}",
        f"**Advisor calls:** {total_advisor}",
        f"**Duration:** {duration:.1f}s",
        f"**Failures:** {', '.join(failures) if failures else 'none'}",
        f"**Diff report:** [{diff_path.name}](diffs/{diff_path.name})",
        "",
    ]
    with open(RUN_LOG, "a") as f:
        f.write("\n".join(block))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Cerebro Council Mode — adversarial parallel model comparison"
    )
    parser.add_argument("--task", default=None,
                        help="Task to send to all participants (required unless --resume is set)")
    parser.add_argument("--participants", default="lean",
                        help="Comma-separated slots, 'lean' (default, 5 slots), or 'full' (6 slots). "
                             f"Valid slots: {', '.join(sorted(PARTICIPANTS.keys()))}")
    parser.add_argument("--diff-question", default="",
                        help="What you're trying to learn from the diff (recommended)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate wiring without making API calls")
    parser.add_argument("--no-personas", action="store_true",
                        help="Disable persona voice layer (neutral run, no per-slot "
                             "system prompt composition, no voice-bank chirps)")
    parser.add_argument("--mode", choices=["legacy", "moa"], default="legacy",
                        help="legacy: current parallel comparison (default). "
                             "moa: asyncio.gather fan-out + aggregator synthesis pass.")
    parser.add_argument("--aggregator", default=None,
                        help="Aggregator slot for --mode moa (e.g. A-claude). "
                             "Required when --mode=moa.")
    parser.add_argument("--gated", action="store_true",
                        help="Enable santa-method dual-reviewer gate (Stage 4). "
                             "Runs Reviewer-A (Sonnet, correctness) + Reviewer-B (Opus, doctrine) "
                             "on the council output. Returns SHIP / ESCALATE_TIER / HALT_TO_OPERATOR. "
                             "Default off — opt-in. Cost ~$0.06/gate.")
    parser.add_argument("--v2", action="store_true",
                        help="Route to council-mode v2 LangGraph backbone (typed substates, "
                             "JSON checkpoint per run). Replaces legacy parallel dispatch. "
                             "Requires --task. Combines with --gated for santa-method Stage 4.")
    parser.add_argument("--resume", default=None, metavar="RUN_ID",
                        help="Resume a v2 council run from its last JSON checkpoint. "
                             "RUN_ID format: council-YYYY-MM-DD-xxxxxxxx. Requires --v2. "
                             "Task is loaded from the checkpoint; --task is ignored if set.")
    parser.add_argument("--debate", action="store_true",
                        help="Run structured adversarial debate (TradingAgents §1 port). "
                             "2-way Advocate/Skeptic → Chief Advisor synthesis. "
                             "Requires --task. Use --risk-debate to also run 3-way risk stage.")
    parser.add_argument("--risk-debate", action="store_true",
                        help="Also run 3-way Opportunist/Guardian/Pragmatist risk stage "
                             "after the advocacy debate. Only used with --debate.")
    parser.add_argument("--max-debate-rounds", type=int, default=1,
                        help="Advocacy debate rounds (default 1). Each round = "
                             "Advocate + Skeptic. Total turns = 2 × rounds.")
    parser.add_argument("--max-risk-rounds", type=int, default=1,
                        help="Risk debate rounds (default 1). Each round = "
                             "Opportunist + Guardian + Pragmatist. Total turns = 3 × rounds.")
    args = parser.parse_args()

    # --resume requires --v2
    if args.resume and not args.v2:
        print("\n❌ --resume requires --v2 flag\n")
        sys.exit(1)

    # --task is required unless --resume is set
    if not args.task and not args.resume and not getattr(args, 'debate', False):
        print("\n❌ --task is required (or use --resume <run_id> with --v2)\n")
        sys.exit(1)

    # Validate MoA args early
    if args.mode == "moa" and not args.aggregator:
        print("\n❌ --aggregator is required when --mode=moa")
        print(f"Valid aggregator slots: {', '.join(sorted(PARTICIPANTS.keys()))}\n")
        sys.exit(1)
    if args.aggregator and args.aggregator not in PARTICIPANTS:
        print(f"\n❌ Unknown aggregator slot: {args.aggregator}")
        print(f"Valid slots: {', '.join(sorted(PARTICIPANTS.keys()))}\n")
        sys.exit(1)

    # Resolve participants
    if args.participants == "lean":
        participants = LEAN_ROSTER
    elif args.participants == "full":
        participants = FULL_ROSTER
    else:
        participants = [p.strip() for p in args.participants.split(",")]
        invalid = [p for p in participants if p not in PARTICIPANTS]
        if invalid:
            print(f"\n❌ Unknown participants: {invalid}")
            print(f"Valid slots: {', '.join(sorted(PARTICIPANTS.keys()))}")
            print(f"Presets: 'lean' ({len(LEAN_ROSTER)} slots), 'full' ({len(FULL_ROSTER)} slots)\n")
            sys.exit(1)

    # API key check (skip for dry-run)
    client = None
    if not args.dry_run:
        key = (
            os.environ.get("ANTHROPIC_API_KEY_DIRECT", "").strip()
            or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        )
        if not key and any(PARTICIPANTS[p]["provider"] == "claude" for p in participants):
            print("\n❌ ANTHROPIC_API_KEY_DIRECT is not set.")
            print("Add to ~/.zshrc:")
            print('  export ANTHROPIC_API_KEY_DIRECT="$(security find-generic-password -a \\"$USER\\" -s ANTHROPIC_API_KEY -w)"')
            sys.exit(1)
        try:
            import anthropic
            if key:
                _proxy_url = FLEET.get("traffic_routing", {}).get("anthropic_base_url", "https://api.anthropic.com")
                client = anthropic.Anthropic(api_key=key, base_url=os.getenv("ANTHROPIC_BASE_URL", _proxy_url))
        except ImportError:
            print("\n❌ anthropic package not installed.")
            print("Install: pip3 install anthropic --break-system-packages\n")
            sys.exit(1)

    # Probe persona loader so the header can report state accurately.
    # (run_council does its own load too — this is cheap and gives the
    # user a confirmation line before work starts.)
    personas_enabled = not args.no_personas
    persona_state_line = "off (--no-personas)"
    if personas_enabled and PersonaLoader is not None:
        try:
            _probe = PersonaLoader()
            if _probe.enabled:
                attached = [s for s in participants if _probe.persona_name_for(s)]
                persona_state_line = (
                    f"{_probe.version} "
                    f"({len(attached)}/{len(participants)} slots voiced)"
                )
            else:
                persona_state_line = "off (map not loaded)"
        except Exception:
            persona_state_line = "off (loader error)"
    elif PersonaLoader is None:
        persona_state_line = "off (loader module missing)"

    # Print header
    mode_label = f"MoA (aggregator: {args.aggregator})" if args.mode == "moa" else "legacy"
    print(f"\n{'='*60}")
    print("CEREBRO COUNCIL MODE — adversarial parallel comparison")
    print(f"{'='*60}")
    print(f"Task:          {args.task[:70]}{'...' if len(args.task) > 70 else ''}")
    print(f"Participants:  {', '.join(participants)} ({len(participants)} total)")
    print(f"Personas:      {persona_state_line}")
    print(f"Mode:          {mode_label}")
    if args.diff_question:
        print(f"Diff question: {args.diff_question}")
    if args.dry_run:
        print("Execution:     DRY RUN — no API calls will be made")
    print(f"{'='*60}\n")

    # ── v2 backbone path (--v2 or --resume) ──────────────────────────────────
    if args.v2 or args.resume:
        from json_checkpointer import JsonRunStore  # type: ignore
        from council_state import CouncilRunState as _CSR  # type: ignore
        from council_graph import run_council_v2_fallback, _LANGGRAPH_OK  # type: ignore

        store = JsonRunStore()
        resume_state = None

        if args.resume:
            resume_state = store.get(args.resume, _CSR)
            if resume_state is None:
                print(f"\n❌ No checkpoint found for run_id: {args.resume}")
                print(f"   Searched: {store.runs_dir}\n")
                sys.exit(1)
            task = resume_state.task
            gated = resume_state.gated
        else:
            task = args.task
            gated = args.gated

        backend = "LangGraph" if _LANGGRAPH_OK else "Sequential Fallback"
        action = f"RESUME ({args.resume})" if args.resume else "NEW RUN"

        print(f"\n{'='*60}")
        print(f"COUNCIL V2 — {action}  [{backend}]")
        print(f"{'='*60}")
        print(f"Task:   {task[:70]}{'...' if len(task) > 70 else ''}")
        print(f"Gated:  {gated}")
        if args.resume and resume_state:
            print(f"Prior:  {resume_state.stage_summary()}")
        if args.dry_run:
            print("Mode:   DRY RUN — no API calls")
        print(f"{'='*60}\n")

        result = run_council_v2_fallback(
            task=task,
            gated=gated,
            dry_run=args.dry_run,
            client=client,
            store=store,
            resume_from=resume_state,
        )

        print(f"\n{'─'*60}")
        print(f"Outcome:  {result.final_outcome}")
        print(f"Run ID:   {result.run_id}")
        tiers_done = [d.tier for d in result.tier_dispatches if d.completed_at]
        if tiers_done:
            print(f"Tiers:    {', '.join(tiers_done)}")
        if result.review:
            rev = result.review
            if hasattr(rev, 'aggregate'):
                print(f"Review:   {rev.aggregate}")
        if result.error:
            print(f"Error:    {result.error}")
        print(f"{'─'*60}")
        if result.final_outcome == "HALT_TO_OPERATOR":
            print("\n🛑 HALT_TO_OPERATOR — logged to state/council-halts.jsonl")
        elif result.final_outcome == "ESCALATE_TIER":
            print("\n⚠️  ESCALATE_TIER — re-run at a higher tier or review manually")
        elif result.final_outcome == "SHIP":
            print("\n✅ SHIP")
        print()
        return

    # ── Adversarial debate path (--debate) ───────────────────────────────────
    if args.debate:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from debate_nodes import run_advocacy_debate, run_risk_debate  # type: ignore

        task = args.task
        print(f"\n{'='*60}")
        print("COUNCIL MODE — ADVERSARIAL DEBATE")
        print(f"{'='*60}")
        print(f"Task:         {task[:70]}{'...' if len(task) > 70 else ''}")
        print(f"Debate mode:  Advocate/Skeptic ({args.max_debate_rounds} round(s))")
        if args.risk_debate:
            print(f"Risk stage:   Opportunist/Guardian/Pragmatist ({args.max_risk_rounds} round(s))")
        if args.dry_run:
            print("Execution:    DRY RUN — no API calls")
        print(f"{'='*60}\n")

        advocacy_result = run_advocacy_debate(
            task=task,
            max_debate_rounds=args.max_debate_rounds,
            client=client,
            dry_run=args.dry_run,
        )

        print(f"\n{'─'*60}")
        print("ADVOCACY DEBATE COMPLETE")
        print(f"{'─'*60}")
        print(f"Turns:  {advocacy_result['count']}")
        print(f"\nCHIEF ADVISOR SYNTHESIS:\n{advocacy_result['judge_decision']}")

        if args.risk_debate:
            print(f"\n{'─'*60}")
            print("RISK DEBATE STARTING")
            print(f"{'─'*60}\n")

            risk_result = run_risk_debate(
                task=task,
                max_risk_discuss_rounds=args.max_risk_rounds,
                client=client,
                dry_run=args.dry_run,
            )

            print(f"\n{'─'*60}")
            print("RISK DEBATE COMPLETE")
            print(f"{'─'*60}")
            print(f"Turns:  {risk_result['count']}")
            print(f"\nPRINCIPAL ADVISOR RECOMMENDATION:\n{risk_result['judge_decision']}")

        print(f"\n{'─'*60}")
        print("Debate complete. Review synthesis above before acting.")
        print(f"{'─'*60}\n")
        return

    # ── MoA path ──────────────────────────────────────────────────────────────
    if args.mode == "moa":
        moa_out = asyncio.run(run_council_moa_async(
            participants=participants,
            task=args.task,
            dry_run=args.dry_run,
            client=client,
            aggregator_slot=args.aggregator,
            personas_enabled=personas_enabled,
        ))
        legs = moa_out["legs"]
        aggregator_result = moa_out["aggregator"]
        wall_elapsed = moa_out.get("wall_elapsed", 0.0)

        print("\nSUMMARY (MoA)")
        print("─" * 60)
        print(f"{'Slot':<18} {'Status':<10} {'Latency':>8}   {'Cost':>10}")
        for r in legs:
            print(f"{r['slot']:<18} {r['status']:<10} {r['elapsed']:>7.1f}s   ${r['cost']:>8.4f}")
        print(f"{'─'*60}")
        print(f"{'[aggregator]':<18} {aggregator_result['status']:<10} "
              f"{aggregator_result['elapsed']:>7.1f}s   ${aggregator_result['cost']:>8.4f}")
        print("─" * 60)
        total_cost = sum(r["cost"] for r in legs) + aggregator_result.get("cost", 0.0)
        print(f"{'TOTAL':<18} {'':<10} {wall_elapsed:>7.1f}s   ${total_cost:>8.4f}")

        if not args.dry_run:
            diff_path = write_moa_diff_report(
                args.task, args.diff_question, legs, aggregator_result, args.aggregator
            )
            append_moa_run_log(
                args.task, participants, legs, aggregator_result,
                args.aggregator, diff_path, wall_elapsed
            )
            print(f"\n✅ MoA diff report: {diff_path}")
            print(f"✅ Run logged:      {RUN_LOG}")
        else:
            print("\n[DRY RUN] No diff report written.")

        print()
        return

    # ── Legacy path (unchanged) ───────────────────────────────────────────────
    start = time.time()
    results = run_council(participants, args.task, args.dry_run, client,
                          personas_enabled=personas_enabled)
    elapsed = time.time() - start

    # Print summary
    print("\nSUMMARY")
    print("─" * 60)
    print(f"{'Slot':<12} {'Status':<10} {'Latency':>8}   {'Cost':>10}")
    for r in results:
        print(f"{r['slot']:<12} {r['status']:<10} {r['elapsed']:>7.1f}s   "
              f"${r['cost']:>8.4f}")
    print("─" * 60)
    total_cost = sum(r["cost"] for r in results)
    total_advisor = sum(r["advisor_calls"] for r in results)
    print(f"{'TOTAL':<12} {'':<10} {elapsed:>7.1f}s   ${total_cost:>8.4f}")
    if total_advisor:
        print(f"Advisor calls consumed: {total_advisor}")

    # Write diff report + run log (skip if dry-run)
    if not args.dry_run:
        diff_path = write_diff_report(args.task, args.diff_question, results)
        append_run_log(args.task, participants, results, diff_path)
        print(f"\n✅ Diff report:  {diff_path}")
        print(f"✅ Run logged:   {RUN_LOG}")
    else:
        print("\n[DRY RUN] No diff report written.")

    # ── Stage 4: santa-method dual-reviewer gate (--gated flag) ──────────────
    if args.gated:
        try:
            from santa_review import run_review, Outcome
        except ImportError:
            print("\n⚠️  santa_review not available — skipping Stage 4 gate")
        else:
            # Gather the best available output for review
            # Use the first successful result as the "selected" output
            selected_output = ""
            for r in results:
                if r.get("status") == "ok" and r.get("response"):
                    selected_output = r["response"]
                    break
            if not selected_output:
                selected_output = str(results)  # fallback: stringify all results

            print(f"\n{'─'*60}")
            print("STAGE 4: santa-method dual-reviewer gate")
            print(f"{'─'*60}")
            review = run_review(
                task=args.task,
                output=selected_output,
                client=client,
                dry_run=args.dry_run,
            )
            a = review.reviewer_a
            b = review.reviewer_b
            print(f"Reviewer-A (Correctness): {a.verdict if a else 'ERROR'}"
                  f"{' — ' + a.reason[:80] if a else ''}")
            print(f"Reviewer-B (Doctrine):    {b.verdict if b else 'ERROR'}"
                  f"{' — ' + b.reason[:80] if b else ''}")
            print(f"{'─'*60}")
            print(f"Gate outcome: {review.outcome.value}  "
                  f"(cost: ${review.cost_usd:.4f}, elapsed: {review.elapsed_s:.1f}s)")
            if review.outcome == Outcome.HALT_TO_OPERATOR:
                print("\n🛑 HALT_TO_OPERATOR — both reviewers FAIL or high-severity disagreement.")
                print("   Logged to state/council-halts.jsonl. Surface to the operator before shipping.")
            elif review.outcome == Outcome.ESCALATE_TIER:
                print("\n⚠️  ESCALATE_TIER — reviewers disagree. Re-run at a higher tier or review manually.")
            else:
                print("\n✅ SHIP — both reviewers PASS.")

    print()


if __name__ == "__main__":
    # LEGACY fail-close (Cerebro 2026-07-30): council-mode is RETIRED and this entrypoint fans a
    # task across MULTIPLE cloud models — the most billable of the three. Refuse unless the operator
    # explicitly opts in, so a default `python council_run.py` cannot silently bill a key.
    if os.environ.get("LIBRO_LEGACY_OPTIN") != "1":
        sys.stderr.write(
            "REFUSED: council-mode is RETIRED (LEGACY) and this entrypoint makes billable multi-model "
            "API calls. See skills/council-mode/SKILL.md (LEGACY banner). To run anyway, set "
            "LIBRO_LEGACY_OPTIN=1.\n")
        sys.exit(2)
    main()
