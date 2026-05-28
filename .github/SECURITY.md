# Security Policy

## Supported versions

Libro ships pre-1.0 alpha releases. The latest tagged release on `main` is the only supported version; older alphas receive no backports.

| Version       | Supported          |
| ------------- | ------------------ |
| 0.2.x-alpha   | :white_check_mark: |
| < 0.2.0-alpha | :x:                |

## Reporting a security issue

If you believe you have found a security issue in Libro — in the installer (`install.sh` / `uninstall.sh`), any shipped skill, dispatch helper, or scaffold material — please report it privately rather than opening a public GitHub issue.

**Email:** `security@cerebrocybersolutions.com`

If you do not receive an acknowledgement within **5 business days**, please open a minimal GitHub issue titled `Security report awaiting acknowledgement` (no technical detail) so we know to chase the inbox.

### What to include

A useful report contains:

1. The Libro version + commit SHA (`git -C <install> log -1 --format=%H`)
2. The profile installed (`libro-core`, `libro-creator`, `libro-govcon`, `libro-ops`, or `libro-full`)
3. The OS + shell (`uname -a`, `$SHELL --version`)
4. A minimal reproduction (commands, files, observed behaviour)
5. The impact you believe it has

### What happens next

- We will acknowledge within 5 business days.
- We will work with you on a fix and a coordinated disclosure timeline. Default disclosure window is **90 days** from the acknowledgement date; we may request an extension for high-complexity issues.
- We will credit you in the release notes when the fix lands, unless you ask to remain anonymous.

### Out of scope

The following are out of scope for this policy:

- Issues in third-party skills, MCPs, or tools that Libro discovers, references, or composes with — report those to the upstream maintainer.
- Issues in Claude Code itself or the Anthropic API — report to Anthropic.
- Theoretical issues without a working proof of concept against a current release.
- Self-inflicted issues from running Libro with credentials checked into the install target. Libro does not read credential files; see `.claude/skills/*/SKILL.md` for the credential-handling guidance Libro ships.

Thank you for helping keep Libro and its operators safe.
