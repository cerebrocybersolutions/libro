# Stage 2 — Scaffold

## Goal

Create every folder and starter doc on disk using the profile locked in Stage 1. No prompts in this stage — Stage 1 already gathered everything. This is the build phase.

---

## Inputs from Stage 1

- `operator_name`, `company_name`
- `workspace_root` (absolute path, expanded)
- `departments` — list of `{folder_name, display_name}` pairs
- `surface_mode` — `two_surface` or `three_surface`
- `contract_governance` — `enabled` or `skipped`

---

## Step 1 — Existing-content check

Before any writes, probe the target:

```bash
ls "{workspace_root}" 2>/dev/null && echo "EXISTS" || echo "CLEAR"
```

**If CLEAR:** continue to Step 2.

**If EXISTS:** list what's there and ask the operator how to proceed:

> "Found existing content at `{workspace_root}`:
> [list files/folders]
>
> Options:
> (a) build only what's missing — skip anything that already exists
> (b) cancel and pick a different root
>
> Which?"

**Never overwrite.** If a file already exists, skip it and note it in the Stage 2 output. Clobbering existing content is the #1 cause of orphan-state incidents.

---

## Step 2 — Create workspace root + Master Brain

```bash
# Workspace root (in case it doesn't exist)
mkdir -p "{workspace_root}"

# Master Brain folders
mkdir -p "{workspace_root}/master-brain/sessions"
mkdir -p "{workspace_root}/master-brain/decisions"
mkdir -p "{workspace_root}/master-brain/skills"

# Contract-governance state folder (only if enabled)
# if contract_governance == "enabled":
mkdir -p "{workspace_root}/master-brain/state"
```

---

## Step 3 — Seed workspace-root CLAUDE.md

Write to `{workspace_root}/CLAUDE.md`:

```markdown
# {company_name} — Workspace Front Door

*Operator: {operator_name} | Initialized: {today_YYYY-MM-DD}*

This file is the front door for any session that opens at this workspace root. It points at the Brain — it does not replace it.

---

## Orientation (read in order)

1. `master-brain/DASHBOARD.md` — current state of the company
2. `master-brain/awareness.md` — running narrative, last-session summaries
3. Latest file in `master-brain/sessions/` — pick up where the last session left off
4. Relevant department Brain — `{dept-folder}/brain/sessions/` and `{dept-folder}/brain/decisions/decisions.md`

---

## Surfaces

This workspace operates across two surfaces:

- **Claude Code** — on-metal executor (terminal). Mac/Linux FS, local models, git, anything that touches process state, planning, synthesis, reading, drafting, file ops within the workspace.
- **Operator ({operator_name})** — relationship + decision layer. Human judgment, vendor/customer touches, sign-offs.

Routing rule: Everything goes through Claude Code unless the Operator needs to step in for a relationship or hard decision.

---

## Departments

{one bullet per dept:}
- `{folder_name}/` — {display_name}

Each department has its own Brain at `{folder_name}/brain/`. Department execution detail lives there, **not** in Master Brain. Master Brain is strategic only (cross-dept decisions, dashboards, company-wide skills).

---

## Session rituals

- `/sessionstart` at the top of every session — loads context.
- `/sessionend` at the close of every session — logs what happened, updates `DASHBOARD.md` + `awareness.md` + the relevant dept Brain.

Both skills need to know your workspace root. Stage 3 of `brain-setup` walks you through wiring them.

{IF contract_governance == "enabled":}
---

## Skill-as-contract (optional governance layer)

This workspace has contract governance enabled. Skills may be bound to contract decision docs with drift trackers under `master-brain/state/`. See `master-brain/SKILL_AS_CONTRACT_SOP.md` (stub seeded — expand as contracts are added).

---

## Non-negotiables

1. **Naming:** lowercase kebab-case for folders. `govcon/`, not `GovCon/`.
2. **Brain chain-of-command:** department data → dept Brain. Master Brain stays strategic.
3. **Credentials:** never paste API keys, tokens, passwords into files or chat. Env vars or a keychain only.
4. **Confirm before clobbering:** never silently overwrite an existing file.

---

*Updated on /sessionend when material context changes.*
```

Substitute `{...}` tokens before writing. Leave `{IF ...}` blocks inline only for the branches that apply — strip the ones that don't.

---

## Step 4 — Seed Master Brain docs

### `master-brain/DASHBOARD.md`

```markdown
# {company_name} — Master Brain Dashboard

*Operator: {operator_name} | Initialized: {today_YYYY-MM-DD}*
*Updated on every /sessionend — source of truth for company state.*

---

## Commander's Summary

> Nothing logged yet. Run `/sessionend` after your first working session.

---

## Department Status

| Department | Status | Current Focus | Active Deadline | Open Decision | Last Session |
|---|---|---|---|---|---|
{one row per dept:}
| {display_name} | 🟡 | Not started | — | — | — |

*Status key: 🟢 on track | 🟡 in progress / attention needed | 🔴 blocked / urgent*

---

## Active Skills

| Skill | Status | Notes |
|---|---|---|
| `brain-setup` | 🟢 Complete | Brain initialized {today_YYYY-MM-DD} |
| `sessionstart` | 🟡 Needs wiring | See Stage 3 |
| `sessionend` | 🟡 Needs wiring | See Stage 3 |

---

## Red Flags

*None logged yet.*

---

## Notes

*Cross-department notes land here during `/sessionend`.*
```

### `master-brain/awareness.md`

```markdown
# {company_name} — Awareness Layer

*Running narrative. Updated on /sessionend when context shifts materially.*
*Initialized: {today_YYYY-MM-DD}*

---

## Current operating posture

Not established yet. Capture the posture (infrastructure mode / growth mode / harvest mode / triage mode) after the first few working sessions.

---

## Last-session summaries (most recent first)

*Nothing logged yet.*

---

## Active blockers

*None tracked yet.*

---

## Next actions (cross-department)

*None queued yet.*
```

