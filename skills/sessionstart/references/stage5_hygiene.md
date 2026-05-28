# Stage 5 — Memory Hygiene (NEW in v2)

## Why this stage exists

Stage 2.5 detected drift. Stage 3 displayed the corrections at the top of the brief.
Stage 5 is the write-back: actually update memory files, update the MEMORY.md index, and
log the correction to an audit trail.

v1 had no equivalent — which is how the ruflo P1 stayed stale across multiple sessions.

## Default mode: auto-correct

the operator chose auto-correct-and-log as the default mode (2026-04-17). Rationale: the ruflo
miss cost more than any auto-correction risk, and the operator has the audit log + rollback if
a correction goes wrong.

**Auto-correct means:**
1. Update the memory file body in-place with the new ground-truth claim
2. Update the MEMORY.md index hook if the short description needs rewording
3. Append the correction to `master-brain/state/memory-corrections.log`
4. Show the correction in the Memory Drift block at top of the brief

## Audit log format

Append to `master-brain/state/memory-corrections.log`:

```
---
timestamp: 2026-04-17T23:42:15
memory_file: project_ruflo_ingest_filter_gap.md
session: 2026-04-17-ops-queue-clear
trigger: stage25_verify probe
old_claim: "PRIORITY 1 next session. Ship wiki.toml exclude."
new_claim: "MITIGATED by file-system layout. Wrapper queued as P3."
probe_used: "find master-brain/knowledge-vault -type d -name ruflo-main"
probe_result: "ruflo-main is at raw/processed/ — filtered by Karpathy path-parts"
index_updated: true
reversible: true
rollback_command: "git checkout HEAD~1 -- <memory-mount>/project_ruflo_ingest_filter_gap.md"
---
```

## What NOT to auto-correct

Some drift findings require the operator's judgment. Surface these as "⚠️ Needs the operator's call"
in the brief — don't auto-write. Examples:

- Memory claims a **decision** is open, reality shows a session implicitly resolved it,
  but the resolution isn't explicit (ambiguous). Surface as "appears resolved in SESSION-X,
  confirm?"
- Memory claims an **infrastructure posture** (e.g., "Western-only model policy"), reality
  shows a config exception. Surface as "policy vs. config tension — confirm intent?"
- Memory claims a **revenue priority** (Cyber Services lead-service, GovCon bid), reality
  shows inactivity. Don't auto-close revenue decisions. Surface as "still open, aging X
  sessions."

Pattern: **auto-correct facts, surface judgment calls.**

## Interaction with awareness.md drift

Stage 4 produces drift findings when awareness.md flags contradict reality. Stage 5
does NOT auto-correct awareness.md — that's a sessionend responsibility (awareness.md is
a sessionend-owned artifact). Instead, Stage 5:
- Notes the awareness.md drift in the audit log
- Adds a reminder to tonight's sessionend: "refresh [dept] block in awareness.md"

## Output

Most of Stage 5's output went into the Memory Drift block at top of Stage 3's brief.
Stage 5's standalone output is just the audit log append + any "needs the operator's call" items
that didn't auto-correct.

Example final output at the end of the brief:

```
---
Memory hygiene: 2 auto-corrections logged + 1 needs-your-call flagged above.
Rollback any correction with: `cat master-brain/state/memory-corrections.log` then git revert.
```

## Timing budget

Stage 5 should complete in under 3 seconds. It's pure file I/O once Stage 2.5 has already
found the drift.

## Governance

This stage respects `BRAIN_GOVERNANCE.md`:
- Department-specific memory claims are corrected against department Brain files only
- Company-wide claims are corrected against Master Brain
- No Stage 5 correction crosses department boundaries without explicit `## Cross-department notes`
  evidence in the source session file

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[BRAIN_GOVERNANCE]]
- [[MEMORY]]
- [[awareness]]
- [[project_ruflo_ingest_filter_gap]]

<!-- AUTOLINK-END -->
