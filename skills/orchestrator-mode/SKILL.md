---
name: orchestrator-mode
description: >
  Sequential chain routing — decomposes a compound task into subtasks, routes each
  subtask to its optimal tier (via advisor-mode underneath), runs a quality-gate check
  after each step, and escalates to a higher tier on gate failure. Complements
  council-mode (parallel comparison). Orchestrator is the "route around failure" thesis
  applied sequentially: keep each subtask on the cheapest tier that passes, escalate
  only when the gate fails.
  Trigger on: "orchestrator mode", "chain this", "break this into subtasks", "route each
  step", "escalation pipeline", "run this as a chain", "decompose and route", "quality-
  gated routing", "sequential tier routing", "run the orchestrator".
audience: operator
surface: claude-code
metadata:
  cerebro:
    port_source: null
    port_commit: null
    libro_ready: true
    libro_ship: true
    libro_status: libro-ship
    libro_profiles: [libro-ops, libro-full]
    profile_vars:
      - brain_root        # resolved from ~/.cerebro/profile.yaml or $CEREBRO_ROOT
      - fleet_primary     # optional — cloud-only buyers leave blank
      - fleet_backup      # optional fallback node
    requires: [advisor-mode]
---

# Orchestrator Mode
### Sequential Chain Routing | Quality-Gated Escalation | Cost-Minimizing

Orchestrator mode takes a compound task, decomposes it into subtasks, and routes each
subtask to its optimal tier via advisor-mode. Between steps, a quality gate checks
whether the output satisfies the subtask's acceptance criteria. If the gate fails, the
subtask re-dispatches one tier up. If the gate passes, the chain continues.

**Core principle:**
> Route around failure, don't pick the "best" model. Orchestrator keeps every subtask
> on the cheapest tier that passes, and only escalates when a specific gate trips.

This is the complement to council-mode. Council compares models on the same task;
orchestrator runs a chain where each step picks its own tier and earns its escalation.

---

## BRAIN CHECK — Run Before Every Orchestrator Call

Brain root: resolved from `$CEREBRO_ROOT` env var or `~/.cerebro/profile.yaml`.

1. Verify advisor-mode is installed and provider-aware
2. **Local fleet (optional):** if `fleet_primary` is set, verify Ollama is reachable.
   Cloud-only deployments skip this check — all tiers route to cloud.
3. Verify the task decomposes into ≥2 discrete subtasks (otherwise use advisor-mode directly)

---

## WHEN TO USE ORCHESTRATOR MODE

| Situation | Why Orchestrator |
|-----------|-----------------|
| Multi-step pipeline with different subtask types | Each step picks its own optimal tier |
| Research → draft → review chain | Decompose by knowledge intensity |
| Long-form deliverable (proposal, report) | Gate each section before continuing |
| Debugging chain | Repro → isolate → fix → verify, gated |
| Any compound task where cheaper tiers cover ≥50% of steps | Material cost saving |

**Do NOT use orchestrator for:** single-shot tasks, tasks with no clear gate condition,
tasks where all steps need frontier reasoning uniformly.

---

## CHAIN MODEL

```
TASK → DECOMPOSE → [Step 1: cheapest tier] → GATE → PASS → [Step 2: cheapest tier] → GATE ...
                                                      → FAIL → ESCALATE (next tier up) → GATE
```

**Tier ladder (default — cloud-only):**

| Tier | Provider | Gate failure escalates to |
|------|----------|--------------------------|
| Fast | Claude Haiku | Mid |
| Mid | Claude Sonnet | Frontier |
| Frontier | Claude Opus | Human (HALT) |

**With local fleet:** Fast tier = local Ollama model (cheapest); Haiku is mid; Sonnet is
frontier. Configure via `orchestrator.local_tier: true` in `~/.cerebro/profile.yaml`.

---

## INVOCATION

```bash
# Standard chain (cloud tiers)
python3 {brain_root}/skills/orchestrator-mode/Scripts/orchestrator_run.py "<compound task>"

# With local fleet as fast tier
python3 {brain_root}/skills/orchestrator-mode/Scripts/orchestrator_run.py --local "<compound task>"

# Custom gate threshold
python3 {brain_root}/skills/orchestrator-mode/Scripts/orchestrator_run.py \
  --gate-threshold 0.85 "<compound task>"
```

---

## OUTPUT FORMAT

Each step emits:

```
[STEP N] <subtask description>
  Tier: <fast|mid|frontier>
  Gate: PASS | FAIL
  Escalated: yes | no
  Output: <subtask output>
```

Final chain summary:

```
=== ORCHESTRATOR CHAIN SUMMARY ===
Steps: N   |   Escalations: M   |   Cost tiers used: fast=X mid=Y frontier=Z
Deliverable: <final stitched output>
```

---

## PROFILE CONFIGURATION

```yaml
orchestrator:
  local_tier: false             # true = use Ollama as fast tier
  local_host: ""                # fleet_primary value
  gate_threshold: 0.80          # quality gate pass threshold (0–1)
  max_escalations: 3            # HALT after N escalations in single chain
```

---

## SCOPE CONTRACT

| Dimension | Scope |
|-----------|-------|
| Read paths | `{brain_root}/skills/advisor-mode/`, `~/.cerebro/profile.yaml` |
| Write paths | `{brain_root}/skills/orchestrator-mode/logs/` |
| MCP / tool surface | None beyond advisor-mode subprocess |
| Network egress | Cloud provider APIs (Anthropic) + optional local Ollama at fleet_primary |
| Surface | Claude Code |
| Credentials | `ANTHROPIC_API_KEY` (env var); `LITELLM_MASTER_KEY` if routing via proxy |
| Escalation trigger | Max escalations hit → HALT, surface to operator before continuing |
