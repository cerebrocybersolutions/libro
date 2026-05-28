---
name: skill-manage
description: 6-action CLI tool for managing your skill library (create/edit/patch/delete/write-file/remove-file). Use when adding a new skill, patching an existing skill body, deleting a retired skill, or attaching reference/template/script/asset files to a skill folder. Enforces validation (lowercase-hyphen names, frontmatter contract, size caps, path-traversal protection).
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: []
    profile_vars: ["brain_root", "skills_dir"]
---

# skill-manage

CLI utility for managing skills under your skills directory. Single tool, six actions, stdlib only.

## When to use

- Successful approach repeated 5+ times → save as skill
- User-corrected workflow that worked → save as skill
- Non-trivial procedural recipe discovered mid-session → save as skill
- Stale instructions in existing skill → patch
- Pattern absorbed from external source → create

Skip for one-off trivial tasks.

## Actions

| Action | Use | Required args |
|---|---|---|
| create | New skill | `--name --content-file [--category]` |
| edit | Full SKILL.md rewrite | `--name --content-file` |
| patch | Targeted find-and-replace | `--name --old --new [--file-path] [--replace-all]` |
| delete | Remove skill | `--name (--absorbed-into <umbrella> OR --pruned)` |
| write-file | Add reference / template / script / asset | `--name --file-path --file-content-file` |
| remove-file | Remove supporting file | `--name --file-path` |

## Usage

```bash
# Create
python3 {brain_root}/skills/skill-manage/scripts/skill_manage.py create \
  --name my-skill --content-file /tmp/skill-md-content.md [--category devops]

# Patch (fuzzy-free; unique match required unless --replace-all)
python3 {brain_root}/skills/skill-manage/scripts/skill_manage.py patch \
  --name my-skill --old "old text" --new "new text"

# Delete with intent declaration (mandatory)
python3 {brain_root}/skills/skill-manage/scripts/skill_manage.py delete \
  --name my-skill --absorbed-into umbrella-skill
# OR
python3 {brain_root}/skills/skill-manage/scripts/skill_manage.py delete \
  --name my-skill --pruned
```

Output: JSON dict to stdout; exit 0 success / exit 1 error.

## Skills root

Default: `{brain_root}/skills/` (auto-detected via `__file__`).
Override: `SKILLS_DIR=/path/to/skills` env var.

## Validation

- Names: lowercase + hyphens/dots/underscores, ≤64 chars
- Frontmatter: requires `name:` + `description:` (description ≤1024 chars)
- SKILL.md size: ≤100K chars
- Supporting file: ≤1 MiB
- Path traversal blocked (`..` rejected)
- Supporting files must live under: `references/`, `templates/`, `scripts/`, `Scripts/`, `assets/`

## Trigger doctrine (when an agent should call create/patch)

1. **Complex task (5+ tool calls) succeeded** → offer create
2. **User-correction worked** → patch existing skill with the correction
3. **Error overcome with non-obvious fix** → patch skill that owned the workflow
4. **Multi-session pattern emerges** → create
5. **External pattern absorbed** → create (package the port as its own skill)

Skip when: simple one-offs; pure data manipulation; trivial commands.

## Deletion intent declaration

Delete requires explicit intent — `--absorbed-into <name>` or `--pruned`. This forces the
operator to declare why the skill went away, which is recoverable later from git
history. Silent deletes are not supported.

## Scope Contract (Least-Privilege)

| Dimension | Scope |
|---|---|
| Read paths | `{skills_dir}` (default `{brain_root}/skills/`) and any `--content-file` / `--file-content-file` paths |
| Write paths | `{skills_dir}/<skill-name>/**` (SKILL.md + supporting files under whitelist) |
| MCP / tool surface | None — pure Python, stdlib only |
| Network egress | None |
| Surface | Any (CLI invocation) |
| Credentials | None |
| Escalation trigger | Validation failure (exit 1) — operator must fix input and retry |
