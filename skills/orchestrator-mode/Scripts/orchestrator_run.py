#!/usr/bin/env python3
"""
orchestrator_run.py — Orchestrator Mode — Sequential Chain with Quality-Gated Escalation

Decomposes a compound task into subtasks per a plan-file, routes each subtask to its
tier (advisor-dispatch underneath), evaluates a gate after each step, and escalates
to a higher tier on gate failure. Halts on double failure or A+ failure.

Usage:
  python3 orchestrator_run.py --task "Evaluate SPE4A626U2596" --plan-file plans/solicitation_eval.json --dry-run
  python3 orchestrator_run.py --task "..." --plan-file plans/solicitation_eval.json
  python3 orchestrator_run.py --task "..." --inline-plan "fetch|C-local|gate,score|B-claude|gate"
  python3 orchestrator_run.py --resume-from score_fit --state-file logs/chains/2026-04-16-1830.state.json

Requirements:
  pip3 install anthropic requests  (--break-system-packages on macOS)
  export ANTHROPIC_API_KEY=your_key_here
  Ollama at http://localhost:11434 if any subtask tier is local

Plan-file format: see ../references/stage1_decompose.md
Gate types: contains | regex | json_schema | length_range (see ../references/stage2_chain.md)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Circuit breaker — failure-aware tier routing.
# Import is local to this directory; adds no external dependency.
try:
    from circuit_breaker import CircuitBreaker  # type: ignore
except ImportError:
    CircuitBreaker = None  # Graceful degradation if module is absent.

# MemoryWriter context fencing (GAP-021 fix)
# fence()/unfence() wrap recalled memory injected into prompts for attribution traceability.
# No active recall injection in this file yet — import available for when Phase +2 lands.
# Graceful degradation if memory_writer is unavailable.
try:
    _mw_path = str(Path(__file__).resolve().parents[2] / "memory-writer" / "memory_writer.py")
    import importlib.util as _ilu
    _mw_spec = _ilu.spec_from_file_location("memory_writer", _mw_path)
    _mw_mod = _ilu.module_from_spec(_mw_spec)
    _mw_spec.loader.exec_module(_mw_mod)  # type: ignore[union-attr]
    _mw_fence = _mw_mod.fence      # type: ignore[attr-defined]
    _mw_unfence = _mw_mod.unfence  # type: ignore[attr-defined]
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
SKILL_ROOT = BRAIN_ROOT / "skills" / "orchestrator-mode"
LOG_DIR    = SKILL_ROOT / "logs"
CHAIN_DIR  = LOG_DIR / "chains"
RUN_LOG    = LOG_DIR / "chain_runs.md"
SHARED_LOG = BRAIN_ROOT / "skills" / "advisor-mode" / "logs" / "daily_usage.md"
PLAN_DIR   = SKILL_ROOT / "Scripts" / "plans"

# --- fleet-dispatch config load (lazy) --------------------------------------
# Loaded on first call to fleet_url / fleet_model — keeps --help and cloud-only
# runs working even when no local fleet config is installed yet.
_FLEET_CACHE = None

def _load_fleet_dispatch():
    global _FLEET_CACHE
    if _FLEET_CACHE is not None:
        return _FLEET_CACHE
    brain_root = _resolve_brain_root()
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

# Tier registry — US-only lock applied 2026-04-21 per fleet-dispatch.json.
# B-local retargeted from qwen2.5:14b (Chinese origin — excluded) to phi4:14b (US/Microsoft).
# B-alt removed — now redundant with B-local (same model, same host after retargeting).
# SHIPPED (GovCon OS) defaults are US+EU only per fleet-dispatch.json routing.
TIERS = {
    "C-claude":  {"provider": "claude", "model": "claude-haiku-4-5",    "cost_tier": "haiku"},
    "B-claude":  {"provider": "claude", "model": "claude-sonnet-4-6",   "cost_tier": "sonnet"},
    "A-claude":  {"provider": "claude", "model": "claude-sonnet-4-6",   "cost_tier": "sonnet", "advisor": "claude-opus-4-7"},
    "A+-claude": {"provider": "claude", "model": "claude-opus-4-7",     "cost_tier": "opus"},
    "C-local":   {"provider": "ollama", "model": fleet_model("C-local"), "cost_tier": "local"},
    "B-local":   {"provider": "ollama", "model": fleet_model("B-local"), "cost_tier": "local"},
}

DEFAULT_ESCALATION = {
    "C-local":   "C-claude",
    "C-claude":  "B-claude",
    "B-claude":  "A-claude",
    "A-claude":  "A+-claude",
    "A+-claude": None,  # HALT
    "B-local":   "B-claude",
}

COST_RATES = {
    "haiku":  (0.80, 4.00),
    "sonnet": (3.00, 15.00),
    "opus":   (15.00, 75.00),
    "local":  (0.0, 0.0),
}

TIMEOUT_SEC = 180  # local 14B first-token budget — keep headroom for cold-load

SYSTEM_PROMPT = (
    "You are an operator assistant for the operator's organization. "
    "Respond directly and concretely. State assumptions if needed."
)
# NOTE: operator identity (company, CAGE/UEI/registration IDs, sector) should be
# loaded from the operator profile (~/.cerebro/profile.yaml) and prepended to
# this prompt at runtime, not hardcoded here.


# ── Gate evaluation ───────────────────────────────────────────────────────────

def evaluate_gate(gate: dict, output: str) -> tuple:
    """
    Evaluate gate against output. Returns (passed: bool, category: str, detail: str).
    Gate dict: {"type": "contains|regex|json_schema|length_range", ...type-specific...}
    """
    gtype = gate.get("type", "contains")
    try:
        if gtype == "contains":
            terms = gate.get("terms", [])
            missing = [t for t in terms if t not in output]
            if missing:
                return False, "INCOMPLETE", f"missing terms: {missing}"
            return True, "OK", ""

        if gtype == "regex":
            pattern = gate.get("pattern", "")
            if re.search(pattern, output, re.MULTILINE | re.DOTALL):
                return True, "OK", ""
            return False, "FORMAT", f"regex did not match: {pattern}"

        if gtype == "json_schema":
            required = gate.get("required_keys", [])
            # Be forgiving: models often wrap JSON in markdown fences or add prose.
            # Try raw, then fenced, then first balanced {...} block.
            candidates = []
            raw = output.strip()
            candidates.append(raw)
            fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
            if fence:
                candidates.append(fence.group(1).strip())
            blob = re.search(r"\{[\s\S]*\}", raw)
            if blob:
                candidates.append(blob.group(0))
            data = None
            last_err = None
            for cand in candidates:
                if not cand:
                    continue
                try:
                    data = json.loads(cand)
                    break
                except json.JSONDecodeError as e:
                    last_err = e
                    continue
            if data is None:
                return False, "FORMAT", f"invalid JSON: {last_err}" if last_err else "invalid JSON: empty response"
            if not isinstance(data, dict):
                return False, "FORMAT", f"expected JSON object, got {type(data).__name__}"
            missing = [k for k in required if k not in data]
            if missing:
                return False, "INCOMPLETE", f"missing keys: {missing}"
            null_keys = [k for k in required if data.get(k) in (None, "", [])]
            if null_keys:
                return False, "INCOMPLETE", f"null/empty keys: {null_keys}"
            return True, "OK", ""

        if gtype == "length_range":
            lo = gate.get("min", 0)
            hi = gate.get("max", 10**9)
            n = len(output.strip())
            if n < lo:
                return False, "LENGTH", f"{n} < {lo}"
            if n > hi:
                return False, "LENGTH", f"{n} > {hi}"
            return True, "OK", ""

        return False, "UNKNOWN", f"unsupported gate type: {gtype}"
    except Exception as e:
        return False, "UNKNOWN", f"gate eval error: {e}"


# ── Dispatch ──────────────────────────────────────────────────────────────────

def dispatch_claude(client, tier_name: str, prompt: str) -> dict:
    """Dispatch via Claude. Mirrors advisor-dispatch's tier logic."""
    cfg = TIERS[tier_name]
    start = time.time()
    try:
        if tier_name == "A-claude":
            resp = client.beta.messages.create(
                model=cfg["model"],
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=[{"type": "advisor_20260301", "name": "advisor", "model": "claude-opus-4-7", "max_uses": 3}],
                messages=[{"role": "user", "content": prompt}],
                betas=["advisor-tool-2026-03-01"],
            )
            advisor_calls = sum(
                1 for b in resp.content
                if hasattr(b, "type") and b.type == "tool_use" and b.name == "advisor"
            )
            text = " ".join(b.text for b in resp.content if hasattr(b, "text"))
        elif tier_name == "A+-claude":
            resp = client.beta.messages.create(
                model=cfg["model"],
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": prompt}],
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
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            advisor_calls = 0
            text = resp.content[0].text

        elapsed = time.time() - start
        in_rate, out_rate = COST_RATES[cfg["cost_tier"]]
        cost = (resp.usage.input_tokens / 1_000_000 * in_rate +
                resp.usage.output_tokens / 1_000_000 * out_rate)
        if advisor_calls:
            cost += advisor_calls * (500 / 1_000_000 * COST_RATES["opus"][0] +
                                     500 / 1_000_000 * COST_RATES["opus"][1])
        return {
            "status": "ok", "text": text,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "advisor_calls": advisor_calls, "cost": cost, "elapsed": elapsed,
        }
    except Exception as e:
        return {
            "status": "failed", "text": "", "error": str(e),
            "input_tokens": 0, "output_tokens": 0, "advisor_calls": 0,
            "cost": 0.0, "elapsed": time.time() - start,
        }


def dispatch_ollama(tier_name: str, prompt: str) -> dict:
    import requests
    cfg = TIERS[tier_name]
    start = time.time()
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": cfg["model"], "system": SYSTEM_PROMPT,
                  "prompt": prompt, "stream": False},
            timeout=TIMEOUT_SEC,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "status": "ok", "text": data.get("response", ""),
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
            "advisor_calls": 0, "cost": 0.0,
            "elapsed": time.time() - start,
        }
    except Exception as e:
        return {
            "status": "failed", "text": "", "error": str(e),
            "input_tokens": 0, "output_tokens": 0, "advisor_calls": 0,
            "cost": 0.0, "elapsed": time.time() - start,
        }


