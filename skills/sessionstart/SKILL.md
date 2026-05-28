---
name: sessionstart
description: Session opening ritual v2.4 — adds Stage 0 session-continuity probe (short-circuits full brief on same-day reopens within 1h break window), single-shot Stage 2 brief loader (one Bash call surfaces dept CLAUDE.md, latest session, pending decisions, dashboard header, memory index, and infrastructure state), runs ground-truth verification against filesystem (including a recursion guard so corrections themselves verify before firing), auto-corrects stale memory, delivers a Department Head Brief plus Infrastructure Snapshot, captures session intent, and renders the same brief to an HTML archive. Use when the user types /sessionstart or says they're getting started, picking up where they left off, or starting a new session.
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: ["brain-setup"]
    profile_vars: ["brain_root", "operator_departments", "operator_name", "house_theme_path"]
---

# Session Start — v2.4

The opening ritual that eliminates the cold-start problem. When you open a new session,
the department head is already briefed AND the machine state is verified. Goal: zero
re-orientation time and zero stale-memory action.

The counterpart to `/sessionend`. Where sessionend closes the loop, sessionstart opens it.

---

## BRAIN STRUCTURE — Know Before You Read

```
Master Brain (Chief of Staff):
  {brain_root}/mission-control/
    DASHBOARD.md             ← company-wide status
    awareness.md             ← per-dept running record (primary source for cross-dept flags)
    decisions/               ← company-wide strategic decisions
    state/                   ← live infrastructure state (circuit-breakers.json, etc.)
    NAMING_CONVENTION.md     ← canonical naming rules
    BRAIN_GOVERNANCE.md      ← chain-of-command rules
    skills/                  ← source-of-truth skill copies

Department Brains (kebab-case, lowercase `brain/` at every dept):
  {operator_departments} — configured in brain.config.yml at install time
  # Pattern:
  #   {dept}/brain/sessions/           | decisions/decisions.md | pipeline/current-state.md
```

**Path hygiene:** `brain/` (lowercase) is canonical at every dept. If a capital-B `Brain/` appears anywhere, surface it in Stage 2.5 as a drift finding and normalize.

Department codes: configured in `brain.config.yml` — set at install time per operator's dept roster.

---

## Stage 0 — Session continuity probe (runs first)

**Purpose:** Avoid re-running a full 5-stage brief when continuing a same-day session within the usual break window (~1h).

### Algorithm

1. Read most recent `{brain_root}/mission-control/sessions/YYYY-MM-DD-*.md` (any dept) by file mtime.
2. If `date == today` AND `status == closed` AND `(now - close_timestamp) < 1h`:
   - Render the 3-line turn-start probe (template in `references/stage0_turn_start.md`):
     - `Previous session: {session_id} (closed {hh:mm})`
     - `Open loops carried: {len(open_loops)} — see Q2 on demand`
     - `Delta since close: {top-3 commits from git log --since={close_timestamp}}`
   - Exit sessionstart. Do NOT run Stages 1–5.
3. Else (> 1h since close, or no same-day closed session, or status != closed) → proceed to Stage 1 normally.

### Guardrails

- **Explicit `/sessionstart` invocation always runs full Stage 1–5.** Stage 0 only short-circuits on implicit "pick up where we left off" opens.
- **Stage 2.5 recursion-rule untouched.** When Stage 0 falls through to Stage 1, the full verify-before-firing protocol runs unchanged.
- **Sessionend unaffected.** Sessionend writes frontmatter the same way regardless of whether the next session opens via Stage 0 or Stage 1.

See `references/stage0_turn_start.md` for the probe template, close-timestamp extraction strategy, and window rationale.

---

## The 8 Stages

### Stage 1 — Detect Department + Session Shape

See `references/stage1_detect.md`

- Auto-detect department from context, confirm rather than ask when confident.
- Detect **session shape**: `dept-work` (working inside one dept) vs. `ops-infra` (working on skills, infrastructure, the machine itself) vs. `mixed`. Shape drives Stage 2.5 depth.

### Stage 1.5 — Load Dept CLAUDE.md

See `references/stage1_detect.md` — "Department → CLAUDE.md Path Mapping"

Primary orientation doc is the dept CLAUDE.md, NOT workspace-root CLAUDE.md.

- Read `{dept}/CLAUDE.md` in full (60-100 lines — well under context budget)
- Use its "Mission", "Current state", "Canonical files", and "Dept non-negotiables" to frame the Stage 3 brief
- If the file doesn't exist, fall back to workspace-root `CLAUDE.md` and flag the miss as a Stage 2.5 drift finding ("dept CLAUDE.md missing — scaffold next")

### Stage 2 — Read Brain + Memory + Infrastructure State

See `references/stage2_read.md`

**Single-shot brief loader (preferred path).** Instead of issuing sequential Read calls per source, invoke one Bash script that emits all Stage 2 sections in a structured stdout block. Run the loader from the Brain root (or set `CLAUDE_PROJECT_DIR` to your `{brain_root}`) so the script resolves `PROJECT_DIR` correctly:

