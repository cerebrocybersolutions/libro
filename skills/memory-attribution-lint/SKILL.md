---
name: memory-attribution-lint
description: Validate and auto-inject the 11-key provenance frontmatter contract on memory files at write time. Use when authoring memory entries, running lint passes on memory directories, or backfilling missing attribution fields. Enforces a uniform provenance schema (name, description, type, source_surface, host, tool, session_id, written_at_utc, source_path, confidence, lifecycle) so every memory entry is traceable to its origin surface, tool, and session.
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: []
    profile_vars: ["brain_root", "workspace_root"]
---

# memory-attribution-lint

Write-time validator + auto-injector for memory file frontmatter. Enforces an 11-key
provenance contract on `.md` files in memory directories. Closes the "where did this
memory come from?" gap by capturing source surface, tool, host, and session at write
time.

## Why provenance matters

Memory entries accumulate across sessions, tools, and surfaces. Without provenance,
stale or contradictory entries are hard to triage. The 11-key contract gives every
memory file a complete audit trail: who wrote it, from what tool, on what host, in
what session, at what time, with what confidence, and at what lifecycle stage.

## Contract

Required frontmatter keys:

| Key | Source | Auto-derived |
|---|---|---|
| name | author | NO |
| description | author | NO |
| type | author (user/feedback/project/reference) | NO |
| source_surface | env CLAUDE_SURFACE or default | YES |
| host | `socket.gethostname()` | YES |
| tool | env CLAUDE_TOOL or default `unknown` | YES |
| session_id | env CLAUDE_SESSION_ID or `unknown` | YES |
| written_at_utc | `datetime.now(timezone.utc).isoformat()` | YES |
| source_path | author declares | NO |
| confidence | author: high/med/low | NO |
| lifecycle | author: pinned/active/archived/closed/superseded/stale-by:YYYY-MM-DD | NO |

## Scripts

- `Scripts/lint.py` — validate + auto-inject; exit 0=pass, 1=blocked, 2=injected
- `Scripts/backfill.py` — bulk backfill existing memory files
- `Scripts/tests/fixtures/` — golden samples for validation cases

## Invocation

```bash
# Validate single file
python3 Scripts/lint.py path/to/memory.md

# Dry-run (report only)
python3 Scripts/lint.py --dry-run path/to/memory.md

# Backfill all memory dirs
python3 Scripts/backfill.py --dry-run
python3 Scripts/backfill.py --execute
```

## Hook wire (PreToolUse)

See `.claude/settings.json` `hooks.PreToolUse` → Write/Edit matching `**/memory/*.md`.
The hook fires lint on any Write/Edit to a file matching the pattern; exit 1 blocks the
write until missing required keys are supplied, exit 2 auto-injects derivable keys and
allows the write to proceed.

## Environment variables consumed

| Variable | Purpose | Default if unset |
|---|---|---|
| `CLAUDE_SURFACE` | Tool surface label (cc / hermes / etc.) | `unknown` |
| `CLAUDE_TOOL` | Specific tool that initiated the write | `unknown` |
| `CLAUDE_SESSION_ID` | Session identifier for cross-reference | `unknown` |

Set these at session start to capture full provenance automatically. Without them, the
required keys still pass validation (defaulted to `unknown`) but lose audit value.

## Scope Contract (Least-Privilege)

| Dimension | Scope |
|---|---|
| Read paths | Any `.md` file passed as target argument |
| Write paths | Same file (auto-inject mode only); never writes outside target |
| MCP / tool surface | None — pure Python, stdlib only |
| Network egress | None |
| Surface | Any (hook fires at write-time regardless of surface) |
| Credentials | None |
| Escalation trigger | Exit 1 (blocked write) — operator must add missing required keys manually |
