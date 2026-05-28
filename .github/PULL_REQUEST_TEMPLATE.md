<!--
Thanks for the PR. Please fill out the sections below. Keep the diff minimal — one logical change per PR.

For security issues, do NOT open a PR. See SECURITY.md.
-->

## Summary

<!-- One paragraph: what does this change and why. -->

## Linked issue

Fixes #

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] Feature (non-breaking)
- [ ] Breaking change (requires major-version bump pre-1.0)
- [ ] Docs only
- [ ] Refactor (no behaviour change)
- [ ] Test / CI only

## Surface touched

- [ ] `install.sh` / `uninstall.sh`
- [ ] `manifests/`
- [ ] `skills/` (specify which skill)
- [ ] `scaffold/`
- [ ] `lib/`
- [ ] Docs (`README.md`, `CHANGELOG.md`, `NOTICE`, etc.)
- [ ] CI / `.github/`

## Smoke test

Confirm the install + doctor + uninstall cycle still passes on at least one profile:

```bash
bash install.sh --profile libro-core --target /tmp/libro-pr --yes
/tmp/libro-pr/.claude/skills/cerebro-doctor/Scripts/doctor.py
bash uninstall.sh --target /tmp/libro-pr --yes
```

- [ ] Ran the smoke test locally on at least one profile
- [ ] CI install-smoke workflow passes

## Checklist

- [ ] Diff is minimal and focused on the linked issue
- [ ] No internal vocabulary, operator-specific paths, or contributor PII added
- [ ] CHANGELOG entry added under `## [Unreleased]` (if user-visible)
- [ ] README updated (if behaviour changed)
- [ ] License is Apache 2.0 (no other-licensed code added)
