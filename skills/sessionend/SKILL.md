---
name: sessionend
description: "End-of-session ritual — reflects on what happened, stores a structured session summary to the correct department Brain, updates the Master Dashboard, updates the Master Brain awareness layer, and updates local memory. Use when the user types /sessionend or says they're done for the session, wrapping up, or signing off."
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: ["brain-setup", "sessionstart"]
    profile_vars: ["brain_root", "operator_departments", "operator_name", "workspace_root"]
---

# Session End

A closing ritual that turns each session into institutional memory. Goal: nothing gets
lost between sessions, and an honest record builds over time so the system improves.

---

## BRAIN STRUCTURE — Know Before You Write

```
Master Brain (Chief of Staff):
  {brain_root}/mission-control/
    DASHBOARD.md     ← status table — update every sessionend
    awareness.md     ← narrative layer — update every sessionend
    decisions/       ← ops-level, cross-dept decisions
    sessions/        ← master/ops sessions only

Department Brains (kebab-case, lowercase `brain/` at every dept):
  {operator_departments} — configured in brain.config.yml at install time
  # Pattern:
  #   {dept}/brain/sessions/           | decisions/
```

Department codes: configured in `brain.config.yml` — set at install time per operator's dept roster.

---

## Step 1 — Read the Session

Review the conversation — what was built, decided, or left unfinished. Run a quick git check:

```bash
git -C $(pwd) log --oneline --since="8 hours ago" 2>/dev/null || true
```

---

## Step 2 — Confirm Department

Auto-detect the department from what was worked on. Ask operator with a single short line:

> "Wrapping up as **[dept]** — good?"

One word confirms. If they name a different dept, use that. For multi-dept sessions: "Wrapping up as **sales + ops** — good?"

---

## Step 3 — Reflect Honestly

Before writing, evaluate — don't just summarize:

- What was actually accomplished? (concrete outputs, not effort)
- What decisions were made and locked?
- What went wrong or needed retrying?
- What's unfinished and needs follow-up?

---

## Step 4 — Write to Department Brain

**Path:** `{dept}/brain/sessions/YYYY-MM-DD-{slug}-{dept}.md` (kebab-case, lowercase `brain/` canonical at every dept).

If a session file already exists for today, append a second block rather than overwriting.

**Required: frontmatter block at the top of every session note.** Schema:

```yaml
---
date: YYYY-MM-DD
session_id: {slug}                       # kebab-case summary of session
dept: {operator_dept_code}               # configured in brain.config.yml
session_shape: dept-work|ops-infra|mixed
status: closed                           # or "open" if retroactive close pending
decisions_made: [decision-doc-filenames-or-blank]
open_loops:
  - {item}: open|queued|scheduled|completed
blockers: []
cross_dept:
  {dept}: {one-line reason — omit if none}
principles_touched: [list of principles applied this session]
---
```

Body follows immediately under the frontmatter:

```markdown
## Session: [dept] — YYYY-MM-DD

### Accomplished
- {what exists now that didn't before}

### Decisions Made
- {locked decisions — brief}

### What went well
- {specific}

### What went wrong
- {honest}

### How to improve
- {actionable}

### Open Loops — Next Session
- {unfinished items}

### Cross-department notes
- {anything other depts should know — omit if none}
```

**If decisions were made**, append to `{dept}/brain/decisions/decisions.md`:

```markdown
## [YYYY-MM-DD] — {Decision Title}
{1–3 sentences: what was decided and why.}
```

---

## Step 5 — Dashboard is a view, not a log

**DASHBOARD.md is a view rendered from frontmatter — do NOT append prose to it.**

- The file is static top-matter + DataView/Q1–Q4 queries. Hand-editing it re-introduces bloat.
- Dashboard freshness is provided by the frontmatter block written in Step 4.
- To verify post-session render, run:
  ```bash
  python3 {brain_root}/mission-control/skills/dashboard-view/dashboard_render.py --query all
  ```
- The ONLY time DASHBOARD top-matter gets hand-edited: (a) framework state change, (b) strategic pivot / doctrine update, (c) operating-model sequence change. Everything else is rendered.

