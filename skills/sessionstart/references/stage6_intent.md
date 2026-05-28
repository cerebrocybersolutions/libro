# Stage 6 — Capture Session Intent

## Unclosed-Session Handling (NEW v2.1 — Gap 1, runs BEFORE the standard intent question)

If Stage 2.5's closure-check flagged the last session as UNCLOSED, you MUST ask this first,
BEFORE the standard "What's the goal" question. Do not roll the previous session's open
loops into today until the operator picks one:

> "Last session (`[filename]`) wasn't closed out. Pick one:
>   (a) Retroactive-close it — tell me what it actually ended on and I'll write a proper close
>   (b) Adopt its WIP as today's intent — we keep going where it left off, I'll close it at today's sessionend
>   (c) Start fresh — I'll archive the hanging file untouched and we begin clean"

**Handling by answer:**

- **(a) Retroactive-close** → Invoke sessionend's Step 10 retroactive-close mode on the
  hanging file with what the operator reports. Once closed, proceed to the standard intent
  question. Any Open Loops the operator names during the retroactive close are candidates for
  today's incoming state.

- **(b) Adopt WIP** → Use the hanging session file's `*Intent:*` and any visible WIP as
  today's starting context. Ask the standard intent question framed as: "Picking up from
  `[filename]`. What's the goal for today — same track or adjusted?" Today's sessionend
  will close BOTH files (hanging + today) via the writeback guard.

- **(c) Fresh start** → Rename the hanging file with suffix `-unclosed-archived.md` (do not
  delete). Proceed to the standard intent question as if it were a first session.

Record the operator's choice in today's session file header:

```markdown
*Prior session handling: (a|b|c) — see [filename] for details*
```

## Ask One Question (standard — runs once closure handling is resolved)

> "What's the goal for this session?"

Wait for the operator's answer. Don't suggest goals — let them pick.

## Write Intent Header to Brain

**Target path** (Tier 3 kebab-case with capital-B fallback):
`[dept]/brain/sessions/YYYY-MM-DD-[dept].md`

If the file doesn't exist yet, create it with this header:

```markdown
## Session: [dept] — YYYY-MM-DD
*Intent: [the operator's stated goal — verbatim or lightly cleaned up]*
*Opened: [time if known]*

---
```

If the file already exists (sessionend already wrote today, or sessionstart reopened it),
append:

```markdown
---
*Session reopened — Intent: [the operator's stated goal]*
*Time: [HH:MM]*
```

This gives sessionend a clear target to close against. One session, one intent, one close.

## Multi-session days

If the operator opens multiple sessions in a single day (sessionend, then sessionstart again),
use distinct filenames:
- First session: `2026-04-17-ops.md`
- Second session: `2026-04-17-ops-queue-clear.md` (suffix describes intent)
- Third session: `2026-04-17-ops-pm-debug.md`

Naming convention per `master-brain/NAMING_CONVENTION.md`: kebab-case, ISO date prefix,
dept code, optional descriptive suffix. Avoid filenames like `YYYY-MM-DD-ops2.md` — use a
word suffix.

## Cross-session reference

If this session is a continuation of earlier work today, cite the prior session file in the
header:

```markdown
## Session: ops-queue-clear — 2026-04-17 PM-late
*Intent: Work infrastructure queue while OLW ingests.*
*Continues from: 2026-04-17-audit-v2.md*
*Opened: PM-late*

---
```

This gives the next sessionstart a breadcrumb for reconstructing the day's arc.

## Handoff

Stage 6 is the final stage. Once intent is captured and written to the Brain:
- The session is open
- The brief is delivered
- Drift is corrected (auto-corrected or surfaced)
- Infrastructure state is known
- Cross-dept flags are verified

the operator walks into the room already oriented. Zero cold-start tax.

## What NOT to do

- Don't ask follow-up questions about the intent ("are you sure?", "any specific deliverables?")
- Don't attempt to narrow the intent yourself — the intent is the operator's call
- Don't write an intent that the operator didn't state. If they say "let's see where this goes,"
  write that verbatim
- Don't skip writing the header — sessionend depends on it to close cleanly

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[-unclosed-archived]]
- [[2026-04-17-audit-v2]]
- [[2026-04-17-ops]]
- [[2026-04-17-ops-pm-debug]]
- [[2026-04-17-ops-queue-clear]]
- [[NAMING_CONVENTION]]
- [[YYYY-MM-DD-ops2]]

<!-- AUTOLINK-END -->