### `master-brain/decisions/decisions.md`

```markdown
# {company_name} — Master Decision Log

*Cross-department decisions land here. Department-local decisions go in the dept's own decision log.*
*Initialized: {today_YYYY-MM-DD}*

---

## Log

| Date | Decision | Why | Owner | Link |
|---|---|---|---|---|
| — | — | — | — | — |

*Add a row on every material cross-department decision. When a decision is load-bearing, also create a dedicated file at `master-brain/decisions/{date}-{topic}.md` and link it here.*
```

{IF contract_governance == "enabled":}

### `master-brain/SKILL_AS_CONTRACT_SOP.md` (stub)

```markdown
# Skill-as-Contract SOP

*Initialized: {today_YYYY-MM-DD} — stub. Expand as contracts are added.*

---

## Intent

A skill becomes a contract when it depends on data or decisions that live outside the skill folder. Each contract-governed skill gets:

1. A decision doc at `master-brain/decisions/{date}-{skill}-contract.md` capturing the rules the skill is bound to.
2. A drift tracker at `master-brain/state/{skill}-contract.md` — the live state that may diverge from the contract.
3. An entry in the contract log below.

---

## Contract log

| Skill | Decision doc | Drift tracker | Last validated |
|---|---|---|---|
| — | — | — | — |
```

---

## Step 5 — Create Department Brains

For each department in `departments`:

```bash
# Dept folder
mkdir -p "{workspace_root}/{folder_name}"

# Dept Brain structure
mkdir -p "{workspace_root}/{folder_name}/brain/sessions"
mkdir -p "{workspace_root}/{folder_name}/brain/decisions"
mkdir -p "{workspace_root}/{folder_name}/brain/pipeline"
```

### Seed `{folder_name}/CLAUDE.md` (dept front door)

```markdown
# {display_name} — Department Front Door

*Department of {company_name}. Operator: {operator_name}.*
*Initialized: {today_YYYY-MM-DD}*

This file is the front door when a session opens scoped to this department. It points at the dept Brain and inherits from the workspace-root `CLAUDE.md`.

---

## Orientation (read in order)

1. `brain/README.md` — what this dept owns, current posture
2. Latest file in `brain/sessions/` — pick up where the last session left off
3. `brain/decisions/decisions.md` — local decision log
4. `brain/pipeline/` — active workflow state (if any)

---

## Scope

*What this department owns and what it does **not** own. Fill in after the first working session.*

---

## Active skills

*Skills scoped to this department. Empty at initialization.*

---

## Non-negotiables

Inherits everything in `{workspace_root}/CLAUDE.md`. Dept-specific rules land here as they're established.
```

### Seed `{folder_name}/brain/README.md`

```markdown
# {display_name} Brain

*Department Brain for {company_name}. Initialized: {today_YYYY-MM-DD}.*

---

## What lives here

- `sessions/` — per-session summaries (filename pattern: `YYYY-MM-DD-{dept-code}.md`)
- `decisions/decisions.md` — local decision log
- `decisions/YYYY-MM-DD-{topic}.md` — dedicated docs for material decisions
- `pipeline/` — active workflow state (current opportunities, in-flight deliverables, etc.)

---

## Chain of command

Department execution detail lives here. **Do not** push dept detail into `master-brain/`. Master Brain is strategic only — cross-dept decisions, company-wide dashboards, shared skills.

---

## Session rituals

- `/sessionstart` loads context from this Brain.
- `/sessionend` writes a new session summary here and updates the dept row in `master-brain/DASHBOARD.md`.
```

### Seed `{folder_name}/brain/decisions/decisions.md`

```markdown
# {display_name} — Decision Log

*Department-local decisions. Cross-department decisions live in `master-brain/decisions/decisions.md`.*
*Initialized: {today_YYYY-MM-DD}*

---

## Log

| Date | Decision | Why | Link |
|---|---|---|---|
| — | — | — | — |
```

---

## Step 6 — Build summary

Report to the operator exactly what was created and what was skipped (due to pre-existing files):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BRAIN SCAFFOLDED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Workspace:   {workspace_root}/
Operator:    {operator_name} | {company_name}

Created:
  {workspace_root}/CLAUDE.md
  {workspace_root}/master-brain/DASHBOARD.md
  {workspace_root}/master-brain/awareness.md
  {workspace_root}/master-brain/sessions/
  {workspace_root}/master-brain/decisions/decisions.md
  {workspace_root}/master-brain/skills/
  [{workspace_root}/master-brain/state/]                  (if contract gov enabled)
  [{workspace_root}/master-brain/SKILL_AS_CONTRACT_SOP.md] (if contract gov enabled)

  Per department:
  {workspace_root}/{folder_name}/CLAUDE.md
  {workspace_root}/{folder_name}/brain/README.md
  {workspace_root}/{folder_name}/brain/sessions/
  {workspace_root}/{folder_name}/brain/decisions/decisions.md
  {workspace_root}/{folder_name}/brain/pipeline/

Skipped (already existed):
  [list any pre-existing files here, or "none"]
```

Then pass control to Stage 3.

---

## Output of Stage 2

```
scaffold_status: complete
workspace_root: {workspace_root}
files_created: [list]
files_skipped: [list or "none"]
```

Stage 3 uses this to verify and wire the session rituals.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[-contract]]
- [[DASHBOARD]]
- [[SKILL_AS_CONTRACT_SOP]]
- [[awareness]]
- [[decisions]]

<!-- AUTOLINK-END -->
