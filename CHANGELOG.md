# Changelog

All notable changes to Libro are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.3.0-alpha] - 2026-10-03

A layout change with an upgrade path, plus the free starter kit folded into Libro as a profile. **If you run 0.2.x, read [`UPGRADING.md`](UPGRADING.md) first.** The short version: `./install.sh --target <your brain>` from this release, then `cerebro-doctor` should say HEALTHY.

### Changed (breaking for scripted paths)
- **`Scripts/` is now `scripts/` in the four active skills:** `cerebro-doctor`, `memory-attribution-lint`, `sessionend`, `sessionstart`. Lowercase is the convention for every skill going forward. The doctor now lives at `.claude/skills/cerebro-doctor/scripts/doctor.py`. Anything that calls the old path on Linux needs the new one (macOS ignores case, so the old spelling still resolves there).
- The three retired skills (`advisor-mode`, `council-mode`, `orchestrator-mode`) keep `Scripts/` unchanged, as their SKILL.md files promise.
- Profile manifests are now version `0.3.0-alpha`, so `.libro-manifest.json` in an upgraded install records the new version. Every version string in the repository (README badge, manifests, security policy, contributing guide, issue template, social preview) now says 0.3.0-alpha; 0.2.1-alpha shipped with manifests still reading 0.2.0-alpha.
- **`install.sh` exit status is now the verdict.** 0 only when the install record was written and the post-install health check is HEALTHY; 2 when the health check fails; 3 when the record could not be written (printed as INSTALL INCOMPLETE). Before, both cases exited 0 with a warning.
- **No HEALTHY without an install record.** `install.sh --doctor` now fails on a missing, unreadable, or empty `.libro-manifest.json`, on drift between the record and disk, and on a record whose version is behind the checkout (with the upgrade command in the message). `doctor.py` reports NOT VERIFIED (exit 2 or 3) instead of HEALTHY in the same cases. A record that no longer describes the target after a failed write is moved aside to `.libro-manifest.json.incomplete`, and records are now written atomically.
- **Excluded paths are refused, not just warned about.** A profile that would install a path under an excluded path (`tools/`, `state/fleet-dispatch.json`, or a manifest's `excluded_paths`) is refused before anything is written, and the record writer refuses too (exit 4). An excluded path the operator created is left untouched, reported, and recorded as `user_owned_excluded_paths_present`.
- **`--dry-run` writes nothing,** not even the log line in `~/.cerebro-install.log`; temp files it uses are deleted. The README now states exactly what a real run writes outside `--target`: the log and the backup folder beside the target.

### Added
- **Upgrade path in `install.sh`.** An installed skill folder that differs from the release (compared by the names stored on disk, file bytes, and the executable bit) is replaced as a whole after the usual backup, which makes the case-only rename land on case-insensitive filesystems. Running `./install.sh --target <path>` without `--profile` re-installs the profile the target already records. Earlier install records still on disk are kept in `.libro-manifest.json`, so `uninstall.sh` stays complete. `--dry-run` lists the files that would change per skill.
- **`libro-starter` profile.** libro-core plus three day-one skills that used to ship as the separate Operator AI Starter Kit download: `daily-brief` (ranked brief from one source), `decision` (yes/no verdict with its reason), and `memory-recall` (read-only recap of your Brain). Free, single SKILL.md files, no scripts. `memory-recall` now reads the Brain Libro scaffolds instead of an unspecified memory folder.
- **Stale-layout check in both doctors.** `doctor.py` and `install.sh --doctor` flag a leftover `Scripts/` folder in a migrated skill, reading stored names so the check works where the filesystem ignores case.
- **`tree-equal` in `lib/distribution.py`:** the stored-name tree comparison the installer uses.
- **CI upgrade job:** installs v0.2.1-alpha, upgrades it with the current checkout, and requires a HEALTHY doctor and a tree identical to a fresh install, on Ubuntu and macOS. `libro-starter` joins the install-smoke matrix.
- **`UPGRADING.md`:** the 0.2.x to 0.3.0-alpha migration note.
- **`tests/install-failure-paths.sh`** and a CI job that runs it on Ubuntu and macOS: failed record write, missing record, empty record, record behind the checkout, excluded path in a profile, operator-owned excluded path, dry run side effects, and a stale `Scripts/` layout. Each must refuse or report NOT VERIFIED, never HEALTHY.
- **`lib/distribution.py`** gains `verify-record` and `check-exclusions`, the checks the installer and doctor now call.
- `profile.schema.json` declares `price_tier` and `_deferred_skills`, which every manifest already used, so all six manifests validate against it.

### Fixed
- Re-running `install.sh` over an existing install no longer nests a changed skill inside itself. Before, a skill whose SKILL.md had changed was copied into the existing folder (`<skill>/<skill>/`), so upgrades silently kept the old files.

### Retired (carried from commits after 0.2.1-alpha)
- `advisor-mode`, `council-mode`, `orchestrator-mode` are marked LEGACY in their SKILL.md files. Their scripts, and the dispatch eval harness, refuse live billable calls unless you set `LIBRO_LEGACY_OPTIN=1`; the eval harness defaults to offline mock mode. `SKILL_STATUS.md` now lists them as retired instead of preview.

### Notes
- Still alpha. A fresh-machine audit (clone, install, and use on a clean box) remains the gate for the first stable release.

---

## [0.2.1-alpha] — 2026-06-16

Follow-up batch to the 0.2.0-alpha public launch: community scaffolding, install CI, the public pre-commit guard, the customer-facing skill-status registry, and the first eval suite.

### Added
- **Community + repo hygiene:** `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, issue templates (bug/feature), PR template, social preview image.
- **Install smoke CI:** `.github/workflows/install-smoke.yml` — clone-and-run install path exercised on every push.
- **Public pre-commit guard:** `scripts/install-git-hooks.sh` + `scripts/pre-commit-lint.sh` — externalization lint (operator identifiers, fleet topology, absolute paths) now enforceable contributor-side, as promised in the 0.2.0 "Pending" section.
- **Skill-status registry:** `SKILL_STATUS.md` + `skill-status.json` + `scripts/skill-status.sh` — customer-facing per-skill maturity registry, replacing the internal MODULE_REGISTRY.
- **Evals:** `evals/` — dispatch-classification eval suite (`eval_dispatch.py` + golden cases) for advisor-mode tier routing.
- **cerebro-doctor:** install-diagnostics additions (`doctor.py`).
- **NOTICE:** named TradingAgents (Tauric Research, Apache 2.0) attribution for council-mode / advisor-mode derived files.

### Changed
- **README:** funnel cross-links (landing + newsletter), "Used by" section with Cerebro as customer zero.
- **advisor-mode:** cloud-only docs clarification + path/vocab fixes in dispatch scripts.
- **sessionstart:** brief HTML written via heredoc/`write_text` instead of the Write tool — kills the duplicate preview-panel copy some agent harnesses surface.
- Content-hash drift fix in install path.
- **.gitignore:** ignore agent-runtime local state (`.claude-flow/`, `.swarm/`, `.hive-mind/`) — never ship install-local absolute paths.

### Notes
- Still alpha. Customer-experience audit (clone → install → use on a fresh box) remains the gate for first stable `0.2.0`.

---

## [0.2.0-alpha] — 2026-05-27

**Distribution model change — first public commit.**

### Added
- Clone-and-run distribution. Libro is now a public git repo at `github.com/cerebrocybersolutions/libro`. Clone, run `./install.sh --profile <name>`, done. No tarball, no release artifacts, no checksum dance.
- Baseline scaffolding: `install.sh`, `uninstall.sh`, `lib/`, `manifests/`, `scaffold/`, `profile.schema.json`, `profile.yaml.template`, `fleet-dispatch.template.json`.
- Five profile manifests preserved from 0.1.2 internal build: `libro-core` / `libro-govcon` / `libro-creator` / `libro-ops` / `libro-full`.
- Operator profile contract via `profile.yaml.template` — operator identity (company name, brain root, set-aside, departments) lives in `~/.cerebro/profile.yaml`, never in the repo.

### Changed
- Distribution moved from tarball-per-profile to monorepo clone. Rationale: standard OSS practice, simpler operator install, single source of truth, no per-profile build matrix.
- Versioning bumped from `0.1.2-pre-products-v1` to `0.2.0-alpha` to mark the distribution-model change.

### Removed
- Tarball builder (`build-bundle.sh`) — not needed under clone-and-run.
- Pricing posture file — Libro is free; no public pricing surface ships in the repo.
- Internal module-status registry (`MODULE_REGISTRY.md`) — Phase B will republish a customer-facing registry stripped of internal dev-log vocabulary.

### Pending (0.2.x)
- Skill packs land per-batch in subsequent commits. Each batch passes maintainer-side externalization lint (no operator identifiers, no fleet topology, no workspace-absolute paths). A public pre-commit hook and customer-facing skill-status registry land in later 0.2.x commits.
- Customer-experience audit (clone → install → use on a fresh box) gates the first stable release (`0.2.0`).

---

## Pre-history (internal, not public)

`0.1.x-pre-products-v1` was an internal tarball build matrix under the prior packaging model. Lint reports for those builds were not released. The model change to clone-and-run supersedes that history.
