# Stage 5 — Escalate
## Advisor Dispatch

**Purpose:** Handle cases where the output from the dispatched tier was insufficient.
Escalation is not failure — it's the quality gate working. Two escalations on the same
task type means the classification is wrong and needs to be fixed permanently.

**Input required:** Original task + tier used + output that was insufficient + reason it failed
**Output:** Escalated execution result + classification update (if warranted)

---

## Escalation Decision Matrix

| Current tier | Output problem | Action |
|---|---|---|
| C | Too shallow / missed nuance | Escalate to Tier B. Re-run. |
| C | Structurally wrong / missed steps | Escalate to Tier B. Re-run. |
| B | Missing strategic context | Escalate to Tier A. Re-run with advisor. |
| B | Wrong direction / needs judgment | Escalate to Tier A. Re-run with advisor. |
| A | Advisor didn't resolve the ambiguity | Increase `max_uses` to 4. Re-run same tier. |
| A | Still wrong after advisor | Escalate to Tier A+. Requires the operator approval. |
| A+ | (this is the ceiling — if A+ is wrong, the problem is the prompt, not the model) | Revise prompt. Re-run A+. |

---

## Escalation Sequence

### Step 1 — Diagnose why the output failed

Before escalating, identify the failure mode. This determines whether escalation or
prompt revision is the right fix:

| Failure mode | Fix |
|---|---|
| Output was too short / not detailed enough | Tier escalation |
| Output missed key context from Brain | Better Brain Check, not escalation |
| Output was wrong direction | Tier escalation + prompt revision |
| Output was fine but the operator changed what they wanted | Not an escalation — new task |
| Advisor plan was weak | Revise advisor prompt template. See `advisor_prompt_templates.md` |
| Model hallucinated facts | Not fixable by tier — add verification step |

### Step 2 — Execute the escalated tier

Follow Stage 2 + Stage 3 for the new tier. State the escalation clearly:

```
ESCALATION: [Original tier] → [New tier]
Reason: [1 sentence — why the previous output was insufficient]
Re-running with [new model/config]...

[Output from re-run]
```

### Step 3 — Log the escalation

In `logs/daily_usage.md`, add a note to the original dispatch row:
```
| ... | [original tier] | [model] | [N] | $[X.XX] | ESCALATED → [new tier] — [reason] |
```

Then add a new row for the escalated run.

---

## Permanent Reclassification Rule

**Trigger:** Same task TYPE (not instance) escalated 2 or more times.

When this happens:
1. Identify the task type pattern (e.g., "GovCon Go/No-Go decisions", "skill architecture questions")
2. Add it to the Fast-Track Rules in `stage1_classify.md` at the higher tier
3. Note the reclassification in `logs/weekly_review_[date].md`

**Example:**
If "Should we pursue [solicitation]?" has escalated from B → A twice:
→ Add to stage1_classify.md Fast-Track A: "Should we pursue [GovCon opportunity]"

This is how the classification system gets smarter over time. It's not set-and-forget —
it's a living system.

---

## Escalation Limits

| Rule | Reason |
|---|---|
| Max 2 escalations per task instance | If it's wrong after 2 escalations, the problem is the task definition, not the model |
| A+ requires explicit the operator approval every time | No auto-escalation to Opus solo |
| Never escalate without logging | Unlogged escalations don't improve the system |
| Never escalate due to impatience | Escalation is for insufficient quality, not slow output |

---

## Handoff

After escalation is complete:
- Return to Stage 3 output format with escalation metadata included
- Return to Stage 4 to log the escalated run
- If this was the 2nd escalation for a task type: update `stage1_classify.md` before closing

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[advisor_prompt_templates]]
- [[daily_usage]]
- [[stage1_classify]]

<!-- AUTOLINK-END -->
