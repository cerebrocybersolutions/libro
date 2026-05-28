---
skill: cerebro-doctor
gate: Tan 10-step shipping gate
verdict: skeleton-v0 — not yet libro-ship-ready
last_evaluated: 2026-05-08
---

# Gate verdict — cerebro-doctor

| # | Step | Status | Note |
|---|---|---|---|
| 1 | Scope contract | ✅ | SKILL.md description clear; read-only scan. |
| 2 | Trigger discipline | ✅ | Trigger phrases named in description; use-when / don't-use-when distinguished. |
| 3 | Idempotent behavior | ✅ | Read-only scan is idempotent by construction. |
| 4 | Failure modes explicit | ⚠️ | Exit codes implicit; explicit failure-mode table pending. |
| 5 | Reversibility | ✅ | Skill is read-only; rollback = delete folder. Additive-only. |
| 6 | Observability | ⚠️ | No heartbeat; scans are fast — may not need one. |
| 7 | Resolver intents | ❌ | Not yet scaffolded in AGENTS.md. |
| 8 | Testing harness | ❌ | No fixtures or tests yet. |
| 9 | Filing rules | ✅ | Outputs to stdout; no state written. |
| 10 | Related / dependencies | ✅ | Parent decisions cited in Skills/AGENTS.md governance. |

**Overall:** 6/10 ship-gate steps fully green. Ship-gate status = **skeleton-v0 / not-yet-libro-ship-ready**.

## What lands this at green

1. Add resolver intents row to `master-brain/AGENTS.md`.
2. Scaffold `Scripts/tests/fixtures/` from `_template/`.
3. Explicit failure-mode table in SKILL.md body.
4. Wet-smoke against live `master-brain/skills/` tree — expect clean exit 0.

*Verdict skeleton-v0 locked 2026-05-08. Next revisit: when Scripts/ test harness lands.*

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[SKILL]]

<!-- AUTOLINK-END -->