---

## Step 6 — awareness.md is per-dept quick-state only

**Do NOT append narrative blocks to `awareness.md`.** Narrative belongs in the session note body (Step 4).

- **The per-dept one-liner ALWAYS updates at every sessionend** — rewrite it to reflect the session just closed. Format:
  ```
  **Dept** — 🟢/🟡 · Last: YYYY-MM-DD ({session_id summary}: {1-line what moved}) · **Open: {open_loops summary — max 5 items, semicolon-separated}.** Pending decisions: {none|item}.
  ```
  - If `open_loops:` frontmatter is empty: write `Open: none.`
  - If `open_loops:` has URGENT-class items (operator-manual, human-in-the-mix gate, credential exposure): prefix with `🔴 URGENT:` before listing
  - Do NOT leave the prior one-liner in place — stale "Next:" clauses from prior sessions persist invisibly. **Always overwrite.**
- Q1 in `awareness.md` renders "latest session per dept" from session-note frontmatter but does NOT render `open_loops` inline — the one-liner is the only human-visible open-loop surface.

**Why "ONLY if state changed" was wrong:** That earlier framing caused open-loop drift — the one-liner is the only place open loops surface in the awareness layer. Leaving it stale = invisible loops. Always overwrite.

---

## Step 7 — Update Local Memory

Persist anything new:
- New preferences or feedback → `feedback_*.md`
- New project facts → `project_*.md`
- New info about operator → `user_*.md`
- New external resource pointers → `reference_*.md`

Update `MEMORY.md` index if anything changed. Only save what's genuinely new.

---

## Step 7.02 — MEMORY.md Size Probe

Probe `MEMORY.md` against the 20 KB hard / 16 KB consolidation caps. Advisory only — never auto-edits.

```bash
python3 {brain_root}/mission-control/skills/sessionend/Scripts/memory_size_probe.py
```

**Behavior by exit code:**
- `0` (under trigger) — no action; do not surface
- `1` (consolidation trigger, ≥16 KB) — add to session frontmatter `open_loops`: `MEMORY.md consolidation pass — at <pct>% of 20KB cap`
- `2` (over hard cap, ≥20 KB) — same open-loop entry tagged `P1`; surface in Step 8 CEO Brief under "What's Stuck" if not already addressed

**Manual consolidation procedure** (operator-driven, never auto): inline-collapse superseded entries OR archive memory file under `archive/` and remove from MEMORY.md index. Re-run probe to confirm under trigger.

**Why caps exist:** MEMORY.md is loaded into every session context. Past 16 KB, retrieval cost outpaces value; past 20 KB, context budget gets squeezed. Caps force periodic consolidation, which is also when stale or superseded entries get pruned.

---

## Step 7.5 — Writeback Guard

Before moving to the CEO Brief, verify the session-note frontmatter and downstream-render path produced the rollup signal.

Run this self-check:

1. **Session file** — confirm written at `{dept}/brain/sessions/YYYY-MM-DD-{slug}-{dept}.md`.
   File exists? ✅ / ❌
2. **Frontmatter block** — confirm the session note starts with `---\n` and contains all required fields.
   Grep check: `head -20 {session-file} | grep -E '^(date|dept|status|open_loops):'` should show 4+ matches.
3. **Rollup render** — confirm Q1 surfaces today's session note for this dept:
   ```bash
   python3 {brain_root}/mission-control/skills/dashboard-view/dashboard_render.py --query q1 | grep $(date +%Y-%m-%d)
   ```
4. **decisions.md** (if decisions were made) — confirm appended.
5. **Memory** — if new memory entries were saved, confirm MEMORY.md index updated.
6. **Parity drift check — CONDITIONAL.** Fires only when the session-in-close touched any of:
   - `{brain_root}/mission-control/decisions/**`
   - `{brain_root}/mission-control/skills/**`
   - `{brain_root}/mission-control/CLAUDE.md` or any dept `CLAUDE.md`
   - `{brain_root}/mission-control/state/fleet-dispatch.json` or routing artifacts

   Detection: `git -C $(pwd) status --porcelain` slice against those paths. If any match, run:
   ```bash
   python3 {brain_root}/mission-control/skills/sessionend/Scripts/parity_drift_check.py
   ```
   Output is advisory — session close is NOT blocked. Surface the findings to operator.

