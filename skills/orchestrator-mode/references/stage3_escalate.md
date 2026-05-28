# Stage 3 — Escalation Logic

Escalation is the moment orchestrator-mode earns its existence. A well-designed chain
escalates rarely; every escalation is a signal that (a) a tier's ceiling was real for
this subtask type, or (b) the gate exposed a failure mode that routing should avoid
next time.

---

## Core Rule — Escalate Once, Then Halt

A subtask gets ONE escalation attempt. If the escalated tier also fails the gate,
the chain halts. This is deliberate:

- A double failure usually means the gate is wrong or the decomposition is wrong.
  Cascading up 3–4 tiers masks these bugs. Halting exposes them.
- Halts are cheap to recover from. The state file lets the operator inspect, fix the
  plan, and resume. A broken chain that silently climbs to A+ on every subtask is
  expensive and trains wrong intuitions.

**A+ never auto-escalates.** Irreversible work is the one place a second A+ call would
be defensible on content quality grounds, but it violates the principle: if A+ failed
its gate, the gate is wrong or the subtask isn't ready. Halt and kick to the operator.

---

## What Escalation IS (and Isn't)

| Is | Isn't |
|---|---|
| Dispatching the same prompt at a higher tier | Retrying the same tier |
| One step up (C-local → C-claude, not C-local → A-claude) | Teleporting to A+ |
| Logged as a distinct event with its own cost | Rolled into subtask cost |
| A signal to update routing heuristics | Free retry budget |

Jumping tiers (skipping levels) is occasionally correct — e.g., a fact-extraction
subtask that fails at C-local should escalate to C-claude, not to B. Level-skipping is
the exception and must be declared explicitly in the plan's `escalate_to` field.

---

## Gate-Failure Classification

When a gate fails, the engine tags the failure with a category. These categories drive
routing updates:

| Category | Meaning | Typical fix |
|---|---|---|
| `CONFABULATION` | Output contains invented facts (CAGE/UEI mismatch, fake URL) | Raise tier, narrow prompt |
| `INCOMPLETE` | Output missing required fields per gate | Raise tier OR widen acceptance |
| `FORMAT` | Output right content, wrong shape (prose instead of JSON) | Tighten prompt formatting, same tier |
| `LENGTH` | Output too short or too long | Adjust tier OR gate bounds |
| `EMPTY` | Model returned no text | Retry once same tier, then escalate |
| `TIMEOUT` | Model didn't return in time | Escalate (likely local → paid) |
| `UNKNOWN` | Doesn't match any category | HALT — gate is too vague, fix plan |

Chain-run logs record the category per subtask. Over 20+ runs, these categorize into a
rough routing-heuristic update:

> "For subtask type `extract_facts`, C-local fails CONFABULATION 15% of the time. Raise
> default tier to C-claude." → update plan file version.

---

## Escalation Budget (Per Chain)

Plan files declare a chain-level budget to prevent runaway escalation chains:

```json
{
  "chain_budget": {
    "max_escalations_total": 2,
    "max_cost_usd": 0.25,
    "halt_on_a_plus_failure": true
  }
}
```

| Field | Default | Purpose |
|---|---|---|
| `max_escalations_total` | 2 | Across all subtasks combined |
| `max_cost_usd` | 0.25 | Hard dollar cap; halts mid-chain if exceeded |
| `halt_on_a_plus_failure` | true | Always halt if any A+ subtask gate fails |

If a chain is hitting these caps regularly, it's the wrong decomposition — subtasks are
being under-assigned. Raise the starting tiers, re-plan.

---

## Escalation Decision Matrix

| Current tier | Gate outcome | Default action |
|---|---|---|
| C-local | Pass | Continue |
| C-local | Fail (CONFABULATION or INCOMPLETE) | → C-claude |
| C-local | Fail (TIMEOUT) | → C-claude |
| C-claude | Pass | Continue |
| C-claude | Fail | → B-claude |
| B-claude | Pass | Continue |
| B-claude | Fail (reasoning gap) | → A-claude |
| B-claude | Fail (FORMAT) | Retry B-claude once with tighter format prompt, then halt |
| A-claude | Pass | Continue |
| A-claude | Fail | → A+-claude (reserved; counts toward chain budget) |
| A+-claude | Pass | Continue |
| A+-claude | Fail | HALT — write state file, alert the operator |

---

## What Happens on Halt

1. Engine writes chain state to `logs/chains/[ts]-[plan].state.json` with:
   - All subtask outputs so far (successful and failed)
   - The failing subtask id, tier, gate, and failure category
   - Chain budget consumed
2. Engine writes a halt summary to the chain-run artifact with a clear `HALTED AT:`
   header so it's visible at a glance.
3. Engine surfaces a one-line alert to stdout:
   ```
   ❌ CHAIN HALTED at subtask `score_fit` — B-claude failed gate (INCOMPLETE) twice.
      State: logs/chains/2026-04-16-1830-solicitation_eval.state.json
      Next: review gate, adjust plan, resume with --resume-from score_fit
   ```
4. Nothing downstream runs. No partial decisions get logged as authoritative.

---

## Resume Semantics

Orchestrator supports `--resume-from <subtask_id>` which loads the state file and
re-runs from that subtask onward. Prior outputs are reused unchanged unless the plan
file itself was modified — if the plan signature (subtask ids + descriptions) has
changed, resume refuses and asks for a fresh run.

---

## Feeding Escalation Data Back Into Council Mode

Every escalation is data. When a plan-file subtask escalates >3 times across runs,
that's a prompt to council-mode it: run the same subtask across multiple tiers in
parallel, see the diff, decide whether to (a) raise the default tier permanently or
(b) tighten the prompt to keep the lower tier viable.

This is the feedback loop between the two skills:

```
council-mode  →  informs plan tier defaults
orchestrator  →  surfaces which subtasks escalate frequently
frequently-escalating subtasks  →  kicked to council for re-assessment
```

Neither skill stands alone well. Together they form an adversarial learning loop that
sharpens routing over time without the operator hand-tuning every subtask.
