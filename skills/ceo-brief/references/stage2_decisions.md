# Stage 2 — Decisions-Only View

Run this when the operator asks specifically about pending decisions or decision backlog.

## Step 1: Load All decisions.md Files
Read decisions.md from every department Brain:
- `govcon/brain/decisions/decisions.md`
- `content-creation/brain/decisions/decisions.md` (if exists)
- `cyber-services/brain/decisions/decisions.md` (if exists)
- `products/brain/decisions/decisions.md` (if exists — consolidated 2026-04-22 EVE from `digital-products/` + `blackbox-ledger/`)
- `master-brain/decisions/` (Master Brain — ops-level decisions)

For each file, if it doesn't exist yet, note "no decisions logged" for that dept.

*Pre-2026-04-17 folder names (Title Case / spaces) may still exist for tiers that
haven't migrated. Check `master-brain/NAMING_CONVENTION.md` "Tier Status" before
failing a read.*

## Step 2: Classify Each Decision

**RESOLVED** — entry has a clear outcome stated, no follow-up needed
**PENDING** — question or option raised with no locked answer
**NEEDS INPUT** — explicitly says "the operator decides" or "TBD"

Only surface PENDING and NEEDS INPUT in the output.

## Step 3: Age the Pending Decisions

For each pending decision, calculate days since logged (from the date in the entry header).
Classify:
- **Urgent** (14+ days): This is blocking something or has been deferred too long
- **Aging** (7–13 days): Needs attention this week
- **Recent** (0–6 days): On the operator's radar, no action needed today

## Step 4: Output Format

```
## Pending Decisions — [Date]

### 🔴 Urgent (14+ days open)
1. [Decision title] — [Dept] — [X days] — [1-line context]

### 🟡 Aging (7–13 days)
1. [Decision title] — [Dept] — [X days] — [1-line context]

### ⚪ Recent (this week)
1. [Decision title] — [Dept] — [X days]
```

After outputting, ask: "Want to resolve any of these now?"
If yes, route to the appropriate department skill or handle inline,
then log the decision to the correct dept `decisions.md`.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[NAMING_CONVENTION]]
- [[decisions]]

<!-- AUTOLINK-END -->
