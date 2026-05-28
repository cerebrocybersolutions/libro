# Stage 0 — Turn-Start Probe Reference

*Introduced in sessionstart v2.3 (2026-04-21). Governs the short-circuit path for same-day
reopens within the 1h break window. See SKILL.md § Stage 0 for the full algorithm.*

---

## Probe Output Template

Render exactly these three lines when Stage 0 fires:

```
Previous session: {session_id} (closed {hh:mm})
Open loops carried: {N} — see Q2 on demand
Delta since close: {top-3 commits or "working tree dirty — see git status"}
```

**session_id** — the filename stem of the most recent closed session file (e.g.
`2026-04-21-ops-chunks-cited-close-trim-plan-signoff`).

**hh:mm** — the extracted close timestamp (see §Close-Timestamp Extraction below).

**N** — count of items under the "Open Loops — Next Session" heading in that session file.
Do NOT enumerate them unless the operator explicitly asks ("see Q2 on demand" is the invite).

**Delta since close** — top 3 one-line entries from:

```bash
git log --oneline --since="{close_timestamp}" | head -3
```

If the working tree is dirty at read time, replace with:

```
working tree dirty — see git status
```

---

## Close-Timestamp Extraction

**Priority 1 — YAML frontmatter `closed_at` field (future-proofing):**

If the session file's YAML frontmatter includes:

```yaml
closed_at: 2026-04-21T15:30
```

use that value directly. This is the preferred explicit marker; sessionend will be updated to
write it in a future pass.

**Priority 2 — Inline `*Closed:` marker in body:**

If frontmatter lacks `closed_at`, scan the session body for a line matching:

```
*Closed: HH:MM*
```

or

```
Closed: HH:MM
```

Parse the time, combine with the session date (from filename `YYYY-MM-DD` prefix) → full
timestamp.

**Priority 3 — File mtime fallback:**

If neither explicit marker exists, use the session file's filesystem mtime as the close
approximation. This is less precise (file could have been touched post-close) but sufficient
for the 1h window comparison — false negatives (falling through to Stage 1) are safe.

**Timestamp comparison:**

```python
from datetime import datetime, timedelta
now = datetime.now()
close_dt = <extracted close_timestamp>
gap = now - close_dt
if gap < timedelta(hours=1):
    # fire Stage 0 probe
else:
    # fall through to Stage 1
```

---

## `git log --since` Flag Composition

Pass the close timestamp in ISO 8601 format:

```bash
git log --oneline --since="2026-04-21T15:30:00" | head -3
```

If file mtime was used, pass it directly:

```bash
git log --oneline --since="$(date -r path/to/session_file '+%Y-%m-%dT%H:%M:%S')" | head -3
```

On macOS, `date -r <file>` reads file mtime; on Linux use `stat --format='%y' <file>`.

---

## Edge Cases

| Condition | Behavior |
|-----------|----------|
| No session file exists for today | Fall through to Stage 1 — first session of the day. |
| Most recent session file is open (no close marker, status not `closed`) | Fall through to Stage 1 — session may still be live. |
| Gap > 1h (any timestamp method) | Fall through to Stage 1 — full brief warranted. |
| Working tree dirty at read time | Delta line: `working tree dirty — see git status`. Probe still fires if other conditions met. |
| Explicit `/sessionstart` slash-command | Bypass Stage 0 entirely — always run full Stage 1–5 brief. This is the the operator override path. |
| Multiple same-day session files | Use the one with the latest mtime (most recent close). |

---

## 1h Window Rationale

Window default (operator-configurable):

The 1h window is a conservative default. Adjust on the operator's explicit call — do not
auto-loosen the window based on session-file gap patterns.

If the operator finds the window too tight or too loose, surface as a decision item
before changing SKILL.md or this file.

---

## Rollback

Delete this file + the Stage 0 block from `SKILL.md`. Returns to v2.2.1 behavior exactly.
Single-commit revert is sufficient (Reversibility #5 — additive insertion).

```bash
git revert <stage0-commit-sha>
```

---

## Principles Touched

| Principle | Role |
|-----------|------|
| Governance #1 | Stage 0 reads session files along chain-of-command (dept Brain → Master Brain order from SKILL.md Stage 1) — same access pattern, just earlier gate. |
| Parity #2 | Probe output mirrors the actual state drift since close (git delta + open loops count) — brief stays in lockstep with reality even for fast reopens. |
| Lockstep #3 | Stage 0 does not write anything; sessionend writes the same frontmatter regardless of which open path fires next session. |
| Human-in-the-Mix #4 | 1h window sourced from the operator directly. `/sessionstart` slash-command preserves manual override. Window adjustment requires explicit the operator call. |
| Reversibility #5 | Additive block + this reference doc. `git revert` restores v2.2.1. No existing stage modified. |
| Observability #6 | Probe output is explicit (3 lines, always rendered) — operator can see at a glance whether short-circuit fired or fell through. |
| Reproducibility #8 | Close-timestamp extraction priority documented; fallback order deterministic; same input (session file + git log) → same output every run. |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[SKILL]]

<!-- AUTOLINK-END -->
