# Upgrading Libro

## From 0.2.x to 0.3.0-alpha

0.3.0-alpha renames one folder inside four skills. If you installed 0.2.0-alpha or
0.2.1-alpha, run the upgrade below once and you are done.

### What changed on disk

| Skill | 0.2.x path | 0.3.0-alpha path |
|---|---|---|
| `cerebro-doctor` | `.claude/skills/cerebro-doctor/Scripts/` | `.claude/skills/cerebro-doctor/scripts/` |
| `memory-attribution-lint` | `.claude/skills/memory-attribution-lint/Scripts/` | `.claude/skills/memory-attribution-lint/scripts/` |
| `sessionend` | `.claude/skills/sessionend/Scripts/` | `.claude/skills/sessionend/scripts/` |
| `sessionstart` | `.claude/skills/sessionstart/Scripts/` | `.claude/skills/sessionstart/scripts/` |

Only the folder name changes: `Scripts` becomes `scripts`. The three retired skills
(`advisor-mode`, `council-mode`, `orchestrator-mode`) keep `Scripts/` exactly as
before, as promised in their SKILL.md files, so anything you built on them keeps
working.

### How to upgrade

```bash
cd libro                      # your clone of this repository
git pull                      # or: git fetch --tags && git checkout v0.3.0-alpha
./install.sh --target ~/cerebro-brain --dry-run   # optional: see what will change
./install.sh --target ~/cerebro-brain             # upgrade in place
```

Use the `--target` you installed into; `~/cerebro-brain` is the default. You do not
need to pass `--profile`: the installer reads the profile your install recorded in
`.libro-manifest.json` and upgrades that one. Pass `--profile` only to switch or add
a profile.

What the run does:

1. Copies your whole Brain folder to `.libro-backup-<name>-<timestamp>/` beside it
   before it changes anything.
2. Compares each installed skill folder with this release, file by file, using the
   names as they are stored on disk.
3. Replaces any skill folder that differs as a whole. Removing the old folder first
   is what makes the `Scripts` to `scripts` rename land on macOS, whose default
   filesystem ignores case. A plain copy or move over the old folder can leave the
   old name in place there.
4. Leaves every scaffold file you edited (CLAUDE.md files, DASHBOARD.md,
   awareness.md, decisions) untouched.
5. Rewrites `.libro-manifest.json` with the new version, keeping anything an
   earlier install recorded that is still on disk.
6. Runs the health check.

### Check it worked

```bash
python3 ~/cerebro-brain/.claude/skills/cerebro-doctor/scripts/doctor.py
```

You should see `cerebro-doctor: HEALTHY`. If you see
`stale pre-0.3.0 layout: <skill>/Scripts/`, the upgrade did not run against that
install; run `./install.sh --target <that path>` from a 0.3.0-alpha checkout.

The installer's exit status tells you the same thing: 0 means the install record
was written and the health check is HEALTHY. If the run prints INSTALL INCOMPLETE
(exit 3), the skill files are in place but the record could not be written, so
nothing vouches for the install; fix the cause it names (usually permissions on
the target) and run the same command again, or `--rollback`.

### If you call these scripts by path

Update any shell alias, cron line, launchd job, note, or prompt that names one of the
old paths:

| Old | New |
|---|---|
| `.claude/skills/cerebro-doctor/Scripts/doctor.py` | `.claude/skills/cerebro-doctor/scripts/doctor.py` |
| `.claude/skills/cerebro-doctor/Scripts/run_daily.sh` | `.claude/skills/cerebro-doctor/scripts/run_daily.sh` |
| `.claude/skills/memory-attribution-lint/Scripts/lint.py` | `.claude/skills/memory-attribution-lint/scripts/lint.py` |
| `.claude/skills/sessionstart/Scripts/brief_loader.sh` | `.claude/skills/sessionstart/scripts/brief_loader.sh` |

On macOS the old spelling still resolves after the upgrade, because the default
filesystem ignores case. On Linux it does not, so fix the paths there first.

### If you edited files inside a skill folder

The upgrade replaces changed skill folders as a whole. Your edited copy is in the
backup folder from step 1; copy back what you need.

### Rolling back

```bash
./install.sh --rollback --target ~/cerebro-brain
```

This restores the most recent backup, which is the state from just before the
upgrade.

### New in 0.3.0-alpha: the starter profile

The free Operator AI Starter Kit is now part of Libro as the `libro-starter`
profile: libro-core plus three day-one skills (`daily-brief`, `decision`,
`memory-recall`). To add it to an existing install:

```bash
./install.sh --profile libro-starter --target ~/cerebro-brain
```

If you dropped the kit's three files into `.claude/skills/` by hand, this replaces
them with the updated versions; your copies are in the backup.
