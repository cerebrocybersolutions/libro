#!/usr/bin/env python3
"""
dispatch_advisor.py — Advisor Dispatch — API Mode Executor

Calls Anthropic Messages API with tiered model routing.
Supports Tier C (Haiku), B (Sonnet), A (Sonnet + Opus advisor), A+ (Opus solo).

Usage (Claude, default):
  python dispatch_advisor.py --tier A --task "Should we pursue SAMPLE-2026-00001?"
  python dispatch_advisor.py --tier B --task "Draft vendor outreach for solicitation X"
  python dispatch_advisor.py --tier C --task "Format this JSON"
  python dispatch_advisor.py --tier A+ --task "Full architecture review" --confirm
  python dispatch_advisor.py --tier A --task "Design skill X" --max-uses 2
  python dispatch_advisor.py --tier A --task "Test run" --dry-run

Usage (Ollama local, added 2026-04-16):
  python dispatch_advisor.py --tier C --task "Summarize these 3 emails" --local
  python dispatch_advisor.py --tier B --task "Draft vendor email" --local
  python dispatch_advisor.py --tier A --task "Plan for X" --local      # degraded — no advisor tool
  python dispatch_advisor.py --tier A+ --task "..." --local             # BLOCKED by design

Usage (side-by-side comparison):
  python dispatch_advisor.py --tier B --task "Draft response" --compare

Requirements:
  pip install anthropic
  export ANTHROPIC_API_KEY=your_key_here
  # For --local / --compare:  brew install ollama && ollama serve
  #                           ollama pull llama3.1:8b && ollama pull phi4:14b
  # Fleet routing (host + model) reads from master-brain/state/fleet-dispatch.json.
  # Override host with: export CEREBRO_OLLAMA_HOST=http://localhost:11434
"""

import argparse
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

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

MODELS = {
    "C":   "claude-haiku-4-5",
    "B":   "claude-sonnet-4-6",
    "A":   "claude-sonnet-4-6",       # executor; advisor is Opus
    "A+":  "claude-opus-4-7",
}

ADVISOR_MODEL = "claude-opus-4-7"

OLLAMA_TIMEOUT = 180.0  # 3 minutes — 14B local inference is slower than Claude API
# OLLAMA_URL and OLLAMA_MODELS are resolved from fleet-dispatch.json — see loader block below.

MAX_TOKENS = {
    "C":   2048,
    "B":   8096,
    "A":   16000,
    "A+":  32000,
}

DEFAULT_MAX_USES = 3
DAILY_ADVISOR_BUDGET = 20

# ── Topology vocabulary (borrowed from ruflo scan, 2026-04-17) ──────────────
# Shared naming across advisor-dispatch, council-mode, orchestrator-mode so the
# agent-graph shape is legible in logs and output without reading the skill code.
# Values: direct | fan-out-1 | parallel-N | chain-N | dialectic-N
# Source: knowledge-vault/raw/swarm-orchestration-patterns-from-the-frontier.md
def get_topology(tier: str, local: bool, compare: bool) -> str:
    """Name the agent-graph shape for this dispatch call."""
    if compare:
        return "parallel-2"                       # Claude + Ollama, same task
    if tier == "A" and not local:
        return "fan-out-1"                        # executor + Opus advisor tool
    return "direct"                               # single model, single call
                                                  # (Tier C/B solo, A+ solo, A --local degraded)

# Auto-detect from script location; override with CEREBRO_BRAIN_ROOT env var if needed.
# Script lives at: <BRAIN_ROOT>/skills/advisor-dispatch/Scripts/dispatch_advisor.py → parents[3] = <BRAIN_ROOT>
BRAIN_ROOT = Path(os.environ.get("CEREBRO_BRAIN_ROOT") or str(Path(__file__).resolve().parents[3]))
LOG_DIR    = BRAIN_ROOT / "skills" / "advisor-dispatch" / "logs"
LOG_FILE   = LOG_DIR / "daily_usage.md"

# --- fleet-dispatch config load (lazy) --------------------------------------
# Loaded on first call to fleet_url / fleet_model — keeps --help and cloud-only
# runs working even when no local fleet config is installed yet.
_FLEET_CACHE = None

