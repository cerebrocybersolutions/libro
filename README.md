# Libro 📓

<p align="left">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge" alt="License: Apache 2.0"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-0.2.0--alpha-orange?style=for-the-badge" alt="Version 0.2.0-alpha"></a>
  <a href="https://claude.ai"><img src="https://img.shields.io/badge/Built_for-Claude-D77757?style=for-the-badge" alt="Built for Claude"></a>
  <a href="https://github.com/cerebrocybersolutions/libro/issues"><img src="https://img.shields.io/badge/Feedback-GitHub_Issues-181717?style=for-the-badge&logo=github" alt="Feedback"></a>
</p>

**A Brain, a skill library, and a small set of operating conventions you drop into your Claude workspace — and your sessions start feeling like a coherent system instead of a pile of chats.**

Libro is not a model. Not an agent host. Not a SaaS product. It's the operating layer a small operator pours their work into — sessions, decisions, dashboards, awareness — so the next session opens where the last one closed, every time. Bring your own Claude subscription. Run it locally. No telemetry. No phone-home.

> **Alpha note (0.2.0).** This is the initial public scaffolding under a clone-and-run distribution model. Seven core skills + dispatch trinity (in `libro-full`) ship today. Vertical skill packs land in subsequent 0.2.x commits as each one clears the externalization audit. Track progress in [`CHANGELOG.md`](CHANGELOG.md).

---

## What you get

<table>
<tr><td><b>A Brain that remembers</b></td><td>Pre-scaffolded folder hierarchy — sessions, decisions, dashboard, awareness — with <code>(operator: populate)</code> markers so you know exactly where to start. Your work compounds across sessions instead of evaporating.</td></tr>
<tr><td><b><code>/sessionstart</code> — open grounded</b></td><td>Single-shot Stage 2 brief loader surfaces dept CLAUDE.md, latest session, pending decisions, dashboard header, memory index, and an infrastructure snapshot in one Bash call. Zero cold-start time.</td></tr>
<tr><td><b><code>/sessionend</code> — close clean</b></td><td>Structured retro, dashboard update, memory-size probe, and a writeback guard that verifies your session actually closed before you walk away.</td></tr>
<tr><td><b><code>cerebro-doctor</code> — health probe</b></td><td>Verifies skill presence, brain scaffold integrity, and host-platform dependencies. Run it any time you wonder if something is wired right.</td></tr>
<tr><td><b><code>memory-attribution-lint</code></b></td><td>Surfaces orphan and under-tagged memory files. Enforces an 11-key provenance frontmatter contract so your memory stays auditable as it grows.</td></tr>
<tr><td><b><code>skill-manage</code></b></td><td>Generic CLI over any skill folder: <code>list</code> / <code>info</code> / <code>enable</code> / <code>disable</code> / <code>validate</code> / <code>audit</code>. Works on Libro skills, your own skills, anybody's skills.</td></tr>
<tr><td><b>Dispatch trinity (<code>libro-full</code>)</b></td><td><code>advisor-mode</code> for tiered model routing, <code>council-mode</code> for adversarial parallel comparison, <code>orchestrator-mode</code> for sequential chain plans. Cleared for alpha evaluation in the <code>libro-full</code> profile.</td></tr>
<tr><td><b>CEO brief</b></td><td>Cross-department rollup that synthesizes the latest session state per department. Useful when you wear all the hats and need the one-screen view.</td></tr>
</table>

---

## Quick install

```bash
git clone https://github.com/cerebrocybersolutions/libro.git
cd libro
./install.sh --profile libro-core          # default target: ~/cerebro-brain
```

Other modes:

```bash
./install.sh --profile libro-full --target ~/my-brain   # custom target + full profile
./install.sh --profile libro-core --dry-run             # plan only, no mutations
./install.sh --rollback                                  # restore latest backup
```

The runner is **presence-idempotent** — re-running the same profile is safe and additive. Your edits to scaffold files are preserved silently (content-hash drift detection is queued for a 0.2.x release). Every install against an existing target creates a timestamped backup (`.libro-backup-<ISO8601>/`) before mutating. Fresh installs into a clean target skip the backup step (nothing to back up).

Install activity logs to `~/.cerebro-install.log`. The runner never modifies files outside `--target`.

### Set up your operator profile

Before first use, copy the template and fill in your identity:

```bash
mkdir -p ~/.cerebro
cp profile.yaml.template ~/.cerebro/profile.yaml
$EDITOR ~/.cerebro/profile.yaml
```

The template documents every key. Dispatch scripts and selected skill prompts read identity (company name, brain root, set-aside type, etc.) from this file at runtime — **no hardcoded operator identity ships in the bundle.** More profile consumers land as deferred skill packs ship.

---

## Profiles

Pick one. Re-running with a different profile is additive — your scaffold stays put, additional skills land alongside.

