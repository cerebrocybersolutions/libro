# Contributing to Libro

Thanks for considering a contribution. Libro is an opinionated Ops scaffold for Claude Code — it ships a small core (seven shipped skills + three dispatch helpers + the install/uninstall surface) and a profile system that wraps them.

This is an alpha (`v0.2.x-alpha`). The API shape, manifest schema, and skill layout may break between minor releases. Please factor that in before investing significant time.

## Before you start

1. **Open an issue first** for anything larger than a typo or a one-line fix. We may already be working on it, or we may have a reason the obvious shape doesn't work.
2. **Read `README.md` and `CHANGELOG.md`** in full. The README documents what each profile ships; the changelog documents what changed and why.
3. **Read the SKILL.md of any skill you're touching.** Skills are self-describing — the SKILL.md is the contract.

## What we welcome

- Bug reports with a minimal reproduction (see `.github/ISSUE_TEMPLATE/bug.yml`)
- Feature requests with a clear use case (see `.github/ISSUE_TEMPLATE/feature.yml`)
- Documentation fixes (typos, broken links, unclear instructions)
- Installer / uninstaller portability fixes (we test on macOS + Linux; Windows is unsupported)
- New skill packs proposed via issue first — we lock the scope before code lands

## What we don't merge

- New skills added without an issue agreeing on scope
- Changes that add Cerebro-internal vocabulary, fleet names, or operator-specific paths back into the public surface (this repo is externalized; the lint that catches that is maintainer-side for now — please grep your patch for the same)
- Changes that bypass `install.sh` checks (writability preflight, profile validation, manifest verification)
- Style-only refactors without a behaviour rationale

## Workflow

1. Fork the repo, branch from `main`.
2. Make your change. Keep the diff minimal — one logical change per PR.
3. Run the smoke install yourself before opening the PR:
   ```bash
   bash install.sh --profile libro-core --target /tmp/libro-pr-test --yes
   /tmp/libro-pr-test/.claude/skills/cerebro-doctor/Scripts/doctor.py
   bash uninstall.sh --target /tmp/libro-pr-test --yes
   ```
4. Open the PR with a clear title and reference the issue it closes (`Fixes #N`).
5. CI runs the install-smoke workflow on PRs touching `install.sh`, `uninstall.sh`, `manifests/`, or `skills/`. PRs must pass CI before review.

## Code style

- Shell: `bash`, `set -uo pipefail` at the top of every script. No `eval`. Quote variables. Prefer `[[ ]]` to `[ ]`.
- Python: 3.10+. No external dependencies in shipped skills (standard library only). Type hints where they help.
- Markdown: GitHub-flavoured. Reference-style links over inline for long URLs.
- Frontmatter: YAML, fields lowercase-snake, values lowercase unless they're proper nouns.

## License

By contributing you agree your contribution is licensed under the **Apache License 2.0** (the same license as the rest of the repo). The `LICENSE` file in this repo is canonical; see `NOTICE` for attribution requirements.

## Code of conduct

Participation in this project is governed by the [Contributor Covenant 2.1](./CODE_OF_CONDUCT.md).

## Security

Found a security issue? **Do not open a public issue.** See [`SECURITY.md`](./SECURITY.md) for the private disclosure path.

## Questions

Open a GitHub Discussion (once enabled) or a low-priority issue tagged `question`. Maintainer response is best-effort — we are a small team.