def _load_fleet_dispatch():
    global _FLEET_CACHE
    if _FLEET_CACHE is not None:
        return _FLEET_CACHE
    brain_root = Path(os.environ.get("CEREBRO_BRAIN_ROOT")
                      or os.environ.get("CEREBRO_ROOT")
                      or Path(__file__).resolve().parents[3])
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

# --- operator profile load (CAGE/UEI/company_name/brain_root substitution) ---
def _load_profile() -> dict:
    """Load operator profile from ~/.cerebro/profile.yaml (or PROFILE_PATH env).

    Returns dict with at minimum: company_name, cage_code, uei_code, operator_name,
    operator_email, brain_root. Missing keys default to empty string so unrendered
    placeholders stay visible (advisory-only, never blocks).
    """
    path = Path(os.environ.get("CEREBRO_PROFILE_PATH") or (Path.home() / ".cerebro" / "profile.yaml"))
    profile = {
        "company_name": "",
        "cage_code": "",
        "uei_code": "",
        "operator_name": "",
        "operator_email": "",
        "brain_root": str(BRAIN_ROOT),
    }
    if not path.exists():
        return profile
    try:
        # Minimal YAML parser — `key: value` per line, no nesting
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                profile[k] = v
    except Exception:
        pass  # Advisory only — never block on profile parse failure
    return profile

PROFILE = _load_profile()

def _render_prompt(text: str) -> str:
    """Substitute {{key}} placeholders from operator profile into prompt text."""
    out = text
    for k, v in PROFILE.items():
        out = out.replace("{{" + k + "}}", v)
    return out
# --- end operator profile load -----------------------------------------------

def fleet_url(tier_slot: str, prefer_fallback: bool = False) -> str:
    """Return the Ollama HTTP base URL for a tier slot (e.g. 'C-local'). Env override wins."""
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
        raise RuntimeError("fleet-dispatch config not installed; cannot resolve local tier. "
                           "Run install.sh to populate state/fleet-dispatch.json or use cloud-only tiers.")
    route = fleet["routing"].get(tier_slot) or {}
    model = route.get("model")
    if not model:
        raise ValueError(f"fleet-dispatch: no model for tier slot {tier_slot!r}")
    return model

# Ollama tier mapping — driven by fleet-dispatch.json (US-only lock, 2026-04-21).
# Canonical host + model bindings: master-brain/state/fleet-dispatch.json
OLLAMA_URL = fleet_url("C-local")   # resolves to Prime by default; CEREBRO_OLLAMA_HOST overrides
OLLAMA_MODELS = {
    "C":  fleet_model("C-local"),   # llama3.1:8b — Operator tier
    "B":  fleet_model("B-local"),   # phi4:14b    — Team Lead tier (US/Microsoft)
    "A":  fleet_model("B-local"),   # degraded A-local — no advisor tool, uses plan-then-act prompt
    "A+": None,                     # BLOCKED — no local model matches Opus extended thinking
}
# --- end fleet-dispatch config load -----------------------------------------

# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "C": (
        "You are an efficient operator assistant for the operator's organization, a "
        "federal contracting and cyber services company run by {{operator_name}}. "
        "Complete tasks accurately and concisely. No preamble. Answer directly. "
        "State any assumptions and proceed. "
        "Company: {{company_name}} | CAGE: {{cage_code}} | UEI: {{uei_code}}"
    ),
    "B": (
        "You are a skilled operator for the operator's organization, a federal "
        "contracting and cyber services company run by {{operator_name}} "
        "{{operator_email}}. "
        "Think through the task before writing. Show your structure. Flag assumptions. "
        "One self-review pass before final output. "
        "Company: {{company_name}} | CAGE: {{cage_code}} | UEI: {{uei_code}} | "
        "Brain: {{brain_root}}/"
    ),
    "A": (
        "You are the execution layer for the operator's advisor-dispatch system. "
        "An Opus advisor will provide you with a strategic plan. Execute that plan precisely. "
        "Rules: (1) Do not begin until you have the advisor's plan. "
        "(2) Follow plan steps in order. "
        "(3) State ambiguities before proceeding through them. "
        "(4) Self-review against the plan after execution. "
        "Company: {{company_name}} | CAGE: {{cage_code}} | "
        "Brain: {{brain_root}}/"
    ),
    "A+": (
        "You are the primary strategic intelligence for the operator's organization, "
        "a Veteran-owned (SDVOSB) company run by {{operator_name}}. "
        "Extended thinking is active. Take the time you need. "
        "Rules: (1) Produce reasoning trace before recommendation. "
        "(2) State confidence levels (High/Medium/Low). "
        "(3) Surface information gaps. "
        "(4) Provide 2+ alternatives before recommending one. "
        "(5) End with a clear, unambiguous recommendation. "
        "Company: {{company_name}} | CAGE: {{cage_code}} | UEI: {{uei_code}}"
    ),
}

