# Stage 2 — Read Brain + Memory + Infrastructure State

## Reading Order (v2.1 — Gap 4 applied, all in one pass, then compose)

### 0. Dept CLAUDE.md (primary orientation — NEW in v2.1)

Read `{dept}/CLAUDE.md` in full before anything else in this stage. This is the dept's
front-door orientation doc per the 2026-04-18 per-dept CLAUDE.md pattern lock. See
`stage1_detect.md` for the dept → CLAUDE.md path mapping.

**Extract:**
- Mission (1-2 lines)
- Current state (status, top priorities, blockers)
- Canonical files for the dept
- Dept non-negotiables (beyond workspace-root rules)
- Known gotchas + activation triggers (if applicable)

**Fallback:** if `{dept}/CLAUDE.md` doesn't exist, fall back to workspace-root `CLAUDE.md`
and surface this as a Stage 2.5 drift finding ("dept CLAUDE.md missing — scaffold next").
Workspace-root `CLAUDE.md` is reference-only for any dept that has its own CLAUDE.md —
dept overrides root where they conflict.

### 1. Department Brain

Navigate to `[dept]/brain/sessions/` and find the most recent file by date (filename pattern: `YYYY-MM-DD-[dept]*.md`).

**Extract from the most recent session file:**
- `### Open Loops — Next Session` — primary brief items
- `### Decisions Made` — locked decisions for context
- `### Accomplished` — 1-2 lines of incoming state
- `*Intent:*` line at top — what the operator intended last time
- Any `### Cross-department notes` section

**Extract from `[dept]/brain/decisions/decisions.md`:**
- Pending decisions (no resolution marker)
- For each: approximate age by comparing date header to today
- Urgency classification:
  - HIGH: deadline within 14 days, or open 3+ sessions, or blocking revenue
  - MEDIUM: open 1-2 sessions, no hard deadline
  - LOW: open but not blocking active work

**Extract from `[dept]/brain/pipeline/current-state.md`** (if exists):
- 1-2 sentence pipeline position

### 2. Master Brain

- `master-brain/DASHBOARD.md` header — read Commander's Summary for today's date
- `master-brain/awareness.md` — find today's or most-recent dept block
- `master-brain/state/circuit-breakers.json` (if exists) — note any tripped breakers

### 3. Auto-Memory (NEW in v2)

Read the operator's memory index (`MEMORY.md` at the platform-resolved memory mount; do NOT
hardcode a session-id). It's an index, ~200 lines max.

**Extract:**
- Any entry flagged as P1, "next session", or "aging"
- Any entry describing infrastructure state that might have drifted
- Any feedback memory that is relevant to today's session shape (e.g., if session shape
  is `ops-infra` and the dept is picking a new config key, preload `feedback_check_skill_docs_before_config_guess.md`)

**Do NOT** read every memory file body in Stage 2. Just the index. Stage 2.5 reads the
specific memory bodies it needs to verify.

### 3.1 MEMORY.md size probe (NEW 2026-05-17 — HM06 absorption)

After reading the index, run the size probe:

```bash
python3 master-brain/skills/memory-writer/scripts/memory_size_probe.py
```

Caps: 20 KB hard / 16 KB consolidation trigger (80 %). Trust-tag emitted:
- `✅ ok` — under trigger, omit from brief
- `⚠️ consolidation-trigger` — 16 KB+, surface in Stage 3 brief under "⚠️ Memory Hygiene"
- `❌ over-hard-cap` — 20 KB+, surface as P1 in Stage 3 brief; carry to Open Loops if not already

Decision doc: `decisions/2026-05-17-hm06-memory-cap.md`. Override cap values by editing the
constants in the probe — single-source.

### 4. Infrastructure State Files (session shape = `ops-infra` or `mixed`)

- `master-brain/knowledge-vault/wiki.toml` — current olw model config (fast, heavy, auto_commit, etc.)
- `master-brain/state/circuit-breakers.json` (full body, not just presence)
- Check for `master-brain/state/heartbeat.log` or similar if referenced in memory
- Check for OLW activity markers:
  - `master-brain/knowledge-vault/.olw.lock` (if the Karpathy package writes one — verify in its codebase, don't assume)
  - Recent mtime on `master-brain/knowledge-vault/wiki/` indicates compile in flight
  - User context: did the opening message mention OLW running?

### 4.1 Fleet reachability probe (NEW 2026-05-17 — always-on)

Run the fleet probe to surface fleet-node state at session open. Runs on
EVERY session shape (not just ops-infra) — knowing whether each fleet node is reachable
should be the first thing the brief surfaces.

```bash
python3 master-brain/skills/sessionstart/Scripts/fleet_probe.py
```

Output (1-line summary):

```
Fleet: fleet-node-a ✅ green (18ms) · fleet-node-b ✅ green (110ms) · fleet-node-c ✅ local [1.09s]
```

Status semantics:
- `✅ green` — node up + critical services healthy (per operator's fleet topology)
- `⚠️ partial` — node up but at least one critical service down (e.g., hub up but Qdrant container exited)
- `⚠️ ping-only` — ICMP ok but SSH login failed (auth issue / sshd down)
- `❌ unreachable` — ping failed (host off or routing broken)

Surface in **Stage 3 brief — Infrastructure Snapshot** line, regardless of session shape.
For full JSON detail use `--json` flag. Stdlib only, parallel probes, ~1-2s budget.

If any node ⚠️ or ❌ → also add Stage 5 hygiene note if memory said the node was up.

### 5. Rollup Render — Agent Parity with Obsidian DataView (NEW in v2.2.1)

After reading DASHBOARD.md + awareness.md (Steps 2–3), run the agent-side rollup render to catch drift between the static top-matter and the live frontmatter-derived view. This is Parity #2 applied: the DataView blocks in Obsidian and `dashboard_render.py` stdout must surface the same signal.

**When to run:**

- `session_shape = ops-infra` OR `session_shape = mixed` → run `--query all`
- `session_shape = dept-work` → run `--query q1` minimum

**Invocation:**

```bash
python3 master-brain/skills/dashboard-view/dashboard_render.py --query all
```

**Drift watch:** If stderr emits `[DRIFT] N/M session notes missing frontmatter (XX%)`, treat as a Stage 2.5 finding. Do not proceed with session intent until either (a) the gap is <20%, or (b) the operator explicitly acknowledges the drift and allows continuation.

**Parity rule:** If a DataView query in DASHBOARD.md or awareness.md is updated, update the equivalent in `dashboard_render.py` in the same session. Divergence is a drift bug.

## Reading Efficiency

- Read all sources in one parallel Bash/Grep/Read block before composing
- Don't summarize as you go — extract, then compose
- If a session file is very long, focus on the LAST session block only
- If decisions.md has 10+ entries, focus on the ones dated in the last 2 weeks

## File Not Found

If a Brain file is missing:
- Note it in the brief: "No session file found for [dept] — this may be the first session."
- Don't fail — use DASHBOARD.md + awareness.md as fallback
- Flag the missing scaffold as a Stage 2.5 drift finding

## Handoff to Stage 2.5

The output of Stage 2 is a **set of claims** — "these items are P1," "this decision is
open," "this infra state is X." Stage 2.5 takes that set and runs a falsification check
against the filesystem BEFORE the brief renders.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[MEMORY]]
- [[awareness]]
- [[current-state]]
- [[decisions]]
- [[feedback_check_skill_docs_before_config_guess]]
- [[stage1_detect]]

<!-- AUTOLINK-END -->
