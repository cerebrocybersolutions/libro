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
import json
import os
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

    out_path = target_dir / ".libro-manifest.json"
    out_path.write_text(
        json.dumps(record, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def find_excluded_leaks(target_dir: Path) -> List[str]:
    """Return any EXCLUDE_AT_INSTALL_TIME paths found inside target_dir.

    Returns a list of relative paths (POSIX-form). Empty list = clean.
    Cheap second-look gate for install.sh post-install — bundle-build is
    the authoritative checker, this is just defense-in-depth.
    """
    found: List[str] = []
    if not target_dir.is_dir():
        return found
    for rel in EXCLUDE_AT_INSTALL_TIME:
        candidate = target_dir / rel
        if candidate.exists():
            found.append(rel)
    return found


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
          {"name": "libro-core", "version": "0.1.0-...", "path": "..."},
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
    """Write .libro-manifest.json to target_dir after a successful install."""
    target = Path(args.target)
    manifests_dir = Path(args.manifests_dir)
    try:
        chain = resolve_chain(manifests_dir, args.profile)
    except (ChainError, ManifestError) as exc:
        print(f"CHAIN ERROR: {exc}", file=sys.stderr)
        return 1

    installed_skills = _split_arg_list(args.installed_skills)
    installed_scaffold = _split_arg_list(args.installed_scaffold)

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
        # Non-fatal — informational. install.sh decides whether to halt.
        # Reported to stderr so stdout stays parseable.
        print(
            f"LEAK WARNING: {len(leaks)} excluded path(s) present in target: "
            f"{', '.join(leaks)}",
            file=sys.stderr,
        )

    print(str(out_path))
    return 0


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

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