```bash
cd {brain_root}                     # or: export CLAUDE_PROJECT_DIR={brain_root}
.claude/skills/sessionstart/Scripts/brief_loader.sh --dept <dept> --shape <dept-work|ops-infra|mixed>
```

Sections emitted (always in this order, demarcated by `===NAME===` sentinels):
- `DEPT_CLAUDE` — dept-scoped CLAUDE.md (primary orientation doc)
- `LATEST_SESSION` — most recent session file frontmatter + closing block
- `DECISIONS_PENDING` — open / pending decisions for the dept
- `DASHBOARD_HEADER` — top-matter from Master Brain `DASHBOARD.md`
- `AWARENESS_DEPT` — current-date block from `awareness.md`
- `MEMORY_INDEX` — auto-memory layer `MEMORY.md` index, with **lifecycle filter** (terminal-state entries hidden)
- `STATE_FILES` — circuit-breakers + relevant infra config
- `FLEET_PROBE` — fleet host reachability (only on ops-infra / mixed)
- `MEMORY_SIZE` — auto-memory MEMORY.md size probe (warns near 16 KB consolidation cap)
- `DASHBOARD_RENDER` — agent-side Q1–Q4 render parity (latest-session-per-dept table)

Missing sections emit `SKIP — reason` instead of failing. Read the stdout block once; compose the brief from its sections. Do NOT re-read individual files after this — the loader output is the canonical Stage 2 snapshot.

**Frozen-snapshot invariant:** the MEMORY.md state captured by the loader is frozen for the session — do not re-read or re-weight mid-session. Any memory updates written during Stage 5 go to `state/memory-corrections.log` + the auto-memory layer; they do not retroactively alter this snapshot.

**Fallback (sequential reads).** If the loader script is missing or returns an error, fall back to sequential reads in this order:
1. Dept Brain: latest session file + `decisions/decisions.md` + `pipeline/current-state.md`
2. Master Brain: `DASHBOARD.md` header + `awareness.md` current-date block
3. `MEMORY.md` index (apply lifecycle filter manually — skip entries tagged terminal/closed/superseded)
4. Infrastructure state files (if session shape = `ops-infra` or `mixed`): `{brain_root}/mission-control/state/circuit-breakers.json` + any active process lock markers

### Stage 2.5 — Ground-Truth Verify

See `references/stage25_verify.md`

For every memory or decision being surfaced as "open" or "P1",
run the single filesystem check that would falsify it. Mark each as:
- ✅ confirmed — claim matches reality
- ⚠️ drift — claim doesn't match reality, memory needs update
- ❌ contradicted — reality shows the item is already resolved

Also runs infrastructure probes when session shape = `ops-infra`:
- Local model host alive? (`curl -s {OLLAMA_HOST}/api/tags` with 2s timeout)
- Any process lock in progress?

**Optional probes (run if installed; skip silently if absent):**
- **Skill discoverability lint** — `{brain_root}/mission-control/skills/skill-discoverability-lint/Scripts/lint.py` (optional). If present, surface any CRITICAL findings in the Stage 3 brief under "⚠️ Skill Drift". WARN/INFO: omit unless asked. Exit 0 always — never blocks session open. Not bundled in V1 profiles; install separately if you want the probe.
- **Handoff closure audit** — `{brain_root}/mission-control/skills/handoff-closure-audit/Scripts/audit.py` (optional). If present, surface DRIFT count only in Stage 3 brief if > 0. Full list on request. Not bundled in V1 profiles; install separately if you want the probe.

**Recursion guard.** A correction is itself a memory claim. Before any correction is queued for Stage 5, re-run the falsification probe against the *source* claim — including absence claims ("file X does NOT exist", "skill Y is NOT installed", "operator action required: do Z"). Restated claims surviving a context-compaction event are memory claims regardless of where they appear. Verify before firing, verify before restating. See `references/stage25_verify.md` §Recursion-rule.

### Stage 3 — Deliver Brief

See `references/stage3_brief.md`

```
🟢 [Department] — Session Brief | [date]

## Infrastructure Snapshot   ← only for ops-infra / mixed sessions
[1-3 lines on machine state: local model host, circuit breakers, key open loops at infra level]

## Incoming State
## Open Loops
## Pending Decisions
## Pipeline Position
```

### Stage 4 — Cross-Dept Flags

See `references/stage4_flags.md`

**Verify-before-surface for HIGH flags.** If awareness.md flags something HIGH, confirm against the implied source before surfacing. Stale HIGH flags are worse than no flag.

### Stage 5 — Memory Hygiene

See `references/stage5_hygiene.md`

If Stage 2.5 found drift, surface a "Memory Drift — Auto-Corrected" block at the top of the brief with what changed. **Default mode is auto-correct.** Every correction:
1. Is logged to `{brain_root}/mission-control/state/memory-corrections.log` (timestamped, reversible)
2. Shows the old claim, the ground-truth finding, and the new memory body
3. Updates MEMORY.md index if the short hook needs rewording

### Stage 6 — Capture Session Intent

See `references/stage6_intent.md`

Ask one question, write intent header to dept Brain.

### Stage 7 — Render HTML