7. **Council-halts scan — CONDITIONAL.** Fires when `{brain_root}/mission-control/state/council-halts.jsonl` exists and is non-empty.
   - Filter to rows where `outcome == "HALT_TO_OPERATOR"` and `ts` is within the last 30 days.
   - Surface in the CEO Brief under a `⚠️ Council halts` section. Do NOT delete rows — append-only.

If ANY of steps 1–5 failed:
- DO NOT proceed to CEO Brief
- Surface the miss and prompt retry

---

## Step 7.6 — Inventory Stamp

**Trigger:** Fires only when the working tree has any dirty files. Skip on clean tree.

```bash
git -C $(pwd) status --porcelain | wc -l
```
If count > 0: run the stamp. If count == 0: skip.

**Invocation (Claude Code surface):**
```bash
python3 {brain_root}/mission-control/skills/inventory-stamp/inventory_stamp.py
```

Stamp writes:
- `{brain_root}/mission-control/INVENTORY.md` — frontmatter + category tables
- Appends one JSON row to `{brain_root}/mission-control/state/inventory-history.jsonl`

---

## Step 7.62 — Manifest Drift Check

**Trigger:** Always run — read-only and fast.

```bash
python3 {brain_root}/mission-control/skills/sessionend/Scripts/manifest_drift_check.py
```

Walks the workspace manifest and live filesystem to detect drift. Always exits 0 — never blocks close. If `REBUILD NEEDED`, print the notice to operator but continue.

---

## Step 7.75 — Commit or Handoff (surface-aware)

> **CC DEFAULT:** Claude Code CAN run `git commit`. If `LIBRO_HANDOFF_SESSION_ID` is NOT set, **commit the dirty files directly — do NOT emit a handoff block**.

**Surface detection:** Check `LIBRO_HANDOFF_SESSION_ID` env var.
- **UNSET** → Claude Code surface. Run `git add` + `git commit` directly. Surface one summary line.
- **SET** → Handoff surface. Emit the handoff block (format below).

**Trigger:** `git -C $(pwd) status --porcelain | wc -l`. If count > 0, enter the surface-appropriate path.

**Thresholds:**
- `0` dirty files → skip this step entirely
- `1–5` dirty files → one-batch commit/handoff
- `6+` dirty files → multi-batch (group by logical area: infra/scripts, session notes, decision docs, HTML artifacts, memory)

**Handoff block format:**

```markdown
---
## 📋 Claude Code Commit-Batch Handoff — [YYYY-MM-DD] [dept]

Working tree has **N** dirty files. Run these commits on-metal:

### Batch 1 — {batch-label} ({count} files)
\`\`\`bash
cd {workspace_root}
git add {file1} {file2} {...}
git commit -m "{one-line-subject}"
\`\`\`
...

**Out of batch (do NOT commit):**
- Auto-memory layer files (stay in the runtime sandbox; never enter version control)
- `.claude/settings.local.json` (local IDE state)
- Any `*.log` or scratch files
---
```

**Guardrails:**
- NEVER include credential files in the batch. Flag separately with a 🚨 line.
- NEVER include auto-memory layer files in the batch.
- Pre-existing dirty files not touched this session → call out separately, not folded into batch.

---

## Step 7.8 — CC Queue Auto-Emit

**Trigger:** Glob `{brain_root}/mission-control/handoffs/README.md` for rows under `## 🟢 Open — real work`. If count > 0, emit the QUEUE block between Step 8 and Step 9.

**Queue block format:**

```markdown
---
## 📋 CC QUEUE — [YYYY-MM-DD] (N open)

1. 🟢 RUN ME · {action one-liner}
   File: {brain_root}/mission-control/handoffs/{exact-filename}.md
   Pre-batch tag: {tag}
   Verification ribbon: §{n} ({count} checks)
---
```

