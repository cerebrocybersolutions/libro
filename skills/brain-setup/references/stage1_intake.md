# Stage 1 — Intake

## Goal

Collect everything needed to build the Brain before touching the filesystem. Nothing gets created until the operator confirms the full profile.

---

## Questions to Ask (in order, conversationally — one at a time)

### 1. Operator name and company

> "To get started — what's your name and company name? These will personalize your DASHBOARD.md and workspace CLAUDE.md."

### 2. Workspace root path

> "Where do you want this whole project to live? This becomes the workspace folder — your Master Brain will live inside it at `master-brain/`, your departments at `{dept-folder}/`, etc."
>
> Example: `~/Desktop/MyCompany`

Expand `~` via `echo ~` if needed.

*Naming note:* if the operator gives a path with CamelCase or spaces (e.g., `~/Desktop/My Company/`), ask once whether they want to rename to kebab-case. Explain briefly: shell-safe, git-friendly, case-sensitive-surface-safe. Accept their answer either way.

### 3. Departments

> "What departments do you want to set up? I can use these Cerebro-reference defaults, or you can give me your own list:
>
> Defaults (lowercase kebab-case folder names, friendly display names):
> • `govcon/` — GovCon: government contracting
> • `content-creation/` — Content Creation: YouTube, social, content ops
> • `cyber-services/` — Cyber Services: client delivery
> • `products/` — Products: productized offerings + product-line packaging
> • `training/` — Training: class / cohort / external education
>
> Type 'defaults' to use these, or list your own (e.g., 'sales, marketing, operations')."

Rules for parsing the answer:
- If 'defaults' → use all 5 above exactly as listed.
- If custom list → accept any comma-separated list. Auto-convert each name to lowercase kebab-case (e.g., "Sales Team" → `sales-team/`). Confirm the converted names back to the operator before moving on.
- If they want no departments → confirm — a Brain with no departments is valid (pure ops/strategy layer).

### 4. Surface assumption

> "This scaffolds the workspace for use with Claude Code (terminal). Confirm or note any
> additional surfaces (e.g., another planner app, an additional LLM CLI) — the workspace
> CLAUDE.md will seed routing notes for the surfaces in use."

Default: Claude Code + Operator (two-surface). Operators can extend the workspace CLAUDE.md after install.

### 5. Contract governance opt-in

> "Do you want your skills to be contract-governed from day one? This creates a `master-brain/state/` folder for drift trackers and seeds a SKILL_AS_CONTRACT_SOP reference. Optional — you can always add it later."

- Yes → scaffold `master-brain/state/` + stub SOP reference in workspace CLAUDE.md.
- No or unsure → skip; just create the Master Brain base folders.

---

## Pre-Build Confirmation

Before any folder creation, present this summary and wait for 'yes':

```
Here's what I'll build:

Operator:         {name} | {company}
Workspace root:   {expanded_workspace_root}/
Surfaces:         {two-surface or three-surface}
Contract gov.:    {enabled or skipped}

Workspace-root:
  {workspace_root}/CLAUDE.md              ← front door, three-surface primer

Master Brain:
  {workspace_root}/master-brain/
  {workspace_root}/master-brain/DASHBOARD.md
  {workspace_root}/master-brain/awareness.md
  {workspace_root}/master-brain/sessions/
  {workspace_root}/master-brain/decisions/
  {workspace_root}/master-brain/decisions/decisions.md
  {workspace_root}/master-brain/skills/
  [{workspace_root}/master-brain/state/  — if contract gov. enabled]

Department Brains (one per dept):
  {workspace_root}/{dept-folder}/CLAUDE.md          ← dept front door
  {workspace_root}/{dept-folder}/brain/README.md
  {workspace_root}/{dept-folder}/brain/sessions/
  {workspace_root}/{dept-folder}/brain/decisions/
  {workspace_root}/{dept-folder}/brain/decisions/decisions.md
  {workspace_root}/{dept-folder}/brain/pipeline/

Ready to build? (yes / make changes)
```

Only proceed to Stage 2 after receiving 'yes'.

---

## Output of Stage 1

```
operator_name: {name}
company_name: {company}
workspace_root: {absolute path}
departments: [{folder_name: display_name}, ...]
surface_mode: {two_surface | three_surface}
contract_governance: {enabled | skipped}
```

Pass all values directly into Stage 2.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[awareness]]
- [[decisions]]

<!-- AUTOLINK-END -->
