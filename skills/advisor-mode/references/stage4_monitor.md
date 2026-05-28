# Stage 4 — Monitor
## Advisor Dispatch

**Purpose:** Track every dispatch, maintain the budget log, flag threshold breaches,
and write the session record to the Brain. The harness is not optional — if you don't
watch it, you can't improve it.

**Input required:** Execution metadata from Stage 3
**Output:** Updated budget log + Brain session entry + status report

---

## Budget Log — Daily Usage

**File path:** `master-brain/skills/advisor-mode/logs/daily_usage.md`

Create this file on first use. Append one row per dispatch. Never overwrite — append only.

```markdown
## [YYYY-MM-DD] Usage Log

| Time | Task (summary) | Tier | Model | Advisor calls | Est. cost | Notes |
|---|---|---|---|---|---|---|
| HH:MM | [task summary, max 10 words] | [C/B/A/A+] | [model] | [N or N/A] | $[X.XX] | [override? escalation?] |
```

**Daily advisor budget default:** 20 advisor calls per day across all tasks.
(Adjustable — the operator sets this threshold in the log header when he wants to change it.)

**Log header format (first entry of each day):**
```markdown
## [YYYY-MM-DD] Usage Log
Daily advisor budget: 20 calls | Tier A cap per task: 3 calls
```

---

## Budget Threshold Alerts

| Condition | Action |
|---|---|
| Advisor calls today: 15/20 (75%) | Note in log: "⚠️ 75% of daily advisor budget used" |
| Advisor calls today: 18/20 (90%) | Surface to the operator in next response: "Heads up — 90% of today's advisor budget consumed" |
| Advisor calls today: 20/20 (100%) | Stop all Tier A dispatches. Inform the operator. Tier B only until reset. |
| Single task used max_uses budget fully (3/3) | Log as "max_uses hit" — flag if task type recurring |
| Same task type escalated 2+ times today | Log as "pattern: [task type] may need reclassification" |

---

## Cost Estimation Reference

These are approximations based on Anthropic's pricing (verify current rates):

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|---|---|---|
| Haiku 4.5 | ~$0.80 | ~$4.00 |
| Sonnet 4.6 | ~$3.00 | ~$15.00 |
| Opus 4.7 | ~$15.00 | ~$75.00 |

**Advisor call cost estimate formula:**
```
Advisor cost per call ≈ (advisor_output_tokens / 1,000,000) × Opus_output_rate
Typical: 500 tokens × ($75/1M) ≈ $0.04 per advisor call
3 advisor calls ≈ $0.12 in Opus advisor cost
```

---

## Brain Session Logging

At the end of each session (or when `/sessionend` is triggered), write a dispatch
summary to the ops Brain:

**File:** `master-brain/sessions/[YYYY-MM-DD]-ops.md` (append to existing file)

```markdown
### Advisor Dispatch Log — [YYYY-MM-DD]

| Task | Tier | Model | Advisor calls | Est. cost |
|---|---|---|---|---|
| [task 1] | [C/B/A] | [model] | [N] | $[X.XX] |
| [task 2] | [C/B/A] | [model] | [N] | $[X.XX] |

Session total:
  Tier C dispatches: [N]
  Tier B dispatches: [N]
  Tier A dispatches: [N] | [total advisor calls]
  Tier A+ dispatches: [N]
  Estimated session cost: $[X.XX]

Patterns flagged:
  [Any escalations, max_uses hits, or task type reclassification notes]
```

---

## Pattern Recognition (run weekly)

Every 7 days, review the `daily_usage.md` log for:

1. **Systematic misclassification:** Any task type that escalated more than twice → reclassify upward in `tier_decision_guide.md`
2. **Advisor waste:** Any Tier A task where advisor was called but output was no better than Tier B → note in log, consider reclassifying down
3. **Budget patterns:** Which days hit 75%+? What task types drove that?
4. **Cost trend:** Is weekly advisor cost growing? Flat? Is it justified by output quality?

Document findings in:
```
master-brain/skills/advisor-mode/logs/weekly_review_[YYYY-MM-DD].md
```

---

## Handoff

If an escalation is needed (output was insufficient), hand off to `stage5_escalate.md`.
Otherwise, session is complete. Log is written. Done.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[-ops]]
- [[daily_usage]]
- [[stage5_escalate]]
- [[tier_decision_guide]]

<!-- AUTOLINK-END -->