def dispatch(client, tier_name: str, prompt: str) -> dict:
    if tier_name not in TIERS:
        return {"status": "failed", "text": "", "error": f"unknown tier {tier_name}",
                "input_tokens": 0, "output_tokens": 0, "advisor_calls": 0,
                "cost": 0.0, "elapsed": 0.0}
    cfg = TIERS[tier_name]
    if cfg["provider"] == "claude":
        return dispatch_claude(client, tier_name, prompt)
    return dispatch_ollama(tier_name, prompt)


# ── Prompt construction ───────────────────────────────────────────────────────

def build_prompt(subtask: dict, prior_outputs: dict, top_task: str) -> str:
    lines = [f"Task: {top_task}", "",
             f"Subtask: {subtask['description']}", ""]
    inputs = subtask.get("inputs", [])
    if inputs:
        lines.append("Prior outputs:")
        for ref in inputs:
            if ref.startswith("@task."):
                continue  # handled implicitly via top_task
            text = prior_outputs.get(ref, {}).get("text", "(missing)")
            lines.append(f"  [{ref}]:\n{text.strip()}")
        lines.append("")
    gate_desc = subtask.get("gate", {}).get("description",
                                             str(subtask.get("gate", "no gate")))
    lines.append(f"Acceptance: {gate_desc}")
    lines.append("")
    lines.append("Respond with only the output that satisfies the acceptance criteria.")
    return "\n".join(lines)


