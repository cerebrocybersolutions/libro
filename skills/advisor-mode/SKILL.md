---
name: advisor-mode
description: >
  [LEGACY 2026-07-26 — retired upstream, shipped for reference only. Do NOT invoke against a live API key: the cloud path bills a real request against a beta unexercised since April 2026, on superseded model pins. The durable tier heuristic is preserved in the banner below.]
  Tiered model routing — classifies incoming tasks by complexity
  and dispatches to the correct model tier: Tier C (Haiku, simple/high-volume), Tier B
  (Sonnet, mid-complexity), Tier A (Sonnet + Opus advisor, strategic/complex), Tier A+
  (Opus solo, highest stakes). Uses Anthropic's native advisor_20260301 API tool for
  Tier A dispatch. Enforces plan-before-act discipline: Opus advises on the PLAN, executor
  carries out the plan. Budget control via max_uses parameter.
  Trigger on: "what tier is this", "classify this task", "dispatch this", "which model
  should handle", "advisor mode", "route this task", "run this as tier A", "check my
  advisor budget", "run with opus advisor", "advisor dispatch", "tier routing".
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: ["brain-setup"]
    profile_vars: ["operator_name", "company_name", "brain_root", "fleet_primary", "fleet_backup"]
---
> ## ⚠️ LEGACY — 2026-07-26 · NOT RECOMMENDED FOR NEW WORK
>
> **This skill is retired upstream and is shipped for reference and reversibility, not for use.**
>
> **Do not invoke it against a live API key.** Its cloud path issues a real, billable
> `client.beta.messages.create` request using the `advisor_20260301` tool with
> `betas=["advisor-tool-2026-03-01"]`, and hardcodes `"model": "claude-opus-4-7"`. That beta has
> not been exercised since April 2026, so whether it still exists server-side is **unknown**, and
> the model pins throughout this skill (`claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`)
> are superseded. An invocation may bill your account for a request that cannot succeed.
>
> **Why it is here at all.** The tier *heuristic* below is the durable part and is model-agnostic:
>
> 1. Can a smart intern do this in one step? → **C**
> 2. Does it need synthesis, structure, or multiple steps? → **B**
> 3. Does it involve strategy, irreversibility, or cross-cutting impact? → **A**
> 4. Would getting it wrong cost $10K+ or set a wrong direction for months? → **A+**
>
> Plus two disciplines worth keeping regardless of which models you run: **plan before act** — the
> stronger model advises on the *plan*, the executor carries it out — and treat an advisor budget
> as a **hard ceiling**, not a suggestion.
>
> **What replaced it upstream.** Modern agent harnesses route internally, so an explicit
> classify-then-dispatch layer has no caller left. The advisor role became a dedicated reviewer
> subagent; gate-and-escalate became a standing review norm. If you want the capability, wire the
> heuristic into whatever harness you already run rather than reviving this dispatcher.
>
> Retired 2026-07-26. Scripts are preserved unmodified so nothing you may have built on them breaks.


# Advisor Mode
### Tiered Model Routing | Plan-First | Budget-Controlled

> **V1 scope:** This skill is a **wrapper / classification-and-dispatch harness**, not a native model runtime. It selects the tier (A+/A/B/C) and the venue (cloud Anthropic API vs local Ollama) and hands off; it does not own inference. Treat advisor-mode as the **HR layer** in the executive-stack org chart below — it routes, it doesn't think for you.

This skill routes tasks to the correct model tier and enforces a plan-before-act discipline.
Simple tasks stay cheap. Strategic tasks get Opus-level reasoning where it counts.

**Core principle:** Opus advises on the PLAN. The executor carries out the plan.
Never use Opus to execute when it could plan instead.

---

## EXECUTIVE STACK — Where advisor-mode fits

advisor-mode is one of **three** orchestration skills, each owning a different layer.
They are NOT alternatives — they cover different axes and are usually composed, not swapped:

