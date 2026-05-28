# Libro

**A folder structure, a skill library, and a small set of operational conventions you drop into your Claude workspace.**

Libro gives you a starting Brain — sessions, decisions, awareness — plus session rituals, memory hygiene, and a handful of business workflows. It is not a model. It is not an agent host. It is not a SaaS product. It is the operating layer a small operator can pour their own work into and have it become a coherent system.

Version: **0.2.0-alpha** · License: **Apache 2.0** (see [`LICENSE`](LICENSE) + [`NOTICE`](NOTICE)) · Compatible with Anthropic Claude (bring your own subscription).

> **Alpha note (0.2.0).** This is the initial public scaffolding for Libro under a clone-and-run distribution model. The install runner, profile manifests, scaffold templates, operator profile contract, seven core skills, and full-profile dispatch trinity are in place. Remaining vertical skill packs land in subsequent commits as each one clears the externalization audit. Track progress in [`CHANGELOG.md`](CHANGELOG.md).

---

## Install

```bash
# Clone
git clone https://github.com/cerebrocybersolutions/libro.git
cd libro

# Plan + execute (creates ~/cerebro-brain by default)
./install.sh --profile libro-core

# Custom target
./install.sh --profile libro-core --target ~/my-brain

# Dry-run (no mutations)
./install.sh --profile libro-core --dry-run

# Rollback the most recent install
./install.sh --rollback
```

The runner is presence-idempotent: re-running the same profile is safe and additive. The installer skips scaffold files that already exist in your target, so your edits to scaffold files are preserved silently (content-hash drift detection is queued for a 0.2.x release; see `CHANGELOG.md`). Every install **against an existing target** creates a timestamped backup (`.libro-backup-<ISO8601>/`) before mutating; the first install into a fresh target produces no backup because there is nothing to back up. `--rollback` restores from the latest backup snapshot.

Install activity is logged to `~/.cerebro-install.log`. The runner never modifies files outside `--target`.

### Operator profile

Before first use, copy `profile.yaml.template` to `~/.cerebro/profile.yaml` and fill in your operator-specific values:

```bash
mkdir -p ~/.cerebro
cp profile.yaml.template ~/.cerebro/profile.yaml
$EDITOR ~/.cerebro/profile.yaml
```

The template documents every key. Dispatch scripts (`advisor-mode`, `council-mode`, `orchestrator-mode`) and selected skill prompts read identity (company name, brain root, set-aside type, etc.) from this file at runtime — no hardcoded operator identity ships in the bundle. More profile consumers land as deferred skill packs (`ceo-brief` executable surface, `govcon-workflow`, others) ship in later 0.2.x commits.

---

## Profiles

| Profile | What it includes in 0.2.0-alpha | Who it's for |
|---|---|---|
| `libro-core` | 7 core skills (Brain skeleton, sessionstart, sessionend, ceo-brief, cerebro-doctor, memory-attribution-lint, skill-manage) + 9 brain scaffolds | Anyone trying Libro for the first time. Smallest footprint. |
| `libro-govcon` | Core only in 0.2.0-alpha; `govcon-workflow` is deferred | Small government-contracting shops with a real solicitation pipeline. |
| `libro-creator` | Core only in 0.2.0-alpha; creator skills are deferred | Solo creators running YouTube / LinkedIn / brand content. |
| `libro-ops` | Core only in 0.2.0-alpha; ops-power-user skills are deferred | Multi-department operators running a small business across multiple workstreams. |
| `libro-full` | Core + dispatch trinity (`advisor-mode`, `council-mode`, `orchestrator-mode`) | Power users evaluating the full alpha surface currently cleared for release. |

Pick one profile per install. Re-running with a different profile is supported and additive.

---

## What you get out of the box

- **Brain folder hierarchy** — sessions, decisions, dashboard, awareness layers, pre-scaffolded with `(operator: populate)` markers.
- **`/sessionstart`** — opens a session with a grounded department brief. Single-shot Stage 2 orientation: one Bash call surfaces dept CLAUDE.md, latest session, pending decisions, dashboard header, memory index, and an infrastructure snapshot.
- **`/sessionend`** — closes with a structured retro, dashboard update, and a memory-size probe.
- **`memory-attribution-lint`** — surfaces orphan / under-tagged memory files at session-end. Enforces an 11-key provenance frontmatter contract.
- **`skill-manage`** — generic CLI over any skill folder: `list` / `info` / `enable` / `disable` / `validate` / `audit`.
- **CEO brief** — cross-dept rollup synthesizing the latest session state per department.
- **`cerebro-doctor`** — health probe for the installed bundle. Verifies skill presence, brain scaffold integrity, and host-platform plugin dependencies.