# ── Chain engine ──────────────────────────────────────────────────────────────

def run_chain(plan: dict, top_task: str, client, dry_run: bool,
              resume_state: dict = None) -> dict:
    prior_outputs = resume_state.get("prior_outputs", {}) if resume_state else {}
    timeline = resume_state.get("timeline", []) if resume_state else []
    failed_outputs = resume_state.get("failed_outputs", []) if resume_state else []
    resume_from = resume_state.get("resume_from") if resume_state else None
    escalations_total = resume_state.get("escalations_total", 0) if resume_state else 0
    total_cost = resume_state.get("total_cost", 0.0) if resume_state else 0.0

    budget = plan.get("chain_budget", {})
    max_esc = budget.get("max_escalations_total", 2)
    max_cost = budget.get("max_cost_usd", 0.25)

    # Circuit breaker — opt-out via plan["circuit_breaker"]=false or env CEREBRO_CB_DISABLE=1.
    # Default ON.
    cb_enabled = (
        CircuitBreaker is not None
        and plan.get("circuit_breaker", True) is not False
        and os.environ.get("CEREBRO_CB_DISABLE") not in ("1", "true", "True")
    )
    cb = CircuitBreaker() if cb_enabled else None

    subtasks = plan["subtasks"]
    start_idx = 0
    if resume_from:
        for i, st in enumerate(subtasks):
            if st["id"] == resume_from:
                start_idx = i
                break

    for st in subtasks[start_idx:]:
        st_id = st["id"]
        tier = st["tier"]
        gate = st.get("gate", {"type": "length_range", "min": 1})
        escalate_to = st.get("escalate_to", DEFAULT_ESCALATION.get(tier))
        max_subtask_esc = st.get("max_escalations", 1)
        if tier == "A+-claude":
            max_subtask_esc = 0

        prompt = build_prompt(st, prior_outputs, top_task)

        if dry_run:
            print(f"  [DRY] {st_id:<15} → {tier:<10} ({TIERS[tier]['model']})")
            timeline.append({
                "id": st_id, "tier": tier, "gate": "dry", "escalated": False,
                "cost": 0.0, "elapsed": 0.0, "category": "DRY",
            })
            prior_outputs[st_id] = {"text": "[dry-run placeholder]", "status": "dry"}
            continue

        print(f"  ▶ {st_id:<15} tier={tier:<10} ", end="", flush=True)
        initial_tier = tier
        # Circuit-breaker pre-check: divert to escalate_to if breaker for (tier, st_id)
        # is currently OPEN. Records the divert and continues; does not halt the chain.
        # task_class = subtask id (the granularity at which failures recur).
        cb_preempted = False
        if cb is not None and escalate_to and cb.is_open(tier, st_id):
            print(f"⚡ breaker open → divert to {escalate_to}", flush=True)
            print(f"    ↳ {escalate_to:<10} ", end="", flush=True)
            initial_tier = tier  # record the tier we would have used
            tier = escalate_to
            cb_preempted = True

        result = dispatch(client, tier, prompt)
        passed, category, detail = (False, "EMPTY", "no output") if result["status"] == "failed" \
            else evaluate_gate(gate, result["text"])
        total_cost += result["cost"]
        escalated = False

        # Circuit-breaker record: update the breaker for the tier we actually ran on.
        # When NOT preempted, update the original tier's breaker.
        # When preempted, update the diverted tier's breaker (the one we actually ran).
        if cb is not None:
            cb.record(tier, st_id, passed=passed)

        # When we've been preempted to escalate_to, disable further escalation for this
        # subtask — we already used the fallback. Prevents double-escalating to the same
        # tier and keeps cost predictable.
        if cb_preempted:
            max_subtask_esc = 0

        if not passed and max_subtask_esc > 0 and escalate_to:
            if escalations_total >= max_esc:
                # Budget exhausted before we could escalate — still capture the failed output.
                failed_outputs.append({
                    "id": st_id, "tier": initial_tier, "escalated_from": None,
                    "category": category, "detail": detail,
                    "text": result.get("text", ""), "error": result.get("error", ""),
                    "cost": result.get("cost", 0.0), "elapsed": result.get("elapsed", 0.0),
                })
                _halt(plan, top_task, timeline, prior_outputs, failed_outputs,
                      st_id, tier, "BUDGET", "chain escalation budget exhausted")
                return {"status": "halted", "timeline": timeline,
                        "prior_outputs": prior_outputs, "failed_outputs": failed_outputs,
                        "total_cost": total_cost}
            # Capture the initial-tier failure before escalating. This is the output a
            # successful escalation would otherwise hide — gold for tuning gate/prompt
            # contracts (cf. fit_score 2026-04-17 contract mismatch incident).
            failed_outputs.append({
                "id": st_id, "tier": initial_tier, "escalated_from": None,
                "category": category, "detail": detail,
                "text": result.get("text", ""), "error": result.get("error", ""),
                "cost": result.get("cost", 0.0), "elapsed": result.get("elapsed", 0.0),
            })
            print(f"✗ {category} → escalate to {escalate_to}", flush=True)
            print(f"    ↳ {escalate_to:<10} ", end="", flush=True)
            result = dispatch(client, escalate_to, prompt)
            total_cost += result["cost"]
            passed, category, detail = (False, "EMPTY", "no output") \
                if result["status"] == "failed" else evaluate_gate(gate, result["text"])
            escalated = True
            escalations_total += 1
            tier = escalate_to  # record final tier used
            # Record the escalated-tier outcome against its own breaker key.
            if cb is not None:
                cb.record(tier, st_id, passed=passed)

        if not passed:
            # Escalation also failed — capture the escalated-tier failure.
            failed_outputs.append({
                "id": st_id, "tier": tier, "escalated_from": initial_tier if escalated else None,
                "category": category, "detail": detail,
                "text": result.get("text", ""), "error": result.get("error", ""),
                "cost": result.get("cost", 0.0), "elapsed": result.get("elapsed", 0.0),
            })
            print(f"✗ {category} {detail}", flush=True)
            _halt(plan, top_task, timeline, prior_outputs, failed_outputs,
                  st_id, tier, category, detail)
            return {"status": "halted", "timeline": timeline,
                    "prior_outputs": prior_outputs, "failed_outputs": failed_outputs,
                    "total_cost": total_cost}

        print(f"✓ {category}  ${result['cost']:.4f}  {result['elapsed']:.1f}s", flush=True)
        prior_outputs[st_id] = result
        timeline.append({
            "id": st_id, "tier": tier, "gate": "✓", "escalated": escalated,
            "cb_preempted": cb_preempted,
            "cost": result["cost"], "elapsed": result["elapsed"], "category": category,
        })

        if total_cost > max_cost:
            _halt(plan, top_task, timeline, prior_outputs, failed_outputs,
                  st_id, tier, "BUDGET", f"total cost ${total_cost:.4f} > cap ${max_cost}")
            return {"status": "halted", "timeline": timeline,
                    "prior_outputs": prior_outputs, "failed_outputs": failed_outputs,
                    "total_cost": total_cost}

    return {"status": "ok", "timeline": timeline, "prior_outputs": prior_outputs,
            "failed_outputs": failed_outputs,
            "total_cost": total_cost, "escalations_total": escalations_total}


