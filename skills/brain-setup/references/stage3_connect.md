# Stage 3 — Verify + Connect

## Goal

Verify the scaffold is intact on disk, present the operator with what they now have, and give clear wiring instructions for both session rituals — `/sessionstart` and `/sessionend`. This skill does **not** edit other skills. The operator wires them.

---

## Inputs from Stage 2

- `workspace_root` (absolute path)
- `departments` — `{folder_name, display_name}` list
- `surface_mode`
- `contract_governance`
- `files_created`, `files_skipped`

---

## Step 1 — Structural verification

Walk every folder and file the scaffold was supposed to create. Report each as ✅ present or ❌ missing.

```bash
# Workspace front door
[ -f "{workspace_root}/CLAUDE.md" ] && echo "✅ CLAUDE.md" || echo "❌ CLAUDE.md"

# Master Brain
[ -f "{workspace_root}/master-brain/DASHBOARD.md" ] && echo "✅ DASHBOARD.md" || echo "❌ DASHBOARD.md"
[ -f "{workspace_root}/master-brain/awareness.md" ] && echo "✅ awareness.md" || echo "❌ awareness.md"
[ -f "{workspace_root}/master-brain/decisions/decisions.md" ] && echo "✅ decisions.md" || echo "❌ decisions.md"
[ -d "{workspace_root}/master-brain/sessions" ] && echo "✅ sessions/" || echo "❌ sessions/"
[ -d "{workspace_root}/master-brain/skills" ] && echo "✅ skills/" || echo "❌ skills/"

# Contract governance (if enabled)
# if contract_governance == "enabled":
[ -d "{workspace_root}/master-brain/state" ] && echo "✅ state/" || echo "❌ state/"
[ -f "{workspace_root}/master-brain/SKILL_AS_CONTRACT_SOP.md" ] && echo "✅ SKILL_AS_CONTRACT_SOP.md" || echo "❌ SKILL_AS_CONTRACT_SOP.md"

# For each dept:
# [ -f "{workspace_root}/{folder_name}/CLAUDE.md" ] && echo "✅ {folder_name}/CLAUDE.md" || echo "❌ ..."
# [ -f "{workspace_root}/{folder_name}/brain/README.md" ] && ...
# [ -f "{workspace_root}/{folder_name}/brain/decisions/decisions.md" ] && ...
# [ -d "{workspace_root}/{folder_name}/brain/sessions" ] && ...
# [ -d "{workspace_root}/{folder_name}/brain/pipeline" ] && ...
```

If anything comes back ❌, create the missing piece now (using the templates from Stage 2) before moving on. A partial scaffold breaks session rituals downstream.

---

## Step 2 — Present the built structure

Show the operator a clean tree of what's live:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR BRAIN IS LIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Workspace:  {workspace_root}/

📁 Front door
   {workspace_root}/CLAUDE.md

📁 Master Brain (strategic layer)
   {workspace_root}/master-brain/
   ├── DASHBOARD.md        ← command center
   ├── awareness.md        ← running narrative
   ├── sessions/           ← session logs land here
   ├── decisions/          ← cross-dept decisions
   │   └── decisions.md
   ├── skills/             ← skill source-of-truth
   {IF contract_governance == "enabled":}
   ├── state/              ← live state / drift trackers
   └── SKILL_AS_CONTRACT_SOP.md

📁 Department Brains (execution layer)
{for each dept:}
   {workspace_root}/{folder_name}/
   ├── CLAUDE.md           ← dept front door
   └── brain/
       ├── README.md
       ├── sessions/
       ├── decisions/
       │   └── decisions.md
       └── pipeline/
```

---

## Step 3 — Wire `/sessionstart`

Present this block verbatim. Do **not** try to edit the sessionstart skill yourself — skill-as-contract discipline says you only touch skills you own.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WIRING SESSIONSTART
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

sessionstart loads context at the top of every working session.
Point it at your workspace root.

Your workspace root (copy this):
  {workspace_root}

Steps:
1. Open the sessionstart skill folder in your Claude Code skills location.

2. Open SKILL.md.

3. Find the BRAIN PATHS block (or equivalent — look for hardcoded paths
   pointing at a "master-brain/" or similar Brain root).

4. Replace the Brain root with:
     {workspace_root}/master-brain/

5. Replace the department Brain paths with:
{for each dept:}
     {display_name}: {workspace_root}/{folder_name}/brain/

6. Save. From the next session onward, /sessionstart will load context
   from your Brain.

If sessionstart is already installed but has no BRAIN PATHS block, you
don't need to edit anything — it will auto-discover from the workspace
root via {workspace_root}/CLAUDE.md (the front door we seeded in Stage 2).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 4 — Wire `/sessionend`

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WIRING SESSIONEND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

sessionend writes a session summary at the close of every working
session. It needs to know where your Brain lives.

Your Brain root (copy this):
  {workspace_root}/master-brain/

Steps:
1. Open the sessionend skill folder in your Claude Code skills location.

2. Open SKILL.md.

3. Find the section "BRAIN STRUCTURE — Know Before You Write"
   (or equivalent block that lists paths for sessions/, decisions/,
   DASHBOARD.md, and per-dept brain folders).

4. Update the paths:
     Master Brain:    {workspace_root}/master-brain/
     Sessions:        {workspace_root}/master-brain/sessions/
     Decisions:       {workspace_root}/master-brain/decisions/
     Dashboard:       {workspace_root}/master-brain/DASHBOARD.md
     Awareness:       {workspace_root}/master-brain/awareness.md

5. For each department, update:
{for each dept:}
     {display_name}:  {workspace_root}/{folder_name}/brain/

6. Save. From the next session onward, /sessionend will write to
   your Brain.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 5 — First-session coaching

Hand the operator a tight first-session plan so the Brain starts accumulating state right away:

```
You're ready. Here's how to use this:

1. START: every working session, run /sessionstart first.
   It loads your Brain, surfaces open loops, and gives you a
   department-head brief before work starts.

2. WORK: pick one department to work in. Execution detail lives
   in that department's Brain, not Master Brain. Master Brain stays
   strategic (cross-dept decisions, dashboards, shared skills).

3. END: close with /sessionend. It writes a session summary to the
   right Brain, updates DASHBOARD.md, and flags any open loops for
   the next session.

4. DASHBOARD: open {workspace_root}/master-brain/DASHBOARD.md anytime
   to see the state of the whole operation.

5. AS YOU ADD SKILLS: every new skill should include a Brain Check
   header that reads from {workspace_root}/master-brain/ — that's how
   skills stay aware of company state without you re-briefing them.

{IF contract_governance == "enabled":}
6. CONTRACTS: when a skill becomes load-bearing, bind it to a
   decision doc at master-brain/decisions/ and create a drift tracker
   at master-brain/state/. See SKILL_AS_CONTRACT_SOP.md for the
   four-rule pattern.
```

---

## Step 6 — Close the skill

Final message to the operator:

```
Brain setup complete.

Next step: run your first working session and close it with /sessionend.
After that first /sessionend fires cleanly, your Brain is fully
operational — every future session builds on it.

If anything feels off after the first session, re-run brain-setup in
"verify-only" mode (Stage 3 alone) and it will surface any drift.
```

---

## Output of Stage 3

```
setup_status: live
workspace_root: {workspace_root}
verification: [all ✅ | list of ❌ remediated]
sessionstart_wiring: instructions_delivered
sessionend_wiring: instructions_delivered
first_session_coaching: delivered
```

Skill complete.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[SKILL]]
- [[SKILL_AS_CONTRACT_SOP]]
- [[awareness]]
- [[decisions]]

<!-- AUTOLINK-END -->
