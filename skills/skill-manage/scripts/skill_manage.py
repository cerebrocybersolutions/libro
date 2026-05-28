#!/usr/bin/env python3
"""
skill_manage — Cerebro-native port of Hermes skill_manager_tool (HM04).

6 actions on Cerebro skills under `master-brain/skills/`:
  create       new skill (SKILL.md + dir)
  edit         full rewrite of SKILL.md
  patch        find-and-replace within SKILL.md or supporting file
  delete       remove skill (with absorbed_into intent)
  write_file   add/overwrite reference / template / script / asset
  remove_file  remove a supporting file

CLI usage:
  python3 skill_manage.py create --name <name> --content-file <path>
  python3 skill_manage.py edit --name <name> --content-file <path>
  python3 skill_manage.py patch --name <name> --old <s> --new <s> [--file-path <p>] [--replace-all]
  python3 skill_manage.py delete --name <name> [--absorbed-into <umbrella>|--pruned]
  python3 skill_manage.py write-file --name <name> --file-path <p> --file-content-file <path>
  python3 skill_manage.py remove-file --name <name> --file-path <p>

Output: JSON dict to stdout; exit 0 on success, 1 on error.

Skills root: master-brain/skills/  (override via CEREBRO_SKILLS_DIR env var)

Deferred from Hermes parent:
  - security scan (no AIDefence integration yet; reverts via git anyway)
  - pinned guard (HM05 pin landed at memory layer not skill layer; pin-at-skill-layer separate decision)
  - curator telemetry / agent-created marking (no Cerebro auto-curator-on-skills yet)
  - fuzzy_match (use exact match; require unique match unless --replace-all)

skill-manage absorption — see operator's decision log for adoption context.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

DEFAULT_SKILLS_DIR = Path(
    os.environ.get("CEREBRO_SKILLS_DIR")
    or (Path(__file__).resolve().parents[3] / "skills")
)
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_CONTENT_CHARS = 100_000
MAX_SKILL_FILE_BYTES = 1_048_576
VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
ALLOWED_SUBDIRS = {"references", "templates", "scripts", "Scripts", "assets"}


# ============================================================
# Validation
# ============================================================

def validate_name(name: str) -> Optional[str]:
    if not name:
        return "Skill name is required."
    if len(name) > MAX_NAME_LENGTH:
        return f"Skill name exceeds {MAX_NAME_LENGTH} characters."
    if not VALID_NAME_RE.match(name):
        return (
            f"Invalid skill name '{name}'. Use lowercase letters, numbers, "
            f"hyphens, dots, underscores. Must start with letter or digit."
        )
    return None


def validate_category(category: Optional[str]) -> Optional[str]:
    if category is None or category == "":
        return None
    if "/" in category or "\\" in category:
        return f"Invalid category '{category}': single segment only."
    if len(category) > MAX_NAME_LENGTH:
        return f"Category exceeds {MAX_NAME_LENGTH} characters."
    if not VALID_NAME_RE.match(category):
        return f"Invalid category '{category}': bad characters."
    return None


def validate_frontmatter(content: str) -> Optional[str]:
    if not content.strip():
        return "Content cannot be empty."
    if not content.startswith("---"):
        return "SKILL.md must start with YAML frontmatter (---)."
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return "SKILL.md frontmatter not closed; needs '---' line."
    yaml_block = content[3 : end_match.start() + 3]

    # Cheap frontmatter parse — name/description required, no PyYAML dep
    fm = {}
    for line in yaml_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    if "name" not in fm:
        return "Frontmatter must include 'name'."
    if "description" not in fm:
        return "Frontmatter must include 'description'."
    if len(fm["description"]) > MAX_DESCRIPTION_LENGTH:
        return f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters."

    body = content[end_match.end() + 3 :].strip()
    if not body:
        return "SKILL.md needs body content after frontmatter."
    return None


def validate_content_size(content: str, label: str = "SKILL.md") -> Optional[str]:
    if len(content) > MAX_SKILL_CONTENT_CHARS:
        return (
            f"{label} content {len(content):,} chars exceeds "
            f"limit {MAX_SKILL_CONTENT_CHARS:,}."
        )
    return None


def validate_file_path(file_path: str) -> Optional[str]:
    if not file_path:
        return "file_path is required."
    parts = Path(file_path).parts
    if not parts:
        return "file_path empty."
    if any(p == ".." for p in parts):
        return "Path traversal ('..') not allowed."
    if parts[0] not in ALLOWED_SUBDIRS:
        return f"File must be under one of: {sorted(ALLOWED_SUBDIRS)}. Got '{file_path}'."
    if len(parts) < 2:
        return f"Provide file path, not just directory. Example: '{parts[0]}/foo.md'"
    return None


# ============================================================
# Helpers
# ============================================================

def skills_root() -> Path:
    return DEFAULT_SKILLS_DIR


def find_skill(name: str) -> Optional[Path]:
    """Return path to skill dir if found (search SKILL.md under root)."""
    root = skills_root()
    if not root.exists():
        return None
    for skill_md in root.rglob("SKILL.md"):
        if skill_md.parent.name == name:
            return skill_md.parent
    return None


def resolve_target(skill_dir: Path, file_path: str) -> Tuple[Optional[Path], Optional[str]]:
    target = (skill_dir / file_path).resolve()
    try:
        target.relative_to(skill_dir.resolve())
    except ValueError:
        return None, "file_path escapes skill directory."
    return target, None


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.tmp.", suffix=""
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ============================================================
# Actions
# ============================================================

def act_create(name: str, content: str, category: Optional[str]) -> dict:
    for check in (validate_name(name), validate_category(category),
                  validate_frontmatter(content), validate_content_size(content)):
        if check:
            return {"success": False, "error": check}
    if find_skill(name):
        return {"success": False, "error": f"Skill '{name}' already exists."}
    skill_dir = skills_root() / (category or "") / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    atomic_write_text(skill_md, content)
    return {
        "success": True,
        "message": f"Skill '{name}' created.",
        "path": str(skill_dir),
    }


def act_edit(name: str, content: str) -> dict:
    err = validate_frontmatter(content) or validate_content_size(content)
    if err:
        return {"success": False, "error": err}
    skill_dir = find_skill(name)
    if not skill_dir:
        return {"success": False, "error": f"Skill '{name}' not found."}
    skill_md = skill_dir / "SKILL.md"
    atomic_write_text(skill_md, content)
    return {
        "success": True,
        "message": f"Skill '{name}' edited (full rewrite).",
        "path": str(skill_dir),
    }


def act_patch(
    name: str,
    old_string: str,
    new_string: str,
    file_path: Optional[str],
    replace_all: bool,
) -> dict:
    if not old_string:
        return {"success": False, "error": "old_string required for patch."}
    if new_string is None:
        return {"success": False, "error": "new_string required for patch (empty string OK)."}
    skill_dir = find_skill(name)
    if not skill_dir:
        return {"success": False, "error": f"Skill '{name}' not found."}

    if file_path:
        err = validate_file_path(file_path)
        if err:
            return {"success": False, "error": err}
        target, err = resolve_target(skill_dir, file_path)
        if err:
            return {"success": False, "error": err}
    else:
        target = skill_dir / "SKILL.md"

    if not target.exists():
        return {"success": False, "error": f"File not found: {target}"}

    content = target.read_text(encoding="utf-8")
    occurrences = content.count(old_string)
    if occurrences == 0:
        return {"success": False, "error": "old_string not found in file."}
    if occurrences > 1 and not replace_all:
        return {
            "success": False,
            "error": f"old_string matches {occurrences} times; pass --replace-all or include more context.",
        }
    new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)

    err = validate_content_size(new_content, label=file_path or "SKILL.md")
    if err:
        return {"success": False, "error": err}
    if not file_path:
        err = validate_frontmatter(new_content)
        if err:
            return {"success": False, "error": f"Patch would break frontmatter: {err}"}

    atomic_write_text(target, new_content)
    return {
        "success": True,
        "message": f"Patched {file_path or 'SKILL.md'} in skill '{name}' ({occurrences if replace_all else 1} replacement(s)).",
    }


def act_delete(name: str, absorbed_into: Optional[str], pruned: bool) -> dict:
    skill_dir = find_skill(name)
    if not skill_dir:
        return {"success": False, "error": f"Skill '{name}' not found."}
    if absorbed_into and pruned:
        return {"success": False, "error": "Pass either --absorbed-into <name> OR --pruned, not both."}
    if not absorbed_into and not pruned:
        return {
            "success": False,
            "error": "Declare intent: --absorbed-into <umbrella> or --pruned. (Curator needs intent to classify consolidation vs pruning.)",
        }
    if absorbed_into:
        if absorbed_into == name:
            return {"success": False, "error": f"absorbed_into cannot equal '{name}'."}
        if not find_skill(absorbed_into):
            return {
                "success": False,
                "error": f"absorbed_into='{absorbed_into}' does not exist. Create/patch umbrella first.",
            }
    shutil.rmtree(skill_dir)
    # cleanup empty category dir
    parent = skill_dir.parent
    if parent != skills_root() and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    msg = f"Skill '{name}' deleted."
    if absorbed_into:
        msg += f" Content absorbed into '{absorbed_into}'."
    return {"success": True, "message": msg}


def act_write_file(name: str, file_path: str, file_content: str) -> dict:
    err = validate_file_path(file_path)
    if err:
        return {"success": False, "error": err}
    if file_content is None:
        return {"success": False, "error": "file_content required."}
    content_bytes = len(file_content.encode("utf-8"))
    if content_bytes > MAX_SKILL_FILE_BYTES:
        return {
            "success": False,
            "error": f"File {content_bytes:,} bytes exceeds {MAX_SKILL_FILE_BYTES:,} (1 MiB).",
        }
    err = validate_content_size(file_content, label=file_path)
    if err:
        return {"success": False, "error": err}
    skill_dir = find_skill(name)
    if not skill_dir:
        return {"success": False, "error": f"Skill '{name}' not found."}
    target, err = resolve_target(skill_dir, file_path)
    if err:
        return {"success": False, "error": err}
    atomic_write_text(target, file_content)
    return {
        "success": True,
        "message": f"File '{file_path}' written to skill '{name}'.",
        "path": str(target),
    }


def act_remove_file(name: str, file_path: str) -> dict:
    err = validate_file_path(file_path)
    if err:
        return {"success": False, "error": err}
    skill_dir = find_skill(name)
    if not skill_dir:
        return {"success": False, "error": f"Skill '{name}' not found."}
    target, err = resolve_target(skill_dir, file_path)
    if err:
        return {"success": False, "error": err}
    if not target.exists():
        return {"success": False, "error": f"File '{file_path}' not found in skill '{name}'."}
    target.unlink()
    parent = target.parent
    if parent != skill_dir and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    return {
        "success": True,
        "message": f"File '{file_path}' removed from skill '{name}'.",
    }


# ============================================================
# CLI
# ============================================================

def _read_content_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(prog="skill_manage")
    sub = ap.add_subparsers(dest="action", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--content-file", required=True, help="Path to file with full SKILL.md content")
    p_create.add_argument("--category", default=None)

    p_edit = sub.add_parser("edit")
    p_edit.add_argument("--name", required=True)
    p_edit.add_argument("--content-file", required=True)

    p_patch = sub.add_parser("patch")
    p_patch.add_argument("--name", required=True)
    p_patch.add_argument("--old", required=True, dest="old_string")
    p_patch.add_argument("--new", required=True, dest="new_string")
    p_patch.add_argument("--file-path", default=None, dest="file_path")
    p_patch.add_argument("--replace-all", action="store_true", dest="replace_all")

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("--name", required=True)
    p_delete.add_argument("--absorbed-into", default=None, dest="absorbed_into")
    p_delete.add_argument("--pruned", action="store_true")

    p_write = sub.add_parser("write-file")
    p_write.add_argument("--name", required=True)
    p_write.add_argument("--file-path", required=True, dest="file_path")
    p_write.add_argument("--file-content-file", required=True, dest="content_file")

    p_remove = sub.add_parser("remove-file")
    p_remove.add_argument("--name", required=True)
    p_remove.add_argument("--file-path", required=True, dest="file_path")

    args = ap.parse_args()

    if args.action == "create":
        result = act_create(args.name, _read_content_file(args.content_file), args.category)
    elif args.action == "edit":
        result = act_edit(args.name, _read_content_file(args.content_file))
    elif args.action == "patch":
        result = act_patch(args.name, args.old_string, args.new_string, args.file_path, args.replace_all)
    elif args.action == "delete":
        result = act_delete(args.name, args.absorbed_into, args.pruned)
    elif args.action == "write-file":
        result = act_write_file(args.name, args.file_path, _read_content_file(args.content_file))
    elif args.action == "remove-file":
        result = act_remove_file(args.name, args.file_path)
    else:
        result = {"success": False, "error": f"Unknown action: {args.action}"}

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