# Ollama-only prompts — Tier A has no native advisor tool locally,
# so we simulate plan-then-act discipline via prompt structure.
OLLAMA_SYSTEM_PROMPTS = {
    "A": (
        "You are a local advisor-executor for the operator's organization, a "
        "federal contracting company run by {{operator_name}}. "
        "No external advisor is available — you must play BOTH roles: first produce a "
        "STRATEGIC PLAN (numbered steps, trade-offs, risks, 2+ alternatives), then a "
        "horizontal rule (---), then EXECUTE the plan. "
        "State confidence (High/Medium/Low) on each recommendation. "
        "This is a degraded local Tier A — for irreversible $10K+ decisions, escalate to Claude Tier A+. "
        "Company: {{company_name}} | CAGE: {{cage_code}} | UEI: {{uei_code}}"
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_api_key() -> str:
    """Verify ANTHROPIC_API_KEY_DIRECT (or ANTHROPIC_API_KEY fallback) is set."""
    key = (
        os.environ.get("ANTHROPIC_API_KEY_DIRECT", "").strip()
        or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    )
    if not key:
        print("\n❌ ANTHROPIC_API_KEY_DIRECT is not set.")
        print("Add to ~/.zshrc:")
        print('  export ANTHROPIC_API_KEY_DIRECT="$(security find-generic-password -a \\"$USER\\" -s ANTHROPIC_API_KEY -w)"')
        sys.exit(1)
    return key


def check_daily_budget() -> int:
    """Read today's advisor call count from the log. Return calls used today."""
    if not LOG_FILE.exists():
        return 0
    today = datetime.now().strftime("%Y-%m-%d")
    calls_today = 0
    with open(LOG_FILE) as f:
        in_today = False
        for line in f:
            if f"## {today}" in line:
                in_today = True
            elif line.startswith("## ") and in_today:
                break
            elif in_today and "| A |" in line or (in_today and "| A+ |" in line):
                # Count rows with advisor calls
                parts = line.split("|")
                if len(parts) >= 6:
                    try:
                        calls = int(parts[5].strip())
                        calls_today += calls
                    except ValueError:
                        pass
    return calls_today


def write_log_entry(tier: str, task_summary: str, model: str,
                    advisor_calls: int, est_cost: float, notes: str = "",
                    topology: str = "direct") -> None:
    """Append one dispatch row to daily_usage.md."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    now   = datetime.now().strftime("%H:%M")

    # Check if today's header exists
    header_exists = False
    if LOG_FILE.exists():
        content = LOG_FILE.read_text()
        header_exists = f"## {today} Usage Log" in content

    with open(LOG_FILE, "a") as f:
        if not header_exists:
            f.write(f"\n## {today} Usage Log\n")
            f.write(f"Daily advisor budget: {DAILY_ADVISOR_BUDGET} calls | "
                    f"Tier A cap per task: {DEFAULT_MAX_USES} calls\n\n")
            f.write("| Time | Task | Tier | Topology | Model | Advisor calls | Est. cost | Notes |\n")
            f.write("|---|---|---|---|---|---|---|---|\n")

        advisor_str = str(advisor_calls) if advisor_calls > 0 else "N/A"
        f.write(f"| {now} | {task_summary[:40]} | {tier} | {topology} | {model} | "
                f"{advisor_str} | ${est_cost:.4f} | {notes} |\n")


def estimate_cost(tier: str, input_tokens: int, output_tokens: int,
                  advisor_calls: int, advisor_tokens: int) -> float:
    """Rough cost estimate based on approximate Anthropic pricing."""
    RATES = {
        "haiku":  (0.80,  4.00),   # per 1M tokens (in, out)
        "sonnet": (3.00,  15.00),
        "opus":   (15.00, 75.00),
    }
    tier_model = {"C": "haiku", "B": "sonnet", "A": "sonnet", "A+": "opus"}[tier]
    in_rate, out_rate = RATES[tier_model]
    cost = (input_tokens / 1_000_000 * in_rate) + (output_tokens / 1_000_000 * out_rate)
    if advisor_calls > 0:
        adv_in, adv_out = RATES["opus"]
        cost += advisor_calls * (500 / 1_000_000 * adv_in + 500 / 1_000_000 * adv_out)
    return cost


# ── Ollama helpers ────────────────────────────────────────────────────────────

def check_ollama_reachable() -> tuple[bool, str]:
    """Ping Ollama's version endpoint. Returns (ok, message)."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(f"{OLLAMA_URL}/api/version")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode())
            return True, data.get("version", "unknown")
    except urllib.error.URLError as e:
        return False, f"Ollama not reachable at {OLLAMA_URL} — is 'ollama serve' running? ({e})"
    except Exception as e:
        return False, f"Ollama health check failed: {e}"


def check_ollama_model(model: str) -> tuple[bool, str]:
    """Confirm the requested Ollama model is pulled. Returns (ok, message)."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode())
            names = [m.get("name", "") for m in data.get("models", [])]
            if model in names:
                return True, f"Model {model} is available"
            return False, (
                f"Model {model} not found locally. Pulled models: {names}. "
                f"Run: ollama pull {model}"
            )
    except Exception as e:
        return False, f"Model availability check failed: {e}"


def dispatch_ollama(tier: str, task: str, dry_run: bool) -> dict:
    """Dispatch to local Ollama. No advisor tool — degraded Tier A uses plan-then-act prompt."""
    model = OLLAMA_MODELS[tier]
    if model is None:
        # Should never reach here — main() blocks Tier A+ local
        raise SystemExit("Tier A+ not supported on Ollama. Use Claude Tier A+ instead.")

    # Pick system prompt: use Ollama-specific for Tier A (plan-then-act), else reuse Claude's
    system_prompt = _render_prompt(OLLAMA_SYSTEM_PROMPTS.get(tier, SYSTEM_PROMPTS[tier]))

    if dry_run:
        print(f"\n[DRY RUN] Would call Ollama model {model} for Tier {tier}")
        print(f"Task: {task[:80]}...")
        return {"tier": tier, "model": f"ollama:{model}", "advisor_calls": 0,
                "input_tokens": 0, "output_tokens": 0, "content": "[dry run]",
                "provider": "ollama"}

    # Pre-flight checks
    ok, msg = check_ollama_reachable()
    if not ok:
        raise SystemExit(f"❌ {msg}")
    ok, msg = check_ollama_model(model)
    if not ok:
        raise SystemExit(f"❌ {msg}")

    # Call Ollama — non-streaming, full response
    import urllib.request
    payload = {
        "model": model,
        "prompt": task,
        "system": system_prompt,
        "stream": False,
        "options": {
            "num_ctx": 8192 if tier == "C" else 16384,
            "num_predict": MAX_TOKENS[tier],
        },
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise SystemExit(f"❌ Ollama generate failed: {e}")

    return {
        "tier": tier,
        "model": f"ollama:{model}",
        "advisor_calls": 0,
        "input_tokens": data.get("prompt_eval_count", 0),
        "output_tokens": data.get("eval_count", 0),
        "content": data.get("response", "[empty response]"),
        "provider": "ollama",
    }


# ── Core dispatch functions ───────────────────────────────────────────────────

def dispatch_tier_c_or_b(client, tier: str, task: str, dry_run: bool) -> dict:
    """Dispatch Tier C or B — no advisor tool."""
    if dry_run:
        print(f"\n[DRY RUN] Would call {MODELS[tier]} with task: {task[:80]}...")
        return {"tier": tier, "model": MODELS[tier], "advisor_calls": 0,
                "input_tokens": 0, "output_tokens": 0, "content": "[dry run]",
                "provider": "claude"}

    response = client.messages.create(
        model=MODELS[tier],
        max_tokens=MAX_TOKENS[tier],
        system=_render_prompt(SYSTEM_PROMPTS[tier]),
        messages=[{"role": "user", "content": task}],
    )
    return {
        "tier": tier,
        "model": MODELS[tier],
        "advisor_calls": 0,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "content": response.content[0].text,
        "provider": "claude",
    }


def dispatch_tier_a(client, task: str, max_uses: int, dry_run: bool) -> dict:
    """Dispatch Tier A — Sonnet executor with Opus advisor."""
    if dry_run:
        print(f"\n[DRY RUN] Would call Sonnet + Opus advisor (max_uses={max_uses})")
        print(f"Task: {task[:80]}...")
        return {"tier": "A", "model": MODELS["A"], "advisor_calls": 0,
                "input_tokens": 0, "output_tokens": 0, "content": "[dry run]",
                "provider": "claude"}

    tools = [
        {
            "type": "advisor_20260301",
            "name": "advisor",
            "model": ADVISOR_MODEL,
            "max_uses": max_uses,
        }
    ]

    response = client.beta.messages.create(
        model=MODELS["A"],
        max_tokens=MAX_TOKENS["A"],
        system=_render_prompt(SYSTEM_PROMPTS["A"]),
        tools=tools,
        messages=[{"role": "user", "content": task}],
        betas=["advisor-tool-2026-03-01"],
    )

    # Count advisor tool uses in the response
    advisor_calls = sum(
        1 for block in response.content
        if hasattr(block, "type") and block.type == "tool_use" and block.name == "advisor"
    )

    # Extract text content
    text_content = " ".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )

    return {
        "tier": "A",
        "model": MODELS["A"],
        "advisor_calls": advisor_calls,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "content": text_content,
        "provider": "claude",
    }


def dispatch_tier_aplus(client, task: str, dry_run: bool) -> dict:
    """Dispatch Tier A+ — Opus solo with extended thinking."""
    if dry_run:
        print(f"\n[DRY RUN] Would call Opus solo (extended thinking enabled)")
        print(f"Task: {task[:80]}...")
        return {"tier": "A+", "model": MODELS["A+"], "advisor_calls": 0,
                "input_tokens": 0, "output_tokens": 0, "content": "[dry run]"}

    # Minimal-change fix 2026-04-17: prior config was
    # {"type": "adaptive", "effort": "high"} which returns
    # 400 "thinking.adaptive.effort: Extra inputs are not
    # permitted". The `effort` key is not valid under adaptive.
    #
    # Do NOT swap to {"type": "enabled", "budget_tokens": N} —
    # SKILL.md and stage2_configure.md both document that
    # `type=enabled` returns 400 on Opus 4.7 and adaptive is
    # required. Minimal fix: drop `effort` only.
    response = client.beta.messages.create(
        model=MODELS["A+"],
        max_tokens=MAX_TOKENS["A+"],
        system=_render_prompt(SYSTEM_PROMPTS["A+"]),
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": task}],
        betas=["interleaved-thinking-2025-05-14"],
    )

    text_content = " ".join(
        block.text for block in response.content
        if hasattr(block, "text") and block.type == "text"
    )

    return {
        "tier": "A+",
        "model": MODELS["A+"],
        "advisor_calls": 0,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "content": text_content,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Advisor Dispatch — tiered model routing for Claude Code"
    )
    parser.add_argument("--tier",     required=True, choices=["C", "B", "A", "A+"],
                        help="Model tier to dispatch to")
    parser.add_argument("--task",     required=True,
                        help="Task description (natural language)")
    parser.add_argument("--max-uses", type=int, default=DEFAULT_MAX_USES,
                        help=f"Max advisor calls for Tier A (default: {DEFAULT_MAX_USES})")
    parser.add_argument("--confirm",  action="store_true",
                        help="Required for Tier A+ dispatch (safety gate)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Show what would be called without making API calls")
    parser.add_argument("--local",    action="store_true",
                        help="Route this call to local Ollama instead of Claude API (free + private)")
    parser.add_argument("--compare",  action="store_true",
                        help="Run task on BOTH Claude and Ollama, print side-by-side outputs")
    args = parser.parse_args()

    # Safety gate: A+ requires explicit --confirm
    if args.tier == "A+" and not args.confirm and not args.dry_run:
        print("\n⚠️  Tier A+ requires explicit confirmation.")
        print("Tier A+ = Opus 4.7 solo with extended thinking. Highest cost tier.")
        print("If you're sure, re-run with: --confirm\n")
        sys.exit(1)

    # Guard: Tier A+ is NOT supported on local Ollama
    if args.tier == "A+" and (args.local or args.compare):
        print("\n🚫 Tier A+ is NOT available on local Ollama.")
        print("No local model matches Opus 4.7's extended thinking on irreversible $10K+ decisions.")
        print("For local strategic work, use: --tier A --local (degraded plan-then-act mode).")
        print("For full Tier A+ quality, run WITHOUT --local.\n")
        sys.exit(1)

    # Budget check applies only to Claude advisor calls — Ollama is free
    skip_budget_check = args.local or args.dry_run

    # Budget check for Tier A (Claude only)
    if args.tier in ("A", "A+") and not skip_budget_check:
        calls_today = check_daily_budget()
        remaining = DAILY_ADVISOR_BUDGET - calls_today
        if remaining <= 0:
            print(f"\n🚫 Daily advisor budget exhausted ({calls_today}/{DAILY_ADVISOR_BUDGET} calls used).")
            print("Tier A/A+ dispatch blocked until tomorrow. Use Tier B for now.\n")
            sys.exit(1)
        if remaining <= 5:
            print(f"\n⚠️  Only {remaining} advisor calls remaining today "
                  f"({calls_today}/{DAILY_ADVISOR_BUDGET} used). Proceeding...\n")

    # API key check — needed for Claude path only (skipped for --local + dry-run)
    needs_claude = not args.local or args.compare
    if needs_claude and not args.dry_run:
        api_key = check_api_key()
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            print("\n❌ anthropic package not installed.")
            print("Install it with: pip install anthropic --break-system-packages\n")
            sys.exit(1)
    else:
        client = None

    # Determine provider label for header
    if args.compare:
        provider_label = "CLAUDE + OLLAMA (compare mode)"
        model_label = f"{MODELS[args.tier]} vs ollama:{OLLAMA_MODELS[args.tier]}"
    elif args.local:
        provider_label = "OLLAMA (local)"
        model_label = f"ollama:{OLLAMA_MODELS[args.tier]}"
    else:
        provider_label = "CLAUDE (API)"
        model_label = MODELS[args.tier] + (
            f" + {ADVISOR_MODEL} advisor (max_uses={args.max_uses})" if args.tier == "A" else ""
        )

    # Topology label — names the agent-graph shape for this call
    topology = get_topology(args.tier, args.local, args.compare)

    # Print dispatch header
    print(f"\n{'='*60}")
    print(f"CEREBRO ADVISOR DISPATCH")
    print(f"{'='*60}")
    print(f"Tier:      {args.tier}")
    print(f"Topology:  {topology}")
    print(f"Provider:  {provider_label}")
    print(f"Model:     {model_label}")
    print(f"Task:      {args.task[:80]}{'...' if len(args.task) > 80 else ''}")
    if args.dry_run:
        print(f"Mode:      DRY RUN — no API/Ollama calls will be made")
    if args.tier == "A" and args.local:
        print(f"Note:      Degraded Tier A — no native advisor tool. Using plan-then-act prompt.")
    print(f"{'='*60}\n")

    start_time = time.time()

    # Dispatch — branches by provider and tier
    def run_claude():
        if args.tier in ("C", "B"):
            return dispatch_tier_c_or_b(client, args.tier, args.task, args.dry_run)
        elif args.tier == "A":
            return dispatch_tier_a(client, args.task, args.max_uses, args.dry_run)
        else:  # A+
            return dispatch_tier_aplus(client, args.task, args.dry_run)

    if args.compare:
        # Run both providers serially (parallel would complicate logging)
        print("→ Running Claude...\n")
        claude_result = run_claude()
        print("→ Running Ollama...\n")
        ollama_result = dispatch_ollama(args.tier, args.task, args.dry_run)
        # Keep "result" as a synthetic combined view for logging
        result = {
            "tier": args.tier,
            "model": f"{claude_result['model']} | {ollama_result['model']}",
            "advisor_calls": claude_result["advisor_calls"],
            "input_tokens": claude_result["input_tokens"] + ollama_result["input_tokens"],
            "output_tokens": claude_result["output_tokens"] + ollama_result["output_tokens"],
            "content": None,  # handled separately in output section
            "provider": "compare",
            "_claude": claude_result,
            "_ollama": ollama_result,
        }
    elif args.local:
        result = dispatch_ollama(args.tier, args.task, args.dry_run)
    else:
        result = run_claude()

    elapsed = time.time() - start_time

    # Cost estimate — Ollama is free, only Claude costs
    if args.compare:
        claude_cost = estimate_cost(
            args.tier,
            result["_claude"]["input_tokens"],
            result["_claude"]["output_tokens"],
            result["_claude"]["advisor_calls"],
            result["_claude"]["advisor_calls"] * 500,
        )
        est_cost = claude_cost  # Ollama side is $0
    elif args.local:
        est_cost = 0.0
    else:
        est_cost = estimate_cost(
            args.tier,
            result["input_tokens"],
            result["output_tokens"],
            result["advisor_calls"],
            result["advisor_calls"] * 500,
        )

    # Print output — compare mode shows side-by-side, others show single
    if args.compare:
        print("\n" + "═" * 60)
        print("CLAUDE OUTPUT")
        print("═" * 60)
        print(result["_claude"]["content"])
        print("\n" + "═" * 60)
        print("OLLAMA OUTPUT")
        print("═" * 60)
        print(result["_ollama"]["content"])
        print("\n" + "─" * 60)
        print(f"COMPARE METADATA")
        print(f"  Tier:              {result['tier']}")
        print(f"  Topology:          {topology}")
        print(f"  Claude model:      {result['_claude']['model']}")
        print(f"  Ollama model:      {result['_ollama']['model']}")
        print(f"  Claude tokens:     {result['_claude']['input_tokens']} in / {result['_claude']['output_tokens']} out")
        print(f"  Ollama tokens:     {result['_ollama']['input_tokens']} in / {result['_ollama']['output_tokens']} out")
        print(f"  Claude cost:       ~${est_cost:.4f}")
        print(f"  Ollama cost:       $0.0000 (local)")
        print(f"  Total time:        {elapsed:.1f}s")
    else:
        print("\nOUTPUT")
        print("─" * 60)
        print(result["content"])
        print("\n" + "─" * 60)
        print(f"METADATA")
        print(f"  Tier:           {result['tier']}")
        print(f"  Topology:       {topology}")
        print(f"  Provider:       {result.get('provider', 'claude')}")
        print(f"  Model:          {result['model']}")
        print(f"  Advisor calls:  {result['advisor_calls'] if result['advisor_calls'] > 0 else 'N/A'}")
        print(f"  Tokens in:      {result['input_tokens']}")
        print(f"  Tokens out:     {result['output_tokens']}")
        print(f"  Est. cost:      ~${est_cost:.4f}" + (" (local = free)" if args.local else ""))
        print(f"  Time elapsed:   {elapsed:.1f}s")

    # Log the dispatch
    if not args.dry_run:
        task_summary = args.task[:40]
        notes_parts = []
        if args.max_uses != DEFAULT_MAX_USES:
            notes_parts.append(f"max_uses={args.max_uses}")
        if args.local:
            notes_parts.append("local")
        if args.compare:
            notes_parts.append("compare-mode")
        notes = "; ".join(notes_parts)
        write_log_entry(
            tier=args.tier,
            task_summary=task_summary,
            model=result["model"],
            advisor_calls=result["advisor_calls"],
            est_cost=est_cost,
            notes=notes,
            topology=topology,
        )
        print(f"\n✅ Logged to {LOG_FILE}")

    print()


if __name__ == "__main__":
    main()