If `handoffs/README.md` is missing: emit `🚨 README parse failed — surface manually` and continue.

---

## Step 8 — CEO Brief

Read `{brain_root}/mission-control/awareness.md` and deliver:

```
✅ Session closed — [dept] | [date]

## CEO Brief

### 🟢 What Moved
[Dept]: [1 line — concrete outcome]

### 🔴 What's Stuck
[Dept]: [1 line — what's blocked and why]

### ⚡ Decisions Needed
1. [Decision] — [Dept] — [urgency]

### 📅 Upcoming (next 14 days)
- [Date] | [Item] | [Dept] | [Status]

### 💡 One Insight
[The one thing connecting dots across departments]
```

Omit any section with nothing to report.

---

## Step 9 — Operator's Rebuttal

After delivering the CEO Brief, pause and ask:

> "Any rebuttals or corrections?"

If the operator pushes back:

1. **Acknowledge** what's being corrected — don't defend the brief.
2. **Update the department Brain session file** — append a rebuttal block.
3. **Update awareness.md** — correct the relevant department section.
4. **If the rebuttal changes a decision** — append to the relevant `decisions.md`.
5. **Confirm the correction** — one line back.

If nothing to add, close with:
> "Session closed. ✅"

---

## Step 10 — Retroactive-Close Mode

Triggered by sessionstart's unclosed-session handling flow. Sessionstart hands off a target filename; sessionend runs a minimal closure ritual against it.

**Do NOT run Steps 1-9 in retroactive mode.**

Steps:
1. **Read the unclosed session file** — extract completed tasks and incomplete tasks.
2. **Reconstruct Accomplished block** from completed tasks only — don't invent outcomes.
3. **Reconstruct Open Loops block** from incomplete tasks.
4. **Append to the unclosed file:**

```markdown
---
### Retroactive closure — [today's date]
*Closed after the fact on YYYY-MM-DD.*

### Accomplished (reconstructed)
- {only confirmed completions from file body}

### Open Loops — Next Session (carried forward)
- {incomplete items flagged in file body}

*Closed retroactively: [HH:MM]*
```

5. **Update DASHBOARD.md + awareness.md** minimally — only the dept row needs a "Last session: [date]" correction.
6. **DO NOT run CEO Brief** — Steps 8 and 9 are skipped.
7. **Hand back to sessionstart** — confirm closure succeeded.

**Guardrails:**
- Retroactive close NEVER invents accomplishments.
- NEVER overwrites a newer closed-session's writeback.
- Stale open loops can be dropped, not blindly forwarded.

---

## Scope Contract

| Dimension | Scope |
|-----------|-------|
| Read paths | Conversation transcript · `git log --since="8 hours ago"` · `{dept}/brain/sessions/` · `{brain_root}/mission-control/DASHBOARD.md` + `awareness.md` · auto-memory layer `MEMORY.md` |
| Write paths | `{dept}/brain/sessions/YYYY-MM-DD-{slug}-{dept}.md` (create or append) · `{dept}/brain/decisions/decisions.md` + per-decision doc · auto-memory layer `{user,feedback,project,reference}_*.md` + `MEMORY.md` · `{brain_root}/mission-control/INVENTORY.md` + `state/inventory-history.jsonl` (Step 7.6 if dirty tree) · (Step 10 only) existing unclosed session file append |
| MCP / tool surface | Read, Bash (git status/log, dashboard_render.py), Write/Edit (session note, decisions, memory) |
| Network egress | None |
| Surface | Claude Code primary |
| Credentials | None required; Step 7.75 actively filters credential files from commit batches |
| Escalation trigger | Step 7.5 writeback guard fails → pause, surface miss, prompt retry · Step 7.75 detects credential file in dirty tree → 🚨 flag, exclude from batch · Step 9 Operator's Rebuttal: any correction that changes a decision re-routes to decisions.md append |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[INVENTORY]]
- [[MEMORY]]
- [[awareness]]
- [[decisions]]

<!-- AUTOLINK-END -->