Profile-specific skills (`govcon-workflow`, `content-pipeline`, `cross-dept-decisions`, `dept-activation`) are listed in manifest `_deferred_skills` and land in later 0.2.x commits after externalization review.

---

## What's deliberately out of scope

- **Self-serve install.** The runner walks you through it, but the framework is meant to be read and adopted, not silently dropped in.
- **Backend integrations.** Libro is the operating layer. No email connectors, calendar connectors, CRM connectors, or local-LLM routing ships in the bundle. Bring those separately if you want them.
- **The paid product line.** BlackBox (Cerebro's paid, on-premises, white-glove deployment) is on a separate roadmap. Libro does not unlock or upsell it.
- **Dispatch modes (`advisor` / `council` / `orchestrator`).** Ship in the `libro-full` profile only (cleared for alpha evaluation). Not included in `libro-core`, `libro-creator`, `libro-govcon`, or `libro-ops` — those profiles ship the seven-skill core only. Cerebro itself does not yet dogfood the trinity in daily flow; daily-flow integration lands in V1.1.

---

## What you need

- **Anthropic Claude.** Claude Code or claude.ai. Bring your own subscription. Libro is built for Claude — cross-model adaptation is not supported in 0.2.0-alpha.
- **macOS or Linux.** The runner is tested on macOS; Linux works with minor adjustments. Windows is untested.
- **Bash 4+ and Python 3.10+.** Standard on modern macOS / Linux.

No telemetry. Libro does not phone home. The maintainer receives no usage data unless you explicitly send feedback.

---

## Known limitations

1. **Residual externalization vocabulary.** Some skills still carry vocabulary specific to the originating operator's setup (e.g., "Cerebro", "Ops"). Inert at runtime; visible in skill prompts. Tracked for cleanup in a future release.
2. **Two skills carry pre-existing parity-flag lint findings.** `dashboard-view` and `sessionend` Step 7.75 carry by-design vendor-internal SOP vocabulary that cannot be removed without renaming the skills. They do not affect bundle integrity.
3. **Local-fleet routing assumes you provide your own infrastructure.** Profiles that reference local models (Ollama, LiteLLM proxy) leave installation and configuration to you. The bundle does not install or manage them.
4. **The framework is opinionated.** Libro encodes a particular operating philosophy (three-surface routing, Ops-as-product, infrastructure mode). If your workflow conflicts, the friction is intentional — adapt the conventions, but understand the why first.

Maintainer-side externalization lint gates every skill batch before release. A public pre-commit hook is planned for a later 0.2.x commit.

---

## Layout

```
libro/
├── README.md                # this file
├── CHANGELOG.md             # version-by-version notes
├── LICENSE                  # Apache 2.0 license text
├── NOTICE                   # Attribution + trademark notice
├── install.sh               # two-stage install runner (plan + execute, idempotent, rollback-aware)
├── uninstall.sh             # symmetric uninstall
├── profile.yaml.template    # operator identity template (copy to ~/.cerebro/profile.yaml)
├── profile.schema.json      # JSON schema for manifest profiles
├── fleet-dispatch.template.json
├── manifests/               # per-profile manifests (libro-core / libro-govcon / libro-creator / libro-ops / libro-full)
├── scaffold/                # starter-template Brain scaffolds
├── lib/                     # installer / distribution helper
└── skills/                  # the actual skill folders (populated incrementally in 0.2.x)
```

---

## Release notes

See [`CHANGELOG.md`](CHANGELOG.md) for version-by-version notes. GitHub Releases tags major milestones.

---

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE) for full text and [`NOTICE`](NOTICE) for attribution + trademark notice.

Libro is open source. You can use, modify, and redistribute it (commercial or non-commercial) under the Apache 2.0 terms. Patent grant included. Trademark protections preserved per Section 6 ("Libro" and "Cerebro Cyber Solutions" are not granted by this license).

Anthropic Claude is a separate product; Anthropic's [Usage Policy](https://www.anthropic.com/legal/aup) applies to any use of Claude through Libro.

Bundled skill packages may include open-source dependencies that retain their original upstream licenses (MIT / Apache-2.0 / other permissive).

---

## Feedback

This is a preview release. File feedback via GitHub Issues on this repo. Bug reports welcome; feature requests welcome but no commitment on roadmap inclusion.

---

## Trademark and naming

"Libro" is a Cerebro Cyber Solutions product label. "Cerebro Cyber Solutions" is the company name. Libro is built to work with Claude, an Anthropic product; references to Claude are descriptive use only and imply no partnership or endorsement.
