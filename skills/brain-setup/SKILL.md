---
name: brain-setup
description: >
  Scaffolds the Brain folder system for a new operator from scratch — prompts
  for your name, company, Brain root path, and departments (or use defaults),
  creates the full Master Brain + dept Brains hierarchy with starter CLAUDE.md
  files and a three-surface-rule primer, seeds DASHBOARD.md + awareness.md,
  and walks you through connecting the sessionstart + sessionend skills.
  Use when: "set up my brain", "build my brain structure", "initialize my brain",
  "brain setup", "create my department brains", "install the brain", "set up
  the brain system", "build out my brain folders", "I want to start using the
  Brain".
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: []
    profile_vars: ["operator_name", "company_name", "workspace_root", "operator_departments"]
---

# Brain Setup

Guided first-time setup that builds the Brain folder system from scratch.
Prompts for operator info and departments, scaffolds the full structure on
disk, seeds a working DASHBOARD.md + awareness.md + workspace CLAUDE.md +
per-dept CLAUDE.md files, and hands off with clear instructions for
connecting the session rituals (sessionstart + sessionend).

**Time to complete:** ~7 minutes.

---

## ⚠️ FIRST-TIME SKILL — No Brain Check

This skill *creates* the Brain. There is nothing to check yet.
Skip any Brain Check. Begin directly with Stage 1.

---

## STAGE ROUTING

| Where the operator is | Stage | Reference file |
|---|---|---|
| Just started — no info collected yet | Stage 1: Intake | `references/stage1_intake.md` |
| Profile confirmed, ready to build folders + docs | Stage 2: Scaffold | `references/stage2_scaffold.md` |
| Folders built, ready to verify + connect session rituals | Stage 3: Connect | `references/stage3_connect.md` |
| Running full setup end-to-end | All stages in sequence | Read all three reference files |

---

## DEFAULT DEPARTMENTS (example pattern)

If the operator has no custom departments in mind, offer these as a starting
point. Folder names are lowercase kebab-case; display names are friendly for docs.

| Code | Folder (kebab-case) | Display name | Purpose |
|---|---|---|---|
| ops | `ops/` | Operations | Company infrastructure, SOPs, skills, dashboards |
| sales | `sales/` | Sales | Pipeline, outreach, proposal tracking |
| delivery | `delivery/` | Delivery | Client work, projects, service execution |
| products | `products/` | Products | Product builds, packaging, pricing |
| content | `content/` | Content | Marketing, social, content ops |

Always ask before applying. Accept any list the operator provides.

Custom departments are welcome — accept any list, auto-convert names to
kebab-case, confirm with operator before building.

---

## WORKSPACE PATHS

All paths are collected from the operator at runtime in Stage 1. Nothing is
hardcoded — this skill works for any operator on any machine.

After Stage 1, the pattern is:

```
{workspace_root}/                          ← top-level project folder
{workspace_root}/CLAUDE.md                 ← workspace-root front door (created in Stage 2)
{workspace_root}/mission-control/             ← Master Brain (Chief of Staff)
{workspace_root}/mission-control/DASHBOARD.md
{workspace_root}/mission-control/awareness.md
{workspace_root}/mission-control/sessions/
{workspace_root}/mission-control/decisions/
{workspace_root}/mission-control/skills/      ← skill source-of-truth layer
{workspace_root}/mission-control/state/       ← live state

{workspace_root}/{dept-folder}/            ← one per department
{workspace_root}/{dept-folder}/CLAUDE.md   ← dept-scoped front door
{workspace_root}/{dept-folder}/brain/
{workspace_root}/{dept-folder}/brain/README.md
{workspace_root}/{dept-folder}/brain/sessions/
{workspace_root}/{dept-folder}/brain/decisions/
{workspace_root}/{dept-folder}/brain/decisions/decisions.md
{workspace_root}/{dept-folder}/brain/pipeline/
```

---

## SURFACE PRIMER (seeded into workspace CLAUDE.md)

The workspace CLAUDE.md seeds this primer so every new session knows where
tasks belong:

- **Claude Code** = on-metal executor. Runs in the operator's terminal with Mac/Linux FS, local models, and git. Surface for drafting, planning, synthesis, file ops, repo work, local model runs, anything that touches process-state on the machine.
- **Operator** = relationship + decision layer. Human judgment, vendor/customer touches, sign-offs.

Routing rule: Everything goes through Claude Code unless the Operator needs to step in for a relationship or hard decision.

---

## KEY RULES

1. **Confirm before building.** Present the full profile and folder plan to the
   operator and wait for a 'yes' before running any commands. A wrong root path
   is painful to undo.

2. **Never overwrite existing content.** Before creating any folder or file, check
   if it exists. If a Brain is partially built, surface what's there and ask how
   to proceed — never silently skip or clobber existing files.

3. **Folders use lowercase kebab-case.** `ops/`, not `Ops/`. `content-creation/`,
   not `ContentCreation/`. Custom dept names get auto-converted.

4. **Scaffold the docs, don't leave them empty.** Every folder the skill creates
   gets a starter doc (CLAUDE.md, README.md, DASHBOARD.md, awareness.md,
   decisions.md). A Brain with empty folders is indistinguishable from a broken Brain.

5. **Stop at instructions for session rituals — do not edit them.** Give the
   operator the Brain root path + explicit what-to-change-where for `sessionend`
   AND `sessionstart`. Don't reach into another skill's files.

6. **Verify before signing off.** After scaffolding, list every folder + file
   that was created and confirm each exists. A setup that silently fails is worse
   than one that errors loudly.

7. **Never seed operator-specific data.** This skill ships to external operators.
   Do not embed any operator-specific identifiers into the scaffolded files.
   The operator supplies their own profile via Stage 1 intake — the skill
   scaffolds the structure, the operator owns the content.

---

## Scope Contract

| Dimension | Scope |
|-----------|-------|
| Read paths | Operator input collected via Stage 1 prompts (name, company, workspace root, department roster) |
| Write paths | New `{workspace_root}/`, `{workspace_root}/mission-control/**`, `{workspace_root}/{dept}/brain/**`, and starter docs — written once during Stage 2 scaffold |
| MCP / tool surface | Python stdlib (`os`, `pathlib`) for folder creation; file I/O for starter docs |
| Network egress | None |
| Surface | Claude Code |
| Credentials | None |
| Escalation trigger | If target root has existing content → **HALT and surface** per Rule 2; require operator confirmation or new path before any write |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[awareness]]
- [[decisions]]
- [[stage1_intake]]
- [[stage2_scaffold]]
- [[stage3_connect]]

<!-- AUTOLINK-END -->