See `references/stage7_html_render.md`

Render the same synthesized brief to HTML in the operator's house theme. Markdown chat brief stays as-is (Reversibility #5 — additive). HTML is the archivable / shareable artifact.

- **Theme:** read `{house_theme_path}` first; drop the `:root` token block into `<style>` verbatim; use `var(--*)` references throughout (no inline hex literals). Default: `{brain_root}/mission-control/audits/theme.md` if no operator override.
- **Output:** `{brain_root}/mission-control/state/briefs/{YYYY-MM-DD}-{dept}-sessionstart.html` (append `-{HHMM}` if multiple on the same date).
- **Same content, different render.** Reproducibility #8 — render-target separation. Synthesis from Stages 1–6 is target-agnostic; markdown and HTML BOTH render from that state. Drift between them is a render-layer bug.
- **Chat delivery:** append a one-line link after the markdown brief.
- **Conditional sections** obey the same hide-when-empty rules as the markdown brief.
- **Trust tags** from Stage 2.5 (✅ / ⚠️ / ❌) render as `badge-green` / `badge-yellow` / `badge-red` pills per the theme spec.

If `house_theme_path` is not configured in the operator profile, skip Stage 7 — markdown brief stands alone.

---

## Key Rules

1. **Verify before surfacing.** Memory + decisions + awareness flags all get a 1-line filesystem spot-check before they hit the brief.

2. **Auto-correct drift by default.** Log the corrections, show them at the top of the brief, offer a rollback command if the operator disagrees.

3. **Shape-aware depth.** Dept-work sessions get a light infra check. Ops/infra sessions get the full machine probe. Don't run the full probe when opening a sales session — it's noise.

4. **Read first, speak second.** Never deliver the brief from memory or the dashboard alone. The dashboard can lag reality.

5. **Open loops are sacred** — if sessionend wrote it under "Open Loops — Next Session," surface it. But verify each one in Stage 2.5 before declaring it still open.

6. **Don't pad.** Empty sections are omitted. Short brief that's accurate beats long brief that's noise.

7. **Cross-dept flags are surgical.** Max 3 bullets, verified-before-surface.

8. **The brief is oriented to action, not history.** Incoming state is 1-2 lines. Open loops + decisions + verified infra state are the main content.

9. **Dept CLAUDE.md is the primary orientation doc.** Workspace-root CLAUDE.md is fallback.

10. **Corrections verify before firing — recursion rule.** A Stage 5 auto-correction is itself a memory claim and gets the same falsification probe its source claim got — applied *before* mutation, before logging, before restatement.

11. **House theme governs HTML render.** Stage 7 HTML render always reads `{house_theme_path}` first as the canonical token block — no inline hex literals, all `var(--*)` references. Same house theme any other operator-facing HTML render uses (audit reports, full-business-audit, command center). Parity #2 — the house style is one of the architectural surfaces skills track.

---

## Scope Contract

| Dimension | Scope |
|-----------|-------|
| Read paths | `{dept}/brain/sessions/` + `decisions/decisions.md` + `pipeline/current-state.md` (per-dept) · `{brain_root}/mission-control/DASHBOARD.md` + `awareness.md` + `sessions/` + `decisions/` + `state/*.json` · workspace-root + dept `CLAUDE.md` · auto-memory layer `MEMORY.md` + referenced memory files · `{house_theme_path}` (Stage 7 render only) |
| Write paths | Session intent header → `{dept}/brain/sessions/YYYY-MM-DD-{slug}-{dept}.md` (Stage 6 only) · `{brain_root}/mission-control/state/memory-corrections.log` (Stage 5 drift correction, append-only) · auto-memory layer `{user,feedback,project,reference}_*.md` updates + `MEMORY.md` index · `{brain_root}/mission-control/state/briefs/{date}-{dept}-sessionstart.html` (Stage 7 HTML render) |
| MCP / tool surface | Read, Bash (filesystem probes + brief loader + dashboard render; optional probes: skill-discoverability-lint, handoff-closure-audit — both skipped silently if not installed), Write/Edit (limited to session intent header + memory-corrections.log + auto-memory layer + briefs dir) |
| Network egress | Local model host probe only (Stage 2.5 infra check; `curl -s {OLLAMA_HOST}/api/tags` with 2s timeout); no external network |
| Surface | Claude Code primary |
| Credentials | None required for reads; no secrets written |
| Escalation trigger | Stage 2.5 probe reports ⚠️ drift on >3 memory claims → pause for explicit operator ack before running Stage 5 auto-corrections; Stage 6 never auto-captures intent — always asks |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[BRAIN_GOVERNANCE]]
- [[DASHBOARD]]
- [[MEMORY]]
- [[NAMING_CONVENTION]]
- [[awareness]]
- [[current-state]]
- [[decisions]]
- [[stage0_turn_start]]
- [[stage1_detect]]
- [[stage25_verify]]
- [[stage2_read]]
- [[stage3_brief]]
- [[stage4_flags]]
- [[stage5_hygiene]]
- [[stage6_intent]]

<!-- AUTOLINK-END -->