def _halt(plan, top_task, timeline, prior_outputs, failed_outputs,
          subtask_id, tier, category, detail):
    CHAIN_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    state = CHAIN_DIR / f"{ts}-{plan['name']}.state.json"
    state.write_text(json.dumps({
        "plan_name": plan["name"],
        "plan_version": plan.get("version", "1"),
        "top_task": top_task,
        "halted_at": subtask_id,
        "halted_tier": tier,
        "halt_category": category,
        "halt_detail": detail,
        "timeline": timeline,
        "prior_outputs": {k: {"text": v.get("text", "")} for k, v in prior_outputs.items()},
        "failed_outputs": failed_outputs,
    }, indent=2))
    print(f"\n❌ CHAIN HALTED at subtask `{subtask_id}` ({category}: {detail})")
    print(f"   State: {state}")
    print(f"   Resume: --resume-from {subtask_id} --state-file {state.name}")


# ── Artifact writers ──────────────────────────────────────────────────────────

def write_chain_artifact(plan: dict, top_task: str, outcome: dict) -> Path:
    CHAIN_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    out = CHAIN_DIR / f"{ts}-{plan['name']}.chain.md"
    lines = [f"# Chain Run — {ts} — {plan['name']}", "",
             f"**Status:** {outcome['status']}", "",
             "## Task", top_task, "",
             "## Timeline",
             "| # | Subtask | Tier | Gate | Escalated | Cost | Latency |",
             "|---|---|---|---|---|---|---|"]
    for i, row in enumerate(outcome.get("timeline", []), 1):
        lines.append(f"| {i} | {row['id']} | {row['tier']} | "
                     f"{row.get('gate','?')} | {'yes' if row['escalated'] else '—'} | "
                     f"${row['cost']:.4f} | {row['elapsed']:.1f}s |")
    lines += ["",
              f"**Total cost:** ${outcome.get('total_cost', 0):.4f}",
              f"**Escalations:** {sum(1 for r in outcome.get('timeline', []) if r['escalated'])}",
              "",
              "## Full Outputs"]
    for row in outcome.get("timeline", []):
        text = outcome["prior_outputs"].get(row["id"], {}).get("text", "")
        lines += ["", f"### {row['id']} — {row['tier']}",
                  "```", (text.strip() or "(empty)"), "```"]

    # Debug section: failed-gate outputs (initial-tier failures that escalated
    # successfully, and terminal halt failures). Only written when failures occur,
    # so successful chain artifacts remain unchanged.
    fails = outcome.get("failed_outputs", [])
    if fails:
        lines += ["", "## Failed Outputs (Debug)",
                  "",
                  "_Outputs that failed their gate. Useful for tuning gate/prompt "
                  "contracts — when a step escalates and recovers, the original "
                  "failure is still captured here._",
                  ""]
        for i, f in enumerate(fails, 1):
            esc_note = f" (pre-escalation from {f['escalated_from']})" \
                if f.get("escalated_from") else ""
            lines += [
                f"### {i}. {f['id']} — {f['tier']}{esc_note}",
                f"- **Category:** {f.get('category', '?')}",
                f"- **Gate detail:** {f.get('detail', '')}",
                f"- **Cost:** ${f.get('cost', 0):.4f}  "
                f"**Latency:** {f.get('elapsed', 0):.1f}s",
            ]
            if f.get("error"):
                lines += [f"- **Dispatch error:** {f['error']}"]
            text = f.get("text", "")
            lines += ["", "**Output text:**", "```",
                      (text.strip() or "(empty)"), "```", ""]

    out.write_text("\n".join(lines))
    return out