| Profile | Ships in 0.2.0-alpha | Who it's for |
|---|---|---|
| `libro-core` | 7 core skills + 9 brain scaffolds | First-timers. Smallest footprint. Start here. |
| `libro-govcon` | Core only (vertical skills deferred) | Government-contracting shops with a real solicitation pipeline. |
| `libro-creator` | Core only (vertical skills deferred) | Solo creators on YouTube / LinkedIn / brand content. |
| `libro-ops` | Core only (vertical skills deferred) | Multi-department operators running a small business across workstreams. |
| `libro-full` | Core + dispatch trinity (`advisor` / `council` / `orchestrator`) | Power users evaluating the full alpha surface. |

Profile-specific skills (`govcon-workflow`, `content-pipeline`, `cross-dept-decisions`, `dept-activation`) are listed in each manifest's `_deferred_skills` and land in later 0.2.x commits after externalization review.

---

## What you need

- **Anthropic Claude.** Claude Code or claude.ai. Bring your own subscription. Libro is built for Claude — cross-model adaptation is not supported in 0.2.0-alpha.
- **macOS or Linux.** Tested on macOS; Linux works with minor adjustments. Windows is untested (WSL2 should work).
- **Bash 4+ and Python 3.10+.** Standard on modern macOS / Linux.

**No telemetry. Libro does not phone home.** The maintainer receives no usage data unless you explicitly send feedback.

---

## What's deliberately out of scope

Libro is opinionated about what it is *not*. If any of these matter to you, you'll want a different tool or you'll add them yourself:

- **Self-serve install.** The runner walks you through it, but the framework is meant to be *read and adopted*, not silently dropped in. The philosophy is half the product.
- **Backend integrations.** No email / calendar / CRM connectors. No local-LLM routing. Libro is the operating layer; bring those separately if you want them.
- **The paid product line.** BlackBox (Cerebro's paid, on-premises, white-glove deployment) is on a separate roadmap. Libro does not unlock or upsell it.
- **Dispatch modes in every profile.** Ships in `libro-full` only — cleared for alpha evaluation. The four other profiles ship the seven-skill core only. Cerebro itself does not yet dogfood the trinity in daily flow; daily-flow integration lands in V1.1.

---

## Known limitations

1. **Residual externalization vocabulary.** Some skills carry vocabulary specific to the originating operator's setup (e.g., "Cerebro", "Ops"). Inert at runtime; visible in skill prompts. Tracked for cleanup.
2. **Two skills carry pre-existing parity-flag lint findings.** `dashboard-view` and `sessionend` Step 7.75 carry by-design vendor-internal SOP vocabulary that can't be removed without renaming the skills. Bundle integrity unaffected.
3. **Local-fleet routing assumes you provide your own infrastructure.** Profiles referencing local models (Ollama, LiteLLM proxy) leave installation and configuration to you. The bundle does not install or manage them.
4. **The framework is opinionated.** Libro encodes a particular operating philosophy — three-surface routing, Ops-as-product, infrastructure mode. If your workflow conflicts, the friction is intentional. Adapt the conventions, but understand the *why* first.

Maintainer-side externalization lint gates every skill batch before release. A public pre-commit hook is planned for a later 0.2.x commit.

---

## Layout

```
libro/
├── README.md                    # this file
├── CHANGELOG.md                 # version-by-version notes
├── LICENSE                      # Apache 2.0 license text
├── NOTICE                       # Attribution + trademark notice
├── install.sh                   # two-stage install runner (plan + execute, idempotent, rollback-aware)
├── uninstall.sh                 # symmetric uninstall
├── profile.yaml.template        # operator identity template (copy to ~/.cerebro/profile.yaml)
├── profile.schema.json          # JSON schema for manifest profiles
├── fleet-dispatch.template.json
├── manifests/                   # per-profile manifests (libro-core / govcon / creator / ops / full)
├── scaffold/                    # starter-template Brain scaffolds
├── lib/                         # installer / distribution helpers
└── skills/                      # the actual skill folders (populated incrementally in 0.2.x)
```

---

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE) for full text and [`NOTICE`](NOTICE) for attribution + trademark notice.

Libro is open source. Use, modify, redistribute (commercial or non-commercial) under the Apache 2.0 terms. Patent grant included. Trademark protections preserved per Section 6 — "Libro" and "Cerebro Cyber Solutions" are not granted by this license.

Anthropic Claude is a separate product; Anthropic's [Usage Policy](https://www.anthropic.com/legal/aup) applies to any use of Claude through Libro.

Bundled skill packages may include open-source dependencies that retain their original upstream licenses (MIT / Apache-2.0 / other permissive).

---

## Feedback

This is a preview release. File feedback via [GitHub Issues](https://github.com/cerebrocybersolutions/libro/issues). Bug reports welcome. Feature requests welcome — no commitment on roadmap inclusion.

---

## Trademark and naming

"Libro" is a Cerebro Cyber Solutions product label. "Cerebro Cyber Solutions" is the company name. Libro is built to work with Claude, an Anthropic product; references to Claude are descriptive use only and imply no partnership or endorsement.