| Org-chart role | Skill | Axis |
|---|---|---|
| HR / routing (pick the rank for the task) | **advisor-mode** (this skill) | Classification + tier selection |
| Parallel specialist advisors (surface disagreement) | **council-mode** | Parallel adversarial comparison |
| Executor + final arbiter (run the chain, gate, escalate) | **orchestrator-mode** | Sequential gate-and-escalate |

Claude tier mapping (canonical): A+ = CEO / Chief Strategist (Opus solo) · A = Director with
Advisor (Sonnet + Opus advisor tool) · B = Director / Manager (Sonnet solo) · C = Analyst /
Junior Operator (Haiku).

**Local layer (US-only model policy):**
Fleet host + model bindings are canonical at `{brain_root}/mission-control/state/fleet-dispatch.json`.
Override host with `OLLAMA_HOST` env var.
- **C-local:** `llama3.1:8b` (Meta/US) — Operator tier, fast daily driver
- **B-local:** `phi4:14b` (Microsoft/US) — Team Lead tier
- **Memory rule:** one heavy model hot at a time per node. Set `OLLAMA_KEEP_ALIVE=1m`.

**When in doubt:** start here (classify), then hand off to council (compare) or orchestrator
(execute) if the task shape calls for it.

---

## TOPOLOGY VOCABULARY — Shared across the stack

Every dispatch call names the **agent-graph shape** it ran in, using a fixed vocabulary
shared across advisor-mode, council-mode, and orchestrator-mode.

| Value | Meaning | When it shows here |
|---|---|---|
| `direct` | Single model, single call | Tier C solo, Tier B solo, Tier A+ solo, Tier A with `--local` |
| `fan-out-1` | Executor + one advisor (1-deep fan-out) | Tier A standard: Sonnet executor + Opus advisor tool |
| `parallel-2` | Two models answering the same prompt in parallel | `--compare` flag |
| `parallel-N` | N-way parallel on same prompt | council-mode (reserved) |
| `chain-N` | Sequential N-step pipeline with gates | orchestrator-mode (reserved) |

**Where it surfaces in output:**
- Run header (`Topology: fan-out-1`)
- Metadata block at end of run
- Log table column (`daily_usage.md`)

**Design principle:** this system is **1-deep fan-out only** for v1. If the topology vocab ever shows `fan-out-N` where N > 1, that's a signal something unintended ran. Tier is **who ran it**; topology is **what shape it ran in**. They're orthogonal.

---

## BRAIN CHECK — Run Before Every Task

Brain root: auto-detected from script location; override with `BRAIN_ROOT` env var.

1. Load last 2 ops session files → `{brain_root}/mission-control/sessions/*-ops.md`
2. Load advisor budget log → `{brain_root}/mission-control/skills/advisor-mode/logs/daily_usage.md` (if exists)
3. Check for any cross-dept flags in `{brain_root}/mission-control/awareness.md`

After loading:
- State current advisor budget status (calls used today vs. cap, if logged)
- Flag any context relevant to the current task
- Then proceed to classification

---

## COMPANY PROFILE (never prompt the operator for this)

```
Company:  {{company_name}}
Operator: {{operator_name}}  |  Email: {{operator_email}}
Brain:    {brain_root}/mission-control/
Skills:   {brain_root}/mission-control/skills/advisor-mode/
API key:  ANTHROPIC_API_KEY (must be set in environment)
```
*Loaded from `~/.cerebro/profile.yaml` at runtime (populated by first-run wizard).*

---

## TIER CLASSIFICATION GUIDE

| Tier | Model | When to use | Cost profile |
|---|---|---|---|
| C | Haiku 4.5 | Single-step, lookup, format, yes/no, <5 min work | Lowest |
| B | Sonnet 4.6 | Multi-step, analysis, structured output, proposals | Medium |
| A | Sonnet 4.6 + Opus advisor | Strategic, cross-dept impact, irreversible, complex reasoning | Controlled |
| A+ | Opus solo | Highest stakes, architecture decisions, significant business impact | Highest |

**Quick classification test:**
1. Can a smart intern do this in one step? → Tier C
2. Does it need synthesis, structure, or multiple steps? → Tier B
3. Does it involve strategy, irreversibility, or cross-dept impact? → Tier A
4. Would getting it wrong cost significantly or set wrong direction for months? → Tier A+

