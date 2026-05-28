---
name: council-mode
description: >
  Adversarial parallel comparison — runs the SAME task across multiple model tiers
  and/or providers in parallel, then surfaces where each model disagrees, fails, or
  hallucinates. Purpose is NOT consensus: the purpose is exposing failure modes so the
  operator can route around them. Built on top of advisor-mode.
  Trigger on: "assemble the council", "convene the council", "put it to the council",
  "what does the council say", "council mode", "run this on all tiers", "compare model
  outputs", "which model failed on this", "adversarial compare", "diff the models",
  "run the council", "parallel dispatch", "show me the disagreements".
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
      - fleet_primary     # e.g. 192.168.x.x or localhost (optional — cloud-only buyers leave blank)
      - fleet_backup      # optional fallback node
    requires: [advisor-mode]
---

# Council Mode
### Adversarial Parallel Comparison | Failure-Mode Surfacing | Not Consensus

Council mode dispatches the **same task** to multiple model tiers and/or providers in
parallel, then produces a diff report surfacing where each output disagrees. The goal is
not to pick a winner — the goal is to learn where each model breaks down, so future
routing avoids known failure modes.

**Core principle:**
> The orchestration layer's job is to surface where each model FAILS so you can route
> around it — NOT to pick the "best" model. Build as adversarial comparison
> infrastructure, not consensus/coordination.

This is the opposite of traditional LLM council patterns (majority vote, consensus
synthesis). Those patterns wash out signal. Council mode preserves disagreement because
disagreement IS the signal.

---

## BRAIN CHECK — Run Before Every Council Call

Brain root: resolved from `$CEREBRO_ROOT` env var or `~/.cerebro/profile.yaml`.

1. Verify advisor-mode is installed and provider-aware (`--local`, `--compare` available)
2. **Local fleet (optional):** if `fleet_primary` is set, verify Ollama is reachable at
   that host on port 11434. Cloud-only deployments (no local fleet) skip this check —
   all tiers route to cloud providers.
3. Check `{brain_root}/skills/advisor-mode/logs/daily_usage.md` if present — is
   remaining advisor budget enough for the council roster?
4. Load task context from the relevant department Brain if the task references one

---

## WHEN TO USE COUNCIL MODE

| Situation | Why Council |
|-----------|-------------|
| Strategic or irreversible decision | Cross-tier disagreement = hidden risk |
| Adversarial drafting (contracts, pitches) | Want the failure scenario, not the best draft |
| Prompt engineering | Find where each tier breaks |
| Architecture review | Different tiers catch different failure modes |
| Any task where you suspect the answer is wrong | Council exposes the wrong |

**Do NOT use council mode for:** routine summaries, quick lookups, bulk drafting tasks,
anything where parallel cost isn't justified by the decision weight.

---

## COUNCIL ROSTER (default)

The roster is configured in `~/.cerebro/profile.yaml` under `council.roster`. Default
tiers (cloud-only deployment):

| Tier | Provider | Purpose |
|------|----------|---------|
| Frontier | Claude Opus (latest) | Highest reasoning — baseline |
| Mid | Claude Sonnet (latest) | Speed/cost trade-off — compare |
| Fast | Claude Haiku (latest) | Latency floor — find where it breaks |

**With local fleet configured:** add `senior-advisor` (local Ollama model) to the
roster via `council.local_tier: true` in profile.

---

## INVOCATION

```bash
# Default roster (cloud tiers)
python3 {brain_root}/skills/council-mode/Scripts/council_run.py "<task>"

# Include local fleet tier (requires fleet_primary set)
python3 {brain_root}/skills/council-mode/Scripts/council_run.py --local "<task>"

# Custom roster
python3 {brain_root}/skills/council-mode/Scripts/council_run.py \
  --tiers frontier,mid "<task>"
```

---

## OUTPUT FORMAT

Council mode emits a structured diff report:

```
=== COUNCIL REPORT ===
Task: <task text>
Roster: frontier | mid | fast

[FRONTIER — Claude Opus]
<output>

[MID — Claude Sonnet]
<output>

[FAST — Claude Haiku]
<output>

=== DISAGREEMENTS ===
[Tier A vs Tier B] <specific point of disagreement>
...

=== FAILURE SIGNALS ===
[TIER] <failure mode detected: hallucination / refusal / contradiction>

=== ROUTING RECOMMENDATION ===
<which tier to trust for this task class, based on this council run>
```

---

## PROFILE CONFIGURATION

Council mode reads `~/.cerebro/profile.yaml` for:

```yaml
council:
  roster:           [frontier, mid, fast]   # active tiers
  local_tier: false                         # true = include Ollama senior-advisor
  local_host: ""                            # fleet_primary value, if local_tier: true
  budget_cap: 10                            # max USD per council run (advisory)
```

If no profile exists, council defaults to cloud-only 3-tier roster.

---

## SCOPE CONTRACT

| Dimension | Scope |
|-----------|-------|
| Read paths | `{brain_root}/skills/advisor-mode/`, `~/.cerebro/profile.yaml` |
| Write paths | `{brain_root}/skills/council-mode/logs/` (council run logs) |
| MCP / tool surface | None beyond advisor-mode subprocess |
| Network egress | Cloud provider APIs (Anthropic) + optional local Ollama at fleet_primary |
| Surface | Claude Code |
| Credentials | `ANTHROPIC_API_KEY` (env var); `LITELLM_MASTER_KEY` if routing via proxy |
| Escalation trigger | Any tier returns empty / timeout / error → surface before reporting |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[daily_usage]]

<!-- AUTOLINK-END -->
