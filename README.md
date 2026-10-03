# Libro 📓

<p align="center">
  <strong>Your Claude workspace, but it remembers everything.</strong>
</p>

<p align="left">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge" alt="License: Apache 2.0"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Version-0.3.0--alpha-orange?style=for-the-badge" alt="Version 0.3.0-alpha"></a>
  <a href="https://claude.ai"><img src="https://img.shields.io/badge/Built_for-Claude-D77757?style=for-the-badge" alt="Built for Claude"></a>
  <a href="https://github.com/cerebrocybersolutions/libro/issues"><img src="https://img.shields.io/badge/Feedback-GitHub_Issues-181717?style=for-the-badge&logo=github" alt="Feedback"></a>
  <a href="#install-in-30-seconds"><img src="https://img.shields.io/badge/Install-30_seconds-3fb950?style=for-the-badge" alt="Install"></a>
  <a href="https://cerebrocybersolutions.com/libro"><img src="https://img.shields.io/badge/Home_%26_Newsletter-cerebrocybersolutions.com-D77757?style=for-the-badge" alt="Libro Home & Newsletter"></a>
</p>

**Libro is a Brain, a skill library, and a tight set of operating conventions you drop into your Claude workspace — and from that day forward, every session opens exactly where the last one closed.** It's not a model. Not an agent host. Not a SaaS. It's the operating layer a small operator pours their work into so the work stops evaporating between conversations.

If you've ever opened a fresh Claude session and spent 10 minutes re-explaining what you're working on, what was decided last week, and which thread you're picking up — **this is what fixes that.**

> **🚧 Alpha (0.3.0).** Seven core skills ship in every profile, and `libro-starter` adds three day-one skills on top. Vertical skill packs land as each one clears the externalization audit. Track progress in [`CHANGELOG.md`](CHANGELOG.md). **Upgrading from 0.2.x?** Read [`UPGRADING.md`](UPGRADING.md): four skills moved their `Scripts/` folder to `scripts/`, and one `./install.sh --target <your brain>` run migrates you.

---

## What Libro actually does

<table>
<tr><td><b>🧠 A Brain that remembers</b></td><td>Pre-scaffolded folder hierarchy — sessions, decisions, dashboard, awareness layers — with <code>(operator: populate)</code> markers so you know exactly where to start. Your decisions compound across sessions instead of evaporating. <b>Open Claude tomorrow and pick up where you left off, byte-for-byte.</b></td></tr>
<tr><td><b>⚡ <code>/sessionstart</code> — zero cold-start</b></td><td>One Bash call surfaces dept CLAUDE.md, latest session, pending decisions, dashboard header, memory index, and an infrastructure snapshot. Stage 2.5 ground-truth verification probes every memory claim against the filesystem before it hits the brief. <b>No more "wait, where were we?"</b></td></tr>
<tr><td><b>🔒 <code>/sessionend</code> — the loop-closer</b></td><td>Structured retro, dashboard update, memory-size probe, and a writeback guard that verifies your session actually closed before you walk away. <b>Nothing gets lost between Friday and Monday.</b></td></tr>
<tr><td><b>🩺 <code>cerebro-doctor</code> — health probe</b></td><td>Verifies skill presence, brain scaffold integrity, host-platform dependencies. Run it any time you suspect drift. Exits HEALTHY or tells you exactly what's broken.</td></tr>
<tr><td><b>🔍 <code>memory-attribution-lint</code></b></td><td>Surfaces orphan and under-tagged memory files. Enforces an 11-key provenance frontmatter contract — every memory has a name, type, source, lifecycle, confidence. <b>Your memory stays auditable as it grows from 50 entries to 5,000.</b></td></tr>
<tr><td><b>🎛️ <code>skill-manage</code></b></td><td>Generic CLI over any skill folder: <code>list</code> / <code>info</code> / <code>enable</code> / <code>disable</code> / <code>validate</code> / <code>audit</code>. Works on Libro skills, your skills, anybody's skills. <b>One CLI to rule them all.</b></td></tr>
<tr><td><b>🌱 Starter skills (<code>libro-starter</code>)</b></td><td><b><code>daily-brief</code></b>: point it at one source and get a short ranked brief.<br><b><code>decision</code></b>: give it a yes/no question and the facts, get a verdict and the reason.<br><b><code>memory-recall</code></b>: ask what you did or decided last week; it reads your Brain and tells you. Free, plain SKILL.md files, no scripts. This profile replaces the separate Operator AI Starter Kit download.</td></tr>
<tr><td><b>🗄️ Retired dispatch skills (<code>libro-full</code>)</b></td><td><code>advisor-mode</code>, <code>council-mode</code>, <code>orchestrator-mode</code>. Retired upstream and kept for reference so existing setups keep working. Their scripts refuse live, billable calls unless you set <code>LIBRO_LEGACY_OPTIN=1</code>. The tier heuristic in their SKILL.md files is the part worth keeping.</td></tr>
<tr><td><b>📊 CEO brief</b></td><td>Cross-department rollup synthesizing latest session state per department. When you wear all the hats and need the one-screen view of the entire business — that screen.</td></tr>
<tr><td><b>🛡️ No telemetry. No phone-home.</b></td><td>Libro never sends usage data anywhere. Your Brain stays on your disk. The maintainer learns nothing about how you use it unless you file an issue.</td></tr>
</table>

