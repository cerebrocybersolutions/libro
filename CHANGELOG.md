# Changelog

All notable changes to Libro are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

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
