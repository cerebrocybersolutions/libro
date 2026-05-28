---
name: cerebro-doctor
description: >
  Meta-audit of the skill system. Walks `{brain_root}/skills/` +
  `{brain_root}/AGENTS.md` and reports three classes of drift: (a) skills with
  no resolver row (unreachable), (b) AGENTS.md rows pointing at missing skills
  (orphan phrases), (c) DRY overlap — two skills claiming the same trigger
  substring. Exit code 0 = clean; non-zero = drift. Trigger on: "cerebro
  doctor", "check resolvable", "skill health check", "resolver audit",
  "DRY audit", "are my skills reachable".
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: ["brain-setup"]
    profile_vars: ["brain_root"]
---

# skill-doctor

Mechanical audit of your skill resolver system. Three checks, one Python
script, no LLM in the loop.

---

## What it does

1. **Reachability** — every `{brain_root}/skills/<name>/SKILL.md` has at least
   one row in `{brain_root}/AGENTS.md` mapping a phrase to `<name>`.
   "Surgeon on staff but not in the hospital directory" — if a skill exists
   but nothing routes to it, it's invisible.

2. **Orphan phrases** — every AGENTS.md row points at a skill that actually
   exists (not archived, not typo'd). Catches stale rows after a skill retires.

3. **DRY overlap** — no two active skills claim the same trigger substring in
   their SKILL.md `description:` frontmatter. When overlap is legitimate, the
   fix is a discriminator row in AGENTS.md under "Known DRY pairs." When
   overlap is a bug, the fix is narrowing the SKILL.md description.

---

## How to run

```bash
python3 {brain_root}/skills/cerebro-doctor/Scripts/check_resolvable.py
```

Optional flags:
- `--root <path>` — override Brain root detection (default: walk up from script location)
- `--format json` — machine-readable output for daily cron integration
- `--quiet` — only print if there's drift

Exit codes:
- `0` — clean
- `1` — reachability drift (unreachable skill or orphan phrase)
- `2` — DRY overlap found
- `3` — both

---

## Scope contract

- **Reads:** `{brain_root}/skills/*/SKILL.md`, `{brain_root}/AGENTS.md`, `{brain_root}/skills/_archive/` (to disambiguate retired from missing)
- **Writes:** nothing. Read-only audit.
- **MCP / tools:** Python stdlib only. No network, no external models.
- **Network egress:** none.
- **Surface:** Claude Code (pure FS read). No git operations.
- **Credentials:** none required.
- **Escalation triggers:** if the script can't parse a SKILL.md frontmatter cleanly, it reports `PARSE_ERROR` for that file and keeps going. Does not abort.

---

## Filing rules

- Writes no Brain output. The script prints to stdout; callers decide whether
  to file the report.
- If a daily cron wraps this, it can file a digest at
  `{brain_root}/audits/<date>-skill-doctor.md` — that's the cron's filing rule,
  not this skill's.

---

## Known limitations (V0)

- DRY check uses naive substring matching on description text. False positives
  are possible (e.g., "find clients" vs "find solicitations" both contain
  "find" — the check uses multi-word phrases, not single words, to dampen this).
- Script-callability check (verifying every referenced script is callable) is
  **deferred to V1** — V0 only does reachability + DRY.
- No `--fix` mode. Drift surfaces; operator or next session authors the fix.

---

## Rollback

Delete `{brain_root}/skills/cerebro-doctor/`. AGENTS.md keeps working as a
human-readable registry; only the machine check goes away.

---

## Related

- `{brain_root}/AGENTS.md` — the resolver registry this audits
- `{brain_root}/skills/brain-setup/` — scaffolds the Brain this audits
- `{brain_root}/skills/sessionstart/` + `{brain_root}/skills/sessionend/` — session rituals that consume a healthy resolver

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[-skill-doctor]]
- [[SKILL]]

<!-- AUTOLINK-END -->