---

## Install in 30 seconds

```bash
git clone https://github.com/cerebrocybersolutions/libro.git
cd libro
./install.sh --profile libro-core          # default target: ~/cerebro-brain
```

That's it. You now have a working Brain at `~/cerebro-brain/` with seven skills wired into your Claude workspace.

Other modes:

```bash
./install.sh --profile libro-full --target ~/my-brain   # full alpha surface, custom target
./install.sh --profile libro-core --dry-run             # plan only: no files, no log written
./install.sh --rollback                                  # restore latest backup
./install.sh --profile libro-starter                     # core + three day-one starter skills
./install.sh --target ~/cerebro-brain                    # upgrade an existing install in place
```

**The runner is idempotent and doubles as the upgrader.** Re-running a profile is safe and additive. Your edits to scaffold files are preserved silently. A skill folder that differs from the checkout you run is replaced as a whole, which is how upgrades land (see [`UPGRADING.md`](UPGRADING.md)). Every install against an existing target creates a timestamped backup (`.libro-backup-<ISO8601>/`) before mutating; fresh installs skip the backup because there is nothing to back up. `--rollback` restores from the latest snapshot.

**What the runner writes outside `--target`:** on a real run, exactly two things: the activity log at `~/.cerebro-install.log` and the `.libro-backup-*` folder beside the target. `--dry-run` writes neither; it reads, prints the plan, and deletes the temp files it used. `--doctor` reads the target and appends to the log.

**The exit status is the verdict.** `install.sh` exits 0 only when it wrote the install record (`.libro-manifest.json`) and the post-install health check is HEALTHY. A failed record write exits non-zero and says INSTALL INCOMPLETE; `cerebro-doctor` never reports HEALTHY for a target with a missing, unreadable, or empty record.

### Set up your operator profile (once)

```bash
mkdir -p ~/.cerebro
cp profile.yaml.template ~/.cerebro/profile.yaml
$EDITOR ~/.cerebro/profile.yaml
```

The template documents every key. Dispatch scripts and selected skill prompts read identity (company name, brain root, set-aside type, etc.) from this file at runtime — **no hardcoded operator identity ships in the bundle.** More profile consumers land as deferred skill packs ship.

---

## Protecting your brain repo

Your brain accumulates real notes, decisions, and context. If you put it under git
(recommended), install the pre-commit guard so your own secrets and PII never land in
history:

```bash
# from the root of your brain repo
bash scripts/install-git-hooks.sh
```

This installs a `pre-commit` hook that scans staged changes on every commit and **blocks**
the commit if it finds:

- credentials — API keys (Anthropic / OpenAI / AWS / GitHub / Google / Slack), private-key
  blocks, or generic `SECRET=…` / `TOKEN=…` / `PASSWORD=…` assignments
