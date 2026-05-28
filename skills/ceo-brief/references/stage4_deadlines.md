# Stage 4 — Deadline Scan

Run this when the operator asks specifically about what's due soon.

## Step 1: Collect All Deadlines

Scan these sources:
1. `master-brain/DASHBOARD.md` — "Upcoming Deadlines" table
2. Any session Open Loops mentioning dates (look for "due", "deadline", "by [date]", "before [date]")
3. GovCon: `govcon/brain/sessions/` — check for RFQ deadlines in Open Loops

Parse dates into ISO format (YYYY-MM-DD) for sorting.

## Step 2: Classify by Urgency

Calculate days from today:
- **Critical** (0–3 days): Act today or tomorrow — no time to deliberate
- **Urgent** (4–7 days): Must be on the operator's radar this session
- **Upcoming** (8–14 days): Plan ahead this week
- **On Horizon** (15–30 days): Know it's coming

Omit anything beyond 30 days — too far out to be actionable today.

## Step 3: Output Format

```
## Deadline Scan — [Date]

### 🔴 Critical (3 days or less)
- [Date] | [Item] | [Dept] | [What needs to happen]

### 🟡 Urgent (this week)
- [Date] | [Item] | [Dept] | [What needs to happen]

### 📅 Upcoming (next 2 weeks)
- [Date] | [Item] | [Dept] | [Status]
```

If nothing is in Critical, say so — it's good news the operator should know.

## Key Rule
For any GovCon deadline, subtract 3 working days for the "action by" date —
you need time to source vendors, build the packet, and draft the submission email
before the SAM.gov due date. Always show both the SAM.gov due date AND
the "last day to act" date.

*Note (2026-04-17): Cerebro is currently in **infrastructure mode** — no active
bid/submission/award arcs. Deadlines still matter for positioning and watchlist,
but don't auto-push packet-building work into the upcoming week unless the operator
has explicitly moved out of infrastructure mode.*

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]

<!-- AUTOLINK-END -->
