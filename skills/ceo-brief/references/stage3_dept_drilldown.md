# Stage 3 — Department Drill-Down

Run this when the operator asks about a specific department.

## Step 1: Identify the Department
Map the operator's phrasing to a dept code and kebab-case folder:

| the operator says | Dept code | Folder |
|---|---|---|
| "GovCon", "contracts", "government", "SAM.gov" | `govcon` | `govcon/` |
| "content", "YouTube", "channel", "videos" | `content` | `content-creation/` |
| "cyber", "cybersecurity", "CMMC", "consulting" | `cyber` | `cyber-services/` |
| "products", "digital products", "Libro", "Clarity.fm", "BlackBox", "ledger" | `products` | `products/` |

*If a folder still exists under its pre-2026-04-17 name (Title Case / spaces),
the migration for that dept hasn't landed — check
`master-brain/NAMING_CONVENTION.md` "Tier Status" before failing the read.*

## Step 2: Load Full Dept Context
For the identified department:
1. Read last 3 session files from `<folder>/brain/sessions/`
2. Read `<folder>/brain/decisions/decisions.md`
3. Read `<folder>/brain/README.md` if it exists

## Step 3: Drill-Down Output Format

```
## [Department] Deep Dive — [Date]

### Status: 🟢/🟡/🔴

### What's Happened (last 3 sessions)
[Session date]: [1–2 line summary of what happened]
[Session date]: [1–2 line summary]
[Session date]: [1–2 line summary]

### Active Work
[What's in progress right now]

### Blockers
[What's preventing progress — be specific]

### Pending Decisions
[List from decisions.md — pending only]

### Next Right Move
[Single most valuable thing to do next session in this department]
```

The "Next Right Move" is not optional. Every dept drill-down should end with
a clear recommendation — even if it's just "make the Path A/B/C decision."

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[NAMING_CONVENTION]]
- [[decisions]]

<!-- AUTOLINK-END -->