def append_run_log(plan: dict, top_task: str, outcome: dict, artifact: Path) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    block = [
        f"\n## {ts} — Orchestrator run ({plan['name']})",
        f"**Task:** {top_task[:80]}{'...' if len(top_task) > 80 else ''}",
        f"**Status:** {outcome['status']}",
        f"**Subtasks:** {len(outcome.get('timeline', []))}",
        f"**Escalations:** {sum(1 for r in outcome.get('timeline', []) if r['escalated'])}",
        f"**Cost:** ${outcome.get('total_cost', 0):.4f}",
        f"**Artifact:** [{artifact.name}](chains/{artifact.name})",
        "",
    ]
    with open(RUN_LOG, "a") as f:
        f.write("\n".join(block))


# ── Inline-plan parser ────────────────────────────────────────────────────────

def parse_inline_plan(s: str) -> dict:
    """'fetch|C-local|contains:NAICS,score|B-claude|length:200-800' → plan dict."""
    subtasks = []
    for part in s.split(","):
        pieces = part.strip().split("|")
        if len(pieces) < 2:
            continue
        st_id, tier = pieces[0], pieces[1]
        gate = {"type": "length_range", "min": 1}
        if len(pieces) >= 3 and pieces[2]:
            g = pieces[2]
            if g.startswith("contains:"):
                gate = {"type": "contains", "terms": g.split(":", 1)[1].split("+")}
            elif g.startswith("length:"):
                rng = g.split(":", 1)[1].split("-")
                gate = {"type": "length_range", "min": int(rng[0]), "max": int(rng[1])}
            elif g.startswith("regex:"):
                gate = {"type": "regex", "pattern": g.split(":", 1)[1]}
        subtasks.append({
            "id": st_id, "description": f"Inline step {st_id}",
            "inputs": [subtasks[-1]["id"]] if subtasks else [],
            "tier": tier, "gate": gate,
        })
    return {"name": "inline", "version": "1", "subtasks": subtasks}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Cerebro Orchestrator Mode — sequential chain with quality-gated escalation"
    )
    p.add_argument("--task", required=False, help="Top-level task")
    p.add_argument("--plan-file", help="Path to plan JSON (relative to Scripts/plans/ or absolute)")
    p.add_argument("--inline-plan", help='Shorthand: "id1|tier|gate,id2|tier|gate"')
    p.add_argument("--dry-run", action="store_true", help="Validate wiring, no API calls")
    p.add_argument("--resume-from", help="Resume chain from this subtask id")
    p.add_argument("--state-file", help="State file to load for --resume-from")
    args = p.parse_args()

    # Resolve plan
    if args.plan_file:
        plan_path = Path(args.plan_file)
        if not plan_path.is_absolute():
            plan_path = PLAN_DIR / plan_path
        if not plan_path.exists():
            print(f"\n❌ Plan file not found: {plan_path}\n")
            sys.exit(1)
        plan = json.loads(plan_path.read_text())
    elif args.inline_plan:
        plan = parse_inline_plan(args.inline_plan)
    elif args.dry_run and args.task:
        # First-run / wiring-check shortcut: --dry-run with only --task.
        # Synthesize a trivial single-stage plan so the dry-run can validate
        # wiring without forcing the operator to author a plan file just to
        # see the orchestrator emit. Real runs still require --plan-file or
        # --inline-plan to define stage tiers + gates.
        plan = {
            "name": "default-dry-run",
            "version": "1",
            "subtasks": [{
                "id": "stage1",
                "description": args.task,
                "inputs": [],
                "tier": "C-claude",
                "gate": {"type": "length_range", "min": 1},
            }],
        }
        print("\n[dry-run] No --plan-file / --inline-plan provided; synthesizing "
              "single-stage default plan (id=stage1, tier=C-claude).\n")
    else:
        print("\n❌ Provide --plan-file or --inline-plan (or run --dry-run --task <text> "
              "to validate wiring with a synthesized single-stage plan)\n")
        sys.exit(1)

    # Resume state
    resume_state = None
    if args.resume_from:
        if not args.state_file:
            print("\n❌ --resume-from requires --state-file\n")
            sys.exit(1)
        sp = Path(args.state_file)
        if not sp.is_absolute():
            sp = CHAIN_DIR / sp
        data = json.loads(sp.read_text())
        resume_state = {
            "prior_outputs": data.get("prior_outputs", {}),
            "timeline": data.get("timeline", []),
            "failed_outputs": data.get("failed_outputs", []),
            "resume_from": args.resume_from,
            "escalations_total": 0,
            "total_cost": 0.0,
        }

    top_task = args.task or resume_state.get("top_task") if resume_state else args.task
    if not top_task:
        print("\n❌ --task is required (or implied by state file)\n")
        sys.exit(1)

    # Client
    client = None
    if not args.dry_run:
        needs_claude = any(TIERS.get(s.get("tier"), {}).get("provider") == "claude"
                           for s in plan["subtasks"])
        if needs_claude:
            key = (
                os.environ.get("ANTHROPIC_API_KEY_DIRECT", "").strip()
                or os.environ.get("ANTHROPIC_API_KEY", "").strip()
            )
            if not key:
                print("\n❌ ANTHROPIC_API_KEY_DIRECT is not set.\n")
                sys.exit(1)
            try:
                import anthropic
                _proxy_url = FLEET.get("traffic_routing", {}).get("anthropic_base_url", "https://api.anthropic.com")
                client = anthropic.Anthropic(api_key=key, base_url=os.getenv("ANTHROPIC_BASE_URL", _proxy_url))
            except ImportError:
                print("\n❌ anthropic not installed. pip3 install anthropic --break-system-packages\n")
                sys.exit(1)

    # Header
    print(f"\n{'='*60}")
    print("CEREBRO ORCHESTRATOR MODE — sequential chain routing")
    print(f"{'='*60}")
    print(f"Task:  {top_task[:70]}{'...' if len(top_task) > 70 else ''}")
    print(f"Plan:  {plan['name']} (v{plan.get('version', '1')}, {len(plan['subtasks'])} subtasks)")
    if args.dry_run:
        print("Mode:  DRY RUN — no API calls")
    if args.resume_from:
        print(f"Mode:  RESUME from '{args.resume_from}'")
    print(f"{'='*60}\n")

    # Run
    start = time.time()
    outcome = run_chain(plan, top_task, client, args.dry_run, resume_state)
    elapsed = time.time() - start

    # Summary
    print("\nSUMMARY")
    print("─" * 60)
    print(f"Status:         {outcome['status']}")
    print(f"Subtasks ran:   {len(outcome.get('timeline', []))}")
    print(f"Escalations:    {sum(1 for r in outcome.get('timeline', []) if r['escalated'])}")
    print(f"Total cost:     ${outcome.get('total_cost', 0):.4f}")
    print(f"Wall time:      {elapsed:.1f}s")

    # Artifact
    if not args.dry_run:
        artifact = write_chain_artifact(plan, top_task, outcome)
        append_run_log(plan, top_task, outcome, artifact)
        print(f"\n✅ Chain artifact: {artifact}")
        print(f"✅ Run logged:     {RUN_LOG}")
    else:
        print("\n[DRY RUN] No artifact written.")
    print()


if __name__ == "__main__":
    # LEGACY fail-close (Cerebro 2026-07-30): orchestrator-mode is RETIRED and this entrypoint makes
    # billable Anthropic API calls. Refuse unless the operator explicitly opts in, so a default
    # `python orchestrator_run.py` cannot silently bill a key. Refuse in code, not just in the doc.
    if os.environ.get("LIBRO_LEGACY_OPTIN") != "1":
        sys.stderr.write(
            "REFUSED: orchestrator-mode is RETIRED (LEGACY) and this entrypoint makes billable "
            "Anthropic API calls. See skills/orchestrator-mode/SKILL.md (LEGACY banner). To run "
            "anyway, set LIBRO_LEGACY_OPTIN=1.\n")
        sys.exit(2)
    main()
