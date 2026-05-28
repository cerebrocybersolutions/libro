# Stage 1 — Classify
## Advisor Dispatch

**Purpose:** Take an incoming task description and return a tier assignment with reasoning.
This is the gate. Nothing runs until it passes through here.

**Input required:** Task description (1–2 sentences minimum)
**Output:** Tier label (C / B / A / A+) + reasoning + recommended model pair + estimated advisor calls

---

## Classification Decision Matrix

Work through each factor. Assign a score. Total determines the tier.

### Factor 1 — Task Complexity
| Description | Score |
|---|---|
| Single step, single output, no judgment required | 0 |
| 2–3 steps, some structure needed, light judgment | 1 |
| Multi-step, synthesis required, significant judgment | 2 |
| Architecture-level, cross-system, novel problem | 3 |

### Factor 2 — Reversibility
| Description | Score |
|---|---|
| Completely reversible (draft, brainstorm, lookup) | 0 |
| Partially reversible (file written, email drafted) | 1 |
| Difficult to reverse (decision logged, sent externally) | 2 |
| Irreversible or high-consequence (submitted, published, financial) | 3 |

### Factor 3 — Cross-Department Impact
| Description | Score |
|---|---|
| Affects one task/output only | 0 |
| Affects one department | 1 |
| Affects 2+ departments or a skill used across all sessions | 2 |
| Affects company direction or is architectural infrastructure | 3 |

### Factor 4 — Stakes
| Description | Score |
|---|---|
| Low (no financial, legal, or reputational risk) | 0 |
| Medium ($100–$1K at stake or reputational if wrong) | 1 |
| High ($1K–$10K at stake or significant direction risk) | 2 |
| Critical ($10K+ at stake or sets a wrong trajectory for months) | 3 |

---

## Tier Assignment Table

| Total Score | Tier | Model |
|---|---|---|
| 0–2 | C | Haiku 4.5 |
| 3–5 | B | Sonnet 4.6 |
| 6–9 | A | Sonnet 4.6 + Opus 4.7 advisor |
| 10–12 | A+ | Opus 4.7 solo (require the operator approval) |

---

## Output Format

After scoring, produce this classification block:

```
TASK CLASSIFICATION
───────────────────
Task: [one-line summary of what was asked]

Scoring:
  Complexity:     [score]/3 — [reasoning]
  Reversibility:  [score]/3 — [reasoning]
  Cross-dept:     [score]/3 — [reasoning]
  Stakes:         [score]/3 — [reasoning]
  Total:          [X]/12

Assigned Tier:    [C / B / A / A+]
Model:            [Haiku 4.5 / Sonnet 4.6 / Sonnet 4.6 + Opus advisor / Opus 4.7]
Advisor budget:   [N/A or "max_uses = 3" for Tier A]
Reasoning:        [1–2 sentences explaining the tier decision]

Next step:        [Proceed to Stage 2: Configure / Awaiting the operator approval (A+)]
```

---

## Fast-Track Rules (skip scoring for obvious cases)

If any of these match, classify immediately without scoring:

- **Fast-track C:** "Format this", "look up X", "what is Y", "summarize this paragraph", "spell check", "convert this to JSON" → Tier C
- **Fast-track B:** "Write a proposal for", "analyze this data", "draft an email about", "create a plan for X", "outline the steps" → Tier B
- **Fast-track A:** "Decide whether we should", "architect this skill", "what's the strategy for", "this affects multiple departments", "irreversible decision" → Tier A
- **Fast-track A+:** "Full architecture review", "should we pivot the company toward", "review all 6 departments and recommend" → A+ (flag for the operator approval)

---

## Conflict Resolution

If you're unsure between two adjacent tiers, always assign the higher tier.
Cost of over-classification: minor ($0.01–$0.10 extra per task).
Cost of under-classification: wrong output, rework, compounding errors.
The asymmetry favors going up.

---

## Handoff to Stage 2

Pass to `stage2_configure.md`:
- Assigned tier
- Task description (verbatim)
- Any context from Brain Check relevant to this task

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[stage2_configure]]

<!-- AUTOLINK-END -->
