# Stage 1 — Full CEO Brief

Run this when the operator wants a complete company picture.

## Step 1: Load DASHBOARD.md
Read `master-brain/DASHBOARD.md`. Note:
- Which departments are 🟢 / 🟡 / 🔴
- Any active red flags
- Upcoming deadlines already listed
- Last session dates per department

## Step 2: Load Recent Sessions (last 7 days only)
For each department with a session in the last 7 days, read the most recent
session file from their `brain/sessions/` folder. Extract:
- **Accomplished** section (what actually happened)
- **Open Loops** section (what's unfinished)
- **Decisions Made** section (what was locked)

Skip departments with no sessions in 7 days — flag them as dormant in the brief.

## Step 3: Load Pending Decisions
For each active department, read their `decisions.md` file.
Flag any entry that is:
- Not marked as resolved
- Older than 7 days (compare date in entry header to today's date)

These go into the "Decisions Needed" section of the brief.

## Step 4: Load Circuit-Breaker State
Read `master-brain/state/circuit-breakers.json` (created by orchestrator-mode).

Expected shape:
```json
{
  "breakers": {
    "B::solicitation_eval": {
      "state": "open",
      "failures": ["2026-04-17T14:12:03Z", "..."],
      "opened_at": "2026-04-17T14:12:03Z"
    },
    ...
  }
}
```

For each breaker entry:
- If `state == "closed"` → ignore (normal operation).
- If `state == "open"` → compute hours-since-`opened_at`. Surface in the brief.
- If `state == "half-open"` → surface as "probing next request" with last-opened timestamp.

If the file is absent or every breaker is `closed`, **omit the Routing Health section entirely**.

Quick inspection command (for sanity when drafting a brief):
```bash
python3 master-brain/skills/orchestrator-mode/Scripts/circuit_breaker.py show
```

## Step 5: Compile and Output
Use the brief template from SKILL.md. Fill in:
- **What Moved**: pull from "Accomplished" in recent sessions
- **What's Stuck**: pull from "Open Loops" + any 🔴 departments
- **Decisions Needed**: aging pending decisions, sorted oldest first
- **Upcoming Deadlines**: pull from DASHBOARD.md + any session Open Loops with dates
- **Routing Health**: ONLY if any breaker is open/half-open (see Step 4). Format:
  `[tier / task-class] | [state] | [hours since open]`
- **One Insight**: your synthesis — what pattern or risk connects the departments?

## Timing guidance
A full brief should take 1–2 minutes to generate. If you're spending more time
than that, you're going too deep. The goal is signal, not a report.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[SKILL]]
- [[decisions]]

<!-- AUTOLINK-END -->