- credential files — `.env`, `*.pem`, `*.key`, `id_rsa`, `.netrc`, `*credentials*`

It also **warns** (without blocking) on absolute home paths, email addresses, and
private-network IPs.

Example/template files (`*.example`, `*.template`, `*.sample`) and obvious placeholders
(`{{...}}`, `YOUR_KEY`, `CHANGEME`) are ignored. Matched secrets are masked in output.

Run it manually any time:

```bash
bash scripts/pre-commit-lint.sh          # scan staged changes
bash scripts/pre-commit-lint.sh --all    # scan the whole tree
```

Bypass a single commit when you're sure: `LIBRO_SKIP_LINT=1 git commit ...` (or
`git commit --no-verify`). The guard complements `.gitignore` — `.gitignore` keeps named
files out, the guard catches secrets pasted *inside* otherwise-fine files.

---

## Pick your profile

Re-running with a different profile is additive — your scaffold stays put, additional skills land alongside.

See [`SKILL_STATUS.md`](SKILL_STATUS.md) for which shipped skills are stable vs preview.

| Profile | Ships in 0.3.0-alpha | Who it's for |
|---|---|---|
| 🟢 **`libro-core`** | 7 core skills + 9 brain scaffolds | First-timers. Smallest footprint. **Start here.** |
| 🌱 **`libro-starter`** | Core + `daily-brief`, `decision`, `memory-recall` | Anyone running their own AI for the first time who wants three jobs that work on day one. |
| 🏛️ **`libro-govcon`** | Core (vertical skills deferred) | Government-contracting shops with a real solicitation pipeline. |
| 🎬 **`libro-creator`** | Core (vertical skills deferred) | Solo creators on YouTube / LinkedIn / brand content. |
| ⚙️ **`libro-ops`** | Core (vertical skills deferred) | Multi-department operators running a small business across workstreams. |
| 🚀 **`libro-full`** | Core + the three retired dispatch skills (reference only) | Power users who want the full surface, including the retired skills' code to read. |

Profile-specific skills (`govcon-workflow`, `content-pipeline`, `cross-dept-decisions`, `dept-activation`) are listed in each manifest's `_deferred_skills` and land in later releases after externalization review.

---

## Why Libro

There's no shortage of "AI productivity tools." Libro is built on a different premise:

- **The product is the *philosophy*, not the runtime.** Libro encodes a way of operating — three-surface routing, Ops-as-product, infrastructure mode, sessions-as-state. Adopt the philosophy and the skills make sense. Skip it and they feel like overhead.
- **You own the Brain.** Your decisions, sessions, awareness layer all live on your disk under `~/cerebro-brain/` (or wherever you point `--target`). No vendor lock-in. No "your data is in the cloud" risk. Walk away whenever — `./install.sh --rollback` puts everything back.
- **Built for Claude specifically.** Libro is opinionated about which model it speaks to. Claude Code is the executor, Claude conversations are the working surface. Cross-model adaptation is not a goal.
- **Aggressively single-operator.** Libro doesn't try to be a team product. It's built for the operator who runs the whole show and needs the whole show to remember itself.

If you want a multi-tenant SaaS with a slick dashboard — this isn't it. If you want a fast, local, auditable operating layer that compounds your work — read on.

---

## What you need