See `references/tier_decision_guide.md` for full matrix with examples.

---

## STAGE ROUTING

| What operator needs | Stage | Reference |
|---|---|---|
| "Classify this task" | Stage 1: Classify | `references/stage1_classify.md` |
| "Configure the model for tier X" | Stage 2: Configure | `references/stage2_configure.md` |
| "Run this task" (new task, all tiers) | Stages 1 → 2 → 3 | Read in sequence |
| "Run this as Tier A" (tier already known) | Stages 2 → 3 | `stage2_configure.md` + `stage3_execute.md` |
| "Check my advisor budget" | Stage 4: Monitor | `references/stage4_monitor.md` |
| "Result wasn't good enough / escalate" | Stage 5: Escalate | `references/stage5_escalate.md` |

---

## WORKSPACE PATHS

```
Skill root:   {brain_root}/mission-control/skills/advisor-mode/
References:   {brain_root}/mission-control/skills/advisor-mode/references/
Scripts:      {brain_root}/mission-control/skills/advisor-mode/Scripts/
Budget logs:  {brain_root}/mission-control/skills/advisor-mode/logs/daily_usage.md
Ops Brain:    {brain_root}/mission-control/sessions/
Awareness:    {brain_root}/mission-control/awareness.md
```

---

## API CONFIGURATION

```
Advisor tool name:  advisor_20260301
Beta header:        advisor-tool-2026-03-01
Valid executor+advisor pairs:
  - claude-haiku-4-5    + claude-opus-4-7   (Tier A from Haiku base)
  - claude-sonnet-4-6   + claude-opus-4-7   (Tier A standard — preferred)
  - claude-opus-4-7     + claude-opus-4-7   (Tier A+ — Opus advising itself)
Default max_uses:   3  (never set to 1 — give the advisor room to think)
Advisor token output: ~400–700 tokens per call
Extended thinking:  adaptive for Tier A+ (required on Opus 4.7; `type=enabled` 400s)
```

---

## KEY RULES

1. **Classify before you dispatch. Always.** Never skip to execution without a tier assignment.

2. **Opus plans. Sonnet executes.** The advisor prompt asks Opus for a PLAN and DECISION CRITERIA — not to write the final output. Give Opus the goal. Give Sonnet the plan.

3. **The harness matters as much as the model.** Log every dispatch: tier used, advisor calls consumed, task type.

4. **max_uses defaults to 3. Never set it to 1.** A single advisor call often isn't enough for Opus to ask clarifying questions and converge on a good plan. Reduce to 2 for time-sensitive tasks. Never 1.

5. **Escalation is not failure.** If Tier C output was insufficient, escalate to Tier B. Log it. Two escalations on the same task type = that task type should be re-classified upward permanently.

6. **Never run Tier A+ without explicit operator approval.** Opus solo is expensive and reserved for architecture-level decisions.

7. **Plan mode for Tier A is not optional.** Before Sonnet executes a Tier A task, Opus must produce a written plan.

8. **Never hardcode the API key.** The key lives in the `ANTHROPIC_API_KEY` environment variable.

---

## Scope Contract

| Dimension | Scope |
|-----------|-------|
| Read paths | Task context from caller (inline prompt), `{brain_root}/mission-control/skills/advisor-mode/` source files |
| Write paths | **None.** Read-only classifier + dispatcher. |
| MCP / tool surface | Anthropic API (Haiku / Sonnet / Opus), `advisor_20260301` native tool for Tier A |
| Network egress | `api.anthropic.com` only |
| Surface | Claude Code |
| Credentials | `ANTHROPIC_API_KEY` (env var) |
| Escalation trigger | If `max_uses` budget cap exceeded → exit with "budget exhausted" message *before* dispatching executor |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[-ops]]
- [[awareness]]
- [[daily_usage]]
- [[stage1_classify]]
- [[stage2_configure]]
- [[stage3_execute]]
- [[stage4_monitor]]
- [[stage5_escalate]]
- [[tier_decision_guide]]

<!-- AUTOLINK-END -->
