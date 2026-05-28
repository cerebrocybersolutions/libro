# Tier Decision Guide — Full Reference
## Advisor Dispatch

This is the complete classification reference with example task patterns.
Use stage1_classify.md for the scoring matrix. Use this file when you need
examples, edge cases, or fast-track confirmation.

---

## Tier C — Haiku 4.5
**Profile:** Simple, single-step, no judgment, fully reversible
**Cost:** Lowest. Use liberally.
**Default max_tokens:** 2048

### Example tasks (Tier C):
- "Format this vendor email as a table"
- "What's the CAGE code for [company]?"
- "Convert this NAICS code list to bullet points"
- "Spell-check this COR submission email"
- "Is this a SDVOSB set-aside or full-and-open?" (lookup only)
- "List the FSC codes for category 61"
- "Summarize this one paragraph"
- "Rename these 5 files to match the naming convention"
- "What day of the week is April 22, 2026?"
- "Translate this RFQ due date into a countdown"

### Never Tier C:
- Anything requiring judgment between options
- Anything that will be sent externally
- Anything where wrong = rework >15 minutes

---

## Tier B — Sonnet 4.6
**Profile:** Multi-step, requires structure or synthesis, moderate judgment
**Cost:** Medium. Default for most work.
**Default max_tokens:** 8096

### Example tasks (Tier B):
- "Write a vendor outreach email for [solicitation]"
- "Analyze these 5 GovCon opportunities and rank them"
- "Draft a proposal outline for CMMC consulting service"
- "Create the session summary for today's content session"
- "Write the EP01 script outline based on the brief pipeline demo"
- "Build the LinkedIn post announcing The GovCon Vet channel"
- "Summarize all pending decisions across GovCon and Content"
- "Generate the Attachment A form for SAMPLE-2026-00001"
- "Write the first draft of the Fractional CISO service page"
- "Create a 5-step onboarding checklist for a new CMMC client"

### Tier B edge cases (could be A — score it):
- "Write the proposal for [specific client]" — if the client is high-value and the proposal is irreversible once sent → A
- "Draft the sessionend summary" — if the session had major strategic decisions → A

---

## Tier A — Sonnet 4.6 + Opus 4.7 Advisor
**Profile:** Strategic, cross-dept, significant judgment, partially/fully irreversible
**Cost:** Controlled — executor stays cheap, Opus only advises
**Default max_tokens:** 16000 | Default max_uses: 3

### Example tasks (Tier A):
- "Should we pursue SAMPLE-2026-00001 (Base Telephone Parts)?"
- "Design the architecture for the advisor-mode skill"
- "Should we lead with CMMC or Fractional CISO for Cyber Services?"
- "Plan the cross-dept-sync skill — what stages does it need?"
- "What's the right path for BlackBox — A, B, or C?"
- "Design the Telegram v0 architecture for the mobile Brain channel"
- "Review the full govcon-workflow skill and identify the flaw that blocked recording"
- "Should we build HeyGen AI clone or record EP01 live first?"
- "Evaluate whether the Advisor Strategy skill should be built before or after cross-dept-sync"
- "Decide the classification tier for [new task type we haven't seen before]"

### Tier A non-negotiables (always A regardless of other factors):
- Any Go/No-Go decision on a GovCon opportunity
- Any decision that gets logged to a decisions.md file
- Any skill architecture design
- Any decision affecting 2+ departments simultaneously
- Anything sent to a government contracting officer

---

## Tier A+ — Opus 4.7 Solo
**Profile:** Highest stakes, architecture-level, $10K+ impact or wrong trajectory risk
**Cost:** Highest. Reserve carefully.
**Requires:** the operator's explicit approval before dispatching
**Default max_tokens:** 32000 | Extended thinking: adaptive (effort: high)

### Example tasks (Tier A+):
- "Full business audit — grade all 6 departments and give recommendations"
- "Review the entire skill architecture and recommend what to build next and why"
- "Should the operator's business pivot focus from GovCon to Cyber Services this quarter?"
- "Design the full advisor-mode + cross-dept-sync integration architecture"
- "Evaluate whether the BlackBox Ledger is worth pursuing vs. doubling down on GovCon"
- "Review the multistage-skill-framework against the first 3 skills built — what's wrong with it?"

### When Opus advising itself (A+ with advisor):
This is valid and sometimes the right call — Opus as executor with Opus as advisor
creates a recursive review loop. Use only when:
- The task is genuinely novel (no precedent in Brain)
- The stakes justify the cost
- the operator explicitly requests it

---

## Ambiguous Cases — How to Decide

| Situation | Resolution |
|---|---|
| Task is B-level but result will be published externally | Bump to A |
| Task is A-level but deadline is in 30 minutes | Stay A, reduce max_uses to 2 |
| Task touches GovCon and Content equally | A (cross-dept = +2 on factor 3) |
| the operator says "just quickly..." | Classify by the task, not the framing. "Just quickly decide the strategy for Cyber Services" is still A. |
| Task is novel — never seen before | Default to one tier higher than your first instinct |
| the operator pushes back that the tier is too high | Accept the override. Log it. If the output is wrong, note it. |

---

## Fast-Track Reference (confirmed by escalation history)

These task types have been confirmed at the listed tier through use:

| Task type | Confirmed tier | Date confirmed |
|---|---|---|
| GovCon Go/No-Go decisions | A | 2026-04-15 (initial classification) |
| Skill architecture design | A | 2026-04-15 (initial classification) |
| Company-wide audit | A+ | 2026-04-15 (initial classification) |
| Vendor outreach drafts | B | 2026-04-15 (initial classification) |
| File formatting/renaming | C | 2026-04-15 (initial classification) |

*(This table grows as escalation history confirms or corrects classifications)*

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[decisions]]
- [[stage1_classify]]

<!-- AUTOLINK-END -->