- **Anthropic Claude.** [Claude Code](https://claude.ai/code) or [claude.ai](https://claude.ai). Bring your own subscription.
- **macOS or Linux.** Tested on macOS; Linux works with minor adjustments. Windows untested (WSL2 should work).
- **Bash 4+ and Python 3.10+.** Standard on modern macOS / Linux.

---

## What's deliberately out of scope

Libro is opinionated about what it is *not*. If any of these matter, you'll want a different tool or you'll add them yourself:

- **Self-serve install.** The runner walks you through it, but the framework is meant to be *read and adopted*, not silently dropped in. The philosophy is half the product.
- **Backend integrations.** No email / calendar / CRM connectors. No local-LLM routing. Libro is the operating layer — bring those separately if you want them.
- **The paid product line.** BlackBox (Cerebro's paid, on-premises, white-glove deployment) is on a separate roadmap. Libro does not unlock or upsell it.
- **Model-routing dispatch.** The three dispatch skills in `libro-full` are retired and refuse live calls unless you opt in. Modern agent harnesses route internally; wire the tier heuristic from their SKILL.md files into the harness you already run.

---

## Known limitations (alpha)

1. **Residual externalization vocabulary.** Some skills carry vocabulary specific to the originating operator's setup (e.g., "Cerebro", "Ops"). Inert at runtime; visible in skill prompts. Tracked for cleanup.
2. **Two skills carry pre-existing parity-flag lint findings.** `dashboard-view` and `sessionend` Step 7.75 carry by-design vendor-internal SOP vocabulary that can't be removed without renaming the skills. Bundle integrity unaffected.
3. **Local-fleet routing assumes you provide your own infrastructure.** Profiles referencing local models (Ollama, LiteLLM proxy) leave installation and configuration to you. The bundle does not install or manage them.
4. **The framework is opinionated.** If your workflow conflicts with three-surface routing / Ops-as-product / infrastructure mode, the friction is intentional. Adapt the conventions, but understand the *why* first.

Maintainer-side externalization lint gates every skill batch before release. The contributor-side pre-commit guard ships in `scripts/` (see Protecting your brain repo).

---

## Used by

Libro's **customer zero is [Cerebro Cyber Solutions](https://cerebrocybersolutions.com/libro)** — the operator that built it. Cerebro runs Libro as its own daily operating layer across a multi-department single-operator business. Every skill in this repo ships only *after* it has earned its place in Cerebro's own real workflow and cleared the externalization audit. Nothing here is theoretical; it's the framework one operator actually runs.

Running Libro and want to be listed here? Open a PR adding yourself to this section — a name, an optional link, and one line on what you use it for. Alpha and proud of it.

---

## Layout

```
libro/
├── README.md                    # this file
├── CHANGELOG.md                 # version-by-version notes
├── UPGRADING.md                 # what to run when moving between versions
├── LICENSE                      # Apache 2.0 license text
├── NOTICE                       # Attribution + trademark notice
├── install.sh                   # two-stage runner (plan + execute, idempotent, rollback-aware)
├── uninstall.sh                 # symmetric uninstall
├── profile.yaml.template        # operator identity template (copy to ~/.cerebro/profile.yaml)
├── profile.schema.json          # JSON schema for manifest profiles
├── fleet-dispatch.template.json
├── manifests/                   # per-profile manifests (libro-core / starter / govcon / creator / ops / full)
├── scaffold/                    # starter-template Brain scaffolds
├── lib/                         # installer / distribution helpers
└── skills/                      # the actual skill folders; each one's scripts live in scripts/ (retired skills keep Scripts/)
```

---

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE) + [`NOTICE`](NOTICE).

Open source. Use, modify, redistribute (commercial or non-commercial) under the Apache 2.0 terms. Patent grant included. Trademark protections preserved per Section 6 — "Libro" and "Cerebro Cyber Solutions" are not granted by this license.

Anthropic Claude is a separate product; Anthropic's [Usage Policy](https://www.anthropic.com/legal/aup) applies to any use of Claude through Libro. Bundled skill packages may include open-source dependencies that retain their original upstream licenses (MIT / Apache-2.0 / other permissive).

---

## Feedback

This is a preview release. File feedback via [GitHub Issues](https://github.com/cerebrocybersolutions/libro/issues). Bug reports welcome. Feature requests welcome — no commitment on roadmap inclusion.

**Built by [Cerebro Cyber Solutions](https://cerebrocybersolutions.com/libro).** Updates, new skill packs as they clear the externalization audit, and the story behind Libro → **[cerebrocybersolutions.com/libro](https://cerebrocybersolutions.com/libro)** (newsletter signup on the page).

---

## Trademark and naming

"Libro" is a Cerebro Cyber Solutions product label. "Cerebro Cyber Solutions" is the company name. Libro is built to work with Claude, an Anthropic product; references to Claude are descriptive use only and imply no partnership or endorsement.
