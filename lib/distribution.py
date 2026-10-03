#!/usr/bin/env python3
"""Libro distribution manifest helper.

Cerebro-native re-implementation of the H22 profile-distribution pattern observed
in the hermes-agent pattern-donor. NOT a code copy — this is a clean-room port
targeted at the Libro packaging layer's specific needs:

  - Strict manifest schema validation (closes Phase 5 finding E1 — install.sh
    must hard-fail on a malformed or missing profile manifest, never silently
    proceed with a partial chain).
  - Parent-profile chain resolution with hard errors on missing parent links
    (closes the silent-degrade path inside install.sh's bash _resolve_profile_chain).
  - Installed-manifest writeback to ``.libro-manifest.json`` at the install
    target (closes Phase 5 finding W1 — gives rollback fidelity, idempotency
    state, and an audit trail of what was actually installed).
  - Externalization-aware exclusion enforcement using ``excluded_paths`` from
    the profile manifest (mirrors Hermes USER_OWNED_EXCLUDE — keeps the
    Least-Privilege #7 gate hot at install time, not just at bundle-build time).

stdlib-only by design. The install.sh runner is bash; this module is invoked
as a subprocess from install.sh and returns exit codes + JSON to stdout.

Layering: this lives in the packaging layer, NOT under master-brain/constellation/.
Constellation is the runtime orchestration spine that ships INSIDE Libro.
Libro packaging tooling lives at products/libro-packaging/ and is the wrapper
that produces shippable bundles. Keeping these layers separate is intentional.

Phase 6 owner: CC handoff. Smoke gate: install.sh against fresh sandbox with
libro-core profile must succeed end-to-end with a written .libro-manifest.json
and a non-zero exit on intentional manifest corruption.

References:
  - profile.schema.json (manifest schema)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Schema constants
# --------------------------------------------------------------------------- #

# Required top-level keys in a profile manifest. The schema file at
# products/libro-packaging/profile.schema.json is authoritative; this list
# is the subset the install runner depends on at runtime.
REQUIRED_KEYS = (
    "spec_version",
    "name",
    "version",
    "parent_profile",  # may be None (root profile)
    "additive_modules",
)

# Required sub-keys inside additive_modules. install.sh iterates over
# ``skills`` and ``brain_scaffold``. Missing either is a manifest defect.
REQUIRED_ADDITIVE_KEYS = ("skills", "brain_scaffold")

# Hard cap on parent_profile chain depth. Matches the cap inside install.sh's
# _resolve_profile_chain so behavior is consistent whether the caller hits the
# bash or Python implementation.
MAX_CHAIN_DEPTH = 10


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class ManifestError(Exception):
    """Raised when a profile manifest violates the runtime contract.

    Distinct from generic IOError / JSONDecodeError so install.sh can
    distinguish manifest-level defects (operator-fixable) from filesystem
    or JSON-syntax issues (likely build-bundle defects).
    """


class ChainError(Exception):
    """Raised when a parent_profile chain is unresolvable.

    Examples: missing parent manifest, circular parent reference, depth
    exceeded. Always a hard failure — never silently degrades to a
    partial install.
    """


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LibroManifest:
    """In-memory representation of a profile manifest.

    Construct via :meth:`load` only — direct construction skips validation.
    Frozen so install.sh subprocess calls can safely cache and re-use.
    """

    path: Path
    name: str
    version: str
    parent_profile: Optional[str]
    spec_version: str
    additive_modules: Dict[str, Any]
    raw: Dict[str, Any] = field(repr=False)

    @classmethod
    def load(cls, path: Path) -> "LibroManifest":
        """Load and validate a manifest file.

        Raises ManifestError on any schema violation. Does NOT validate the
        parent_profile chain — that's :func:`resolve_chain`'s job, because
        the chain walk depends on the manifest directory layout.
        """
        if not path.is_file():
            raise ManifestError(f"manifest not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"manifest JSON parse error in {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ManifestError(f"manifest must be a JSON object: {path}")

        missing = [k for k in REQUIRED_KEYS if k not in raw]
        if missing:
            raise ManifestError(
                f"manifest {path} missing required keys: {', '.join(missing)}"
            )

        additive = raw.get("additive_modules")
        if not isinstance(additive, dict):
            raise ManifestError(
                f"manifest {path}: additive_modules must be an object"
            )
        missing_add = [k for k in REQUIRED_ADDITIVE_KEYS if k not in additive]
        if missing_add:
            raise ManifestError(
                f"manifest {path}: additive_modules missing keys: "
                f"{', '.join(missing_add)}"
            )
        for k in REQUIRED_ADDITIVE_KEYS:
            if not isinstance(additive[k], list):
                raise ManifestError(
                    f"manifest {path}: additive_modules.{k} must be an array"
                )

        parent = raw.get("parent_profile")
        if parent is not None and not isinstance(parent, str):
            raise ManifestError(
                f"manifest {path}: parent_profile must be string or null"
            )

        return cls(
            path=path,
            name=str(raw["name"]),
            version=str(raw["version"]),
            parent_profile=parent if isinstance(parent, str) else None,
            spec_version=str(raw["spec_version"]),
            additive_modules=additive,
            raw=raw,
        )

    def skills(self) -> List[str]:
        return list(self.additive_modules.get("skills", []))

    def brain_scaffold(self) -> List[str]:
        return list(self.additive_modules.get("brain_scaffold", []))


# --------------------------------------------------------------------------- #
# Chain resolution
# --------------------------------------------------------------------------- #


def resolve_chain(manifests_dir: Path, profile_name: str) -> List[LibroManifest]:
    """Walk parent_profile chain root-first.

    Returns the chain ordered from root profile to the requested profile,
    so install.sh can apply each profile in order without re-reversing.

    Hard-fails (ChainError) on:
      - the requested profile manifest missing
      - any parent manifest missing
      - circular parent reference
      - chain depth exceeding MAX_CHAIN_DEPTH

    This is the E1 fix: where bash _resolve_profile_chain warns and breaks
    out of the loop (silently producing a partial chain), Python resolve_chain
    raises and propagates the failure to install.sh's exit status.
    """
    if not manifests_dir.is_dir():
        raise ChainError(f"manifests directory not found: {manifests_dir}")

    chain: List[LibroManifest] = []
    seen: List[str] = []
    current: Optional[str] = profile_name

    while current is not None:
        if current in seen:
            cycle = " -> ".join(seen + [current])
            raise ChainError(f"circular parent_profile reference: {cycle}")
        if len(seen) >= MAX_CHAIN_DEPTH:
            raise ChainError(
                f"parent_profile chain depth >= {MAX_CHAIN_DEPTH} at "
                f"{' -> '.join(seen)}"
            )
        manifest_path = manifests_dir / f"{current}.json"
        try:
            manifest = LibroManifest.load(manifest_path)
        except ManifestError as exc:
            raise ChainError(
                f"unresolvable parent_profile chain at '{current}': {exc}"
            ) from exc
        chain.append(manifest)
        seen.append(current)
        current = manifest.parent_profile

    # chain is leaf-first (requested profile -> root); reverse for root-first.
    chain.reverse()
    return chain


# --------------------------------------------------------------------------- #
# Installed-manifest writeback
# --------------------------------------------------------------------------- #


# Files / paths that MUST NEVER appear inside an installed Libro target.
# Defense-in-depth list checked at writeback time.
EXCLUDE_AT_INSTALL_TIME = frozenset(
    {
        "tools",
        "state/fleet-dispatch.json",
    }
)


def write_installed_manifest(
    target_dir: Path,
    chain: List[LibroManifest],
    installed_skills: List[str],
    installed_scaffold: List[str],
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write ``.libro-manifest.json`` to target_dir capturing what was installed.

    Closes Phase 5 finding W1. The file records:
      - the leaf profile name + version + spec_version
      - the full parent_profile chain (root-first)
      - the canonical skill list applied to this target
      - the canonical scaffold list applied to this target
      - install timestamp (UTC, ISO 8601, Z-suffixed)

    Returns the absolute path to the written file. Idempotent: re-running an
    install overwrites this file with the new state. The previous state is
    preserved indirectly via the .libro-backup-* snapshot that install.sh
    creates before mutation.

    Raises OSError if target_dir does not exist or is not writable.
    """
    if not target_dir.is_dir():
        raise OSError(f"install target directory does not exist: {target_dir}")

    leaf = chain[-1]
    record: Dict[str, Any] = {
        "_schema": "libro-installed-manifest/v1",
        "profile": leaf.name,
        "version": leaf.version,
        "spec_version": leaf.spec_version,
        "parent_chain": [m.name for m in chain],
        "installed_skills": sorted(set(installed_skills)),
        "installed_scaffold": sorted(set(installed_scaffold)),
        "install_ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host_os": sys.platform,
    }
    if extra:
        # Allow callers to attach build-bundle SHA, fleet-dispatch hash, etc.
        # Stored under a sub-key so the top-level schema stays predictable.
        record["extra"] = dict(extra)

    present = find_excluded_leaks(target_dir)
    if present:
        # Libro never writes these paths (exclusion_violations() refuses before
        # this function runs), so anything here belongs to the operator. Record
        # it explicitly instead of passing over it in silence.
        record["user_owned_excluded_paths_present"] = present

    # Write to a temp file and rename into place, so a failed write leaves either
    # the previous record or nothing, never a half-written file.
    out_path = target_dir / ".libro-manifest.json"
    tmp_path = target_dir / ".libro-manifest.json.tmp"
    try:
        tmp_path.write_text(
            json.dumps(record, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, out_path)
    finally:
        if tmp_path.exists() and tmp_path.is_file():
            tmp_path.unlink()
    return out_path


def excluded_prefixes(chain: List[LibroManifest]) -> List[str]:
    """Every path Libro must never install: the built-in list plus each
    profile's ``excluded_paths`` (trailing slashes dropped)."""
    out = set(EXCLUDE_AT_INSTALL_TIME)
    for m in chain:
        for p in m.raw.get("excluded_paths", []) or []:
            p = str(p).strip().strip("/")
            if p:
                out.add(p)
    return sorted(out)


def exclusion_violations(
    chain: List[LibroManifest],
    installed_skills: List[str],
    installed_scaffold: List[str],
) -> List[str]:
    """Installed paths that fall on or under an excluded path. Any entry here is
    a packaging defect: the install must be refused, not recorded as healthy."""
    excluded = excluded_prefixes(chain)
    installed = list(installed_scaffold) + [f".claude/skills/{s}" for s in installed_skills]
    bad: List[str] = []
    for rel in sorted(set(installed)):
        norm = rel.strip().strip("/")
        for ex in excluded:
            if norm == ex or norm.startswith(ex + "/"):
                bad.append(f"{rel} (excluded: {ex})")
                break
    return bad


def find_excluded_leaks(target_dir: Path) -> List[str]:
    """Return any EXCLUDE_AT_INSTALL_TIME paths found inside target_dir.

    Returns a list of relative paths (POSIX-form). Empty list = clean. Libro
    never writes these, so a hit means the operator created the path; it is
    recorded in the install record and reported, never treated as a pass or
    silently ignored.
    """
    found: List[str] = []
    if not target_dir.is_dir():
        return found
    for rel in sorted(EXCLUDE_AT_INSTALL_TIME):
        candidate = target_dir / rel
        if candidate.exists():
            found.append(rel)
    return found


# --------------------------------------------------------------------------- #
# Tree comparison (upgrade path)
# --------------------------------------------------------------------------- #


IGNORED_DIRS = frozenset({"__pycache__"})
IGNORED_FILES = frozenset({".DS_Store"})


def tree_fingerprint(root: Path) -> Dict[str, str]:
    """Map every entry under root to a fingerprint, keyed by its STORED relative path.

    os.walk reports names as they are stored on disk, so a folder stored as
    ``Scripts`` and one stored as ``scripts`` produce different keys even on a
    case-insensitive filesystem (default macOS), where opening either name reaches
    the same folder. That is the property the upgrade path needs: a compare that
    opened files by name would call a ``Scripts/`` install identical to a
    ``scripts/`` source and skip the migration.

    Directories fingerprint as ``dir``; files as ``file:<x|->:<sha256>`` where x
    marks the owner-executable bit; symlinks as ``link:<target>``. Runtime
    litter (``__pycache__``, ``*.pyc``, ``.DS_Store``) is ignored, so running a
    skill's scripts does not make an up-to-date install look changed.
    """
    out: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        base = Path(dirpath)
        for d in dirnames:
            full = base / d
            rel = full.relative_to(root).as_posix()
            out[rel] = f"link:{os.readlink(full)}" if full.is_symlink() else "dir"
        for f in sorted(filenames):
            if f in IGNORED_FILES or f.endswith(".pyc"):
                continue
            full = base / f
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                out[rel] = f"link:{os.readlink(full)}"
                continue
            mode = full.stat().st_mode
            digest = hashlib.sha256(full.read_bytes()).hexdigest()
            out[rel] = f"file:{'x' if mode & stat.S_IXUSR else '-'}:{digest}"
    return out


def tree_delta(src: Path, dst: Path) -> List[str]:
    """Human-readable differences between two trees (empty list = identical)."""
    a, b = tree_fingerprint(src), tree_fingerprint(dst)
    lines: List[str] = []
    for rel in sorted(set(a) | set(b)):
        if rel not in b:
            lines.append(f"only in source: {rel}")
        elif rel not in a:
            lines.append(f"only in installed copy: {rel}")
        elif a[rel] != b[rel]:
            lines.append(f"differs: {rel}")
    return lines


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _cmd_validate(args: argparse.Namespace) -> int:
    """Validate a single manifest. Exit 0 = valid, exit 1 = ManifestError."""
    path = Path(args.manifest)
    try:
        m = LibroManifest.load(path)
    except ManifestError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: {m.name} v{m.version} (spec {m.spec_version}, "
        f"parent={m.parent_profile or 'none'}, "
        f"skills={len(m.skills())}, scaffold={len(m.brain_scaffold())})"
    )
    return 0


def _cmd_resolve_chain(args: argparse.Namespace) -> int:
    """Resolve parent_profile chain and emit JSON to stdout.

    Output shape (root-first):
      {
        "chain": [
          {"name": "libro-core", "version": "0.3.0-alpha", "path": "..."},
          ...
        ],
        "skills": ["brain-setup", "sessionstart", ...],
        "brain_scaffold": ["master-brain/CLAUDE.md", ...]
      }

    Skills and scaffold are de-duplicated, install-order-preserved (root first).
    Exit 1 on any ChainError or ManifestError.
    """
    manifests_dir = Path(args.manifests_dir)
    try:
        chain = resolve_chain(manifests_dir, args.profile)
    except (ChainError, ManifestError) as exc:
        print(f"CHAIN ERROR: {exc}", file=sys.stderr)
        return 1

    seen_skills: List[str] = []
    seen_scaffold: List[str] = []
    for m in chain:
        for s in m.skills():
            if s not in seen_skills:
                seen_skills.append(s)
        for s in m.brain_scaffold():
            if s not in seen_scaffold:
                seen_scaffold.append(s)

    out = {
        "chain": [
            {"name": m.name, "version": m.version, "path": str(m.path)}
            for m in chain
        ],
        "skills": seen_skills,
        "brain_scaffold": seen_scaffold,
    }
    print(json.dumps(out, indent=2))
    return 0


def _cmd_writeback(args: argparse.Namespace) -> int:
    """Write .libro-manifest.json to target_dir after a successful install.

    Exit codes: 0 written; 1 chain error or the write failed; 4 an installed
    path falls under an excluded path (nothing is written; install.sh refuses).
    """
    target = Path(args.target)
    manifests_dir = Path(args.manifests_dir)
    try:
        chain = resolve_chain(manifests_dir, args.profile)
    except (ChainError, ManifestError) as exc:
        print(f"CHAIN ERROR: {exc}", file=sys.stderr)
        return 1

    installed_skills = _split_arg_list(args.installed_skills)
    installed_scaffold = _split_arg_list(args.installed_scaffold)

    violations = exclusion_violations(chain, installed_skills, installed_scaffold)
    if violations:
        print(
            f"EXCLUSION VIOLATION: {len(violations)} installed path(s) fall under an excluded path; "
            f"refusing to write an install record: {'; '.join(violations)}",
            file=sys.stderr,
        )
        return 4

    extra: Dict[str, Any] = {}
    if args.bundle_sha:
        extra["bundle_sha"] = args.bundle_sha
    if args.source_root:
        extra["source_root"] = args.source_root

    try:
        out_path = write_installed_manifest(
            target_dir=target,
            chain=chain,
            installed_skills=installed_skills,
            installed_scaffold=installed_scaffold,
            extra=extra or None,
        )
    except OSError as exc:
        print(f"WRITEBACK ERROR: {exc}", file=sys.stderr)
        return 1

    leaks = find_excluded_leaks(target)
    if leaks:
        # Libro did not write these (the violation check above refuses that), so
        # they are operator-owned. Reported on stderr so stdout stays parseable,
        # and recorded in the install record under user_owned_excluded_paths_present.
        print(
            f"NOTE: {len(leaks)} excluded path(s) exist in the target and were left untouched "
            f"(not installed by Libro; recorded in the install record): {', '.join(leaks)}",
            file=sys.stderr,
        )

    print(str(out_path))
    return 0


def verify_install_record(target_dir: Path, manifests_dir: Path) -> List[str]:
    """Check the install record at target_dir. Returns problem lines, each
    prefixed MISSING, BAD, DRIFT or BEHIND; an empty list means the record
    exists, is readable, lists at least one skill, matches what is on disk, and
    records the version this checkout ships for its profile.

    A missing or unreadable record is a problem, never a pass: the record is
    the only proof of what was installed, and the upgrade path reads it.
    """
    path = target_dir / ".libro-manifest.json"
    if not path.exists():
        return ["MISSING install record .libro-manifest.json: nothing proves what was installed; re-run ./install.sh"]
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as exc:
        return [f"BAD install record unreadable ({exc}); re-run ./install.sh"]
    skills = d.get("installed_skills")
    scaffold = d.get("installed_scaffold", [])
    if not isinstance(skills, list) or not skills:
        return ["BAD install record lists no installed skills; re-run ./install.sh"]
    if not isinstance(scaffold, list):
        return ["BAD install record installed_scaffold is not a list; re-run ./install.sh"]
    problems: List[str] = []
    for s in skills:
        if not (target_dir / ".claude" / "skills" / str(s)).is_dir():
            problems.append(f"DRIFT skill '{s}' is in the install record but missing from .claude/skills/")
    for rel in scaffold:
        if not (target_dir / str(rel)).is_file():
            problems.append(f"DRIFT scaffold '{rel}' is in the install record but missing from the target")
    profile, version = str(d.get("profile", "")), str(d.get("version", ""))
    try:
        want = LibroManifest.load(manifests_dir / f"{profile}.json").version
    except ManifestError:
        problems.append(f"BEHIND profile '{profile}' in the install record is not shipped by this checkout")
    else:
        if version != want:
            problems.append(f"BEHIND install record says {profile} {version}; this checkout ships {want}; "
                            f"run ./install.sh --target {target_dir} to upgrade")
    return problems


def _cmd_verify_record(args: argparse.Namespace) -> int:
    """Print one line per install-record problem; exit 0 only if there are none."""
    problems = verify_install_record(Path(args.target), Path(args.manifests_dir))
    for p in problems:
        print(p)
    return 0 if not problems else 1


def _cmd_check_exclusions(args: argparse.Namespace) -> int:
    """Pre-install gate: exit 4 if the resolved profile would install any path on
    or under an excluded path, 1 on a chain error, 0 if clean. install.sh runs
    this before it touches the target, so a bad manifest never half-installs."""
    try:
        chain = resolve_chain(Path(args.manifests_dir), args.profile)
    except (ChainError, ManifestError) as exc:
        print(f"CHAIN ERROR: {exc}", file=sys.stderr)
        return 1
    skills: List[str] = []
    scaffold: List[str] = []
    for m in chain:
        skills += m.skills()
        scaffold += m.brain_scaffold()
    violations = exclusion_violations(chain, skills, scaffold)
    if violations:
        print(
            f"EXCLUSION VIOLATION: profile '{args.profile}' would install {len(violations)} "
            f"excluded path(s): {'; '.join(violations)}",
            file=sys.stderr,
        )
        return 4
    print(f"OK: no profile path falls under {', '.join(excluded_prefixes(chain))}")
    return 0


def _cmd_tree_equal(args: argparse.Namespace) -> int:
    """Exit 0 if the two trees match (stored names, bytes, exec bit), 1 if not.

    With --verbose, prints each difference to stdout. Exit 2 if either path is
    not a directory.
    """
    src, dst = Path(args.src), Path(args.dst)
    if not src.is_dir() or not dst.is_dir():
        print(f"TREE ERROR: not a directory: {src if not src.is_dir() else dst}", file=sys.stderr)
        return 2
    delta = tree_delta(src, dst)
    if args.verbose:
        for line in delta:
            print(line)
    return 0 if not delta else 1


def _split_arg_list(raw: str) -> List[str]:
    """Split a whitespace- or newline-separated bash array string into items."""
    if not raw:
        return []
    items = [s.strip() for s in raw.replace("\n", " ").split() if s.strip()]
    return items


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="libro-distribution",
        description=(
            "Libro packaging distribution helper. Closes Phase 5 findings "
            "E1 (silent-degrade chain) and W1 (no manifest writeback)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp_v = sub.add_parser("validate", help="Validate a single profile manifest")
    sp_v.add_argument("--manifest", required=True, help="Path to manifest JSON")
    sp_v.set_defaults(func=_cmd_validate)

    sp_c = sub.add_parser(
        "resolve-chain",
        help="Resolve parent_profile chain and emit canonical install order",
    )
    sp_c.add_argument("--manifests-dir", required=True)
    sp_c.add_argument("--profile", required=True)
    sp_c.set_defaults(func=_cmd_resolve_chain)

    sp_w = sub.add_parser(
        "writeback",
        help="Write .libro-manifest.json to install target post-install",
    )
    sp_w.add_argument("--target", required=True)
    sp_w.add_argument("--manifests-dir", required=True)
    sp_w.add_argument("--profile", required=True)
    sp_w.add_argument(
        "--installed-skills",
        default="",
        help="Whitespace-separated list of skill names actually installed",
    )
    sp_w.add_argument(
        "--installed-scaffold",
        default="",
        help="Whitespace-separated list of scaffold paths actually installed",
    )
    sp_w.add_argument("--bundle-sha", default=None)
    sp_w.add_argument("--source-root", default=None)
    sp_w.set_defaults(func=_cmd_writeback)

    sp_r = sub.add_parser(
        "verify-record",
        help="Check the target's .libro-manifest.json against disk and this checkout",
    )
    sp_r.add_argument("--target", required=True)
    sp_r.add_argument("--manifests-dir", required=True)
    sp_r.set_defaults(func=_cmd_verify_record)

    sp_x = sub.add_parser(
        "check-exclusions",
        help="Exit 4 if a profile would install a path under an excluded path",
    )
    sp_x.add_argument("--manifests-dir", required=True)
    sp_x.add_argument("--profile", required=True)
    sp_x.set_defaults(func=_cmd_check_exclusions)

    sp_t = sub.add_parser(
        "tree-equal",
        help="Exit 0 if two directory trees match (stored names, bytes, exec bit)",
    )
    sp_t.add_argument("--src", required=True)
    sp_t.add_argument("--dst", required=True)
    sp_t.add_argument("--verbose", action="store_true")
    sp_t.set_defaults(func=_cmd_tree_equal)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
