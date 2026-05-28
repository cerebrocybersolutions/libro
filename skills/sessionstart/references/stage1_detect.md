# Stage 1 — Department Detection + Session Shape

## Auto-Detect Department (Try First)

Look at context clues before asking:
- What did the operator say in his opening message? ("Let's work on GovCon" → govcon)
- What file or project is mentioned? (SAM.gov, solicitation → govcon; LinkedIn outreach → cyber or content; council/orchestrator/advisor → ops)
- What skill was last used in this conversation?
- What does the most recent `DASHBOARD.md` session column show?

## Confirm, Don't Ask From Scratch

If you can infer the department with high confidence, confirm rather than ask:

> "Opening **[dept]** — good?"

One word confirms. If he names a different dept, pivot immediately.

## Ask Only If Unclear

If genuinely ambiguous:

> "Which department are we opening? govcon / content / cyber / products / blackbox / training / ops"

Don't offer descriptions. Don't explain what each dept does. the operator knows.

## Multi-Department Sessions

If the operator names two departments:
- Run the full brief for the PRIMARY one
- Flag the secondary: "Want a brief for [dept2] too before we start?"
- Don't try to merge two briefs — it becomes noise

---

## Detect Session Shape (NEW in v2)

After department is locked, classify the session shape. This drives how deep Stage 2.5
runs its infrastructure probes.

**Three shapes:**

| Shape | Signals | Stage 2.5 depth |
|---|---|---|
| `dept-work` | Dept is govcon/content/cyber/products/blackbox/training AND the operator's intent is revenue-side work (draft outreach, ship content, fill tracker, etc.) | LIGHT — skip Ollama/OLW probes, just memory + circuit-breaker spot-check |
| `ops-infra` | Dept is ops OR the operator's intent mentions skills, advisor, council, orchestrator, brain, memory, naming, infrastructure, architecture, olw, wiki | FULL — memory + infra state files + Ollama/OLW/advisor probes |
| `mixed` | Dept is revenue-side BUT intent mentions infra work ("while I'm here let's also...") | FULL for first-pass, then narrow to dept for the brief body |

**Default for ambiguous: `mixed`** — cheap to over-probe, expensive to miss drift.

## Department → Brain Path Mapping (Tier 3 kebab-case)

| Code | Brain Sessions Path | Decisions Path | Pipeline Path |
|---|---|---|---|
| govcon | `govcon/brain/sessions/` | `govcon/brain/decisions/decisions.md` | `govcon/brain/pipeline/current-state.md` |
| content | `content-creation/brain/sessions/` | `content-creation/brain/decisions/decisions.md` | `content-creation/brain/pipeline/current-state.md` |
| cyber | `cyber-services/brain/sessions/` | `cyber-services/brain/decisions/decisions.md` | `cyber-services/brain/pipeline/current-state.md` |
| products | `products/brain/sessions/` | `products/brain/decisions/decisions.md` | `products/brain/pipeline/current-state.md` |
| training | `training/brain/sessions/` | `training/brain/decisions/decisions.md` | N/A |
| ops | `master-brain/sessions/` | `master-brain/decisions/` | N/A |

**Path hygiene:** `brain/` (lowercase) is canonical at every dept as of 2026-04-18 PM (Tier-3 rename closed). If a capital-B `Brain/` appears anywhere, surface it as post-rename drift in Stage 2.5 and normalize.

---

## Department → CLAUDE.md Path Mapping (NEW in v2.1 — Gap 4, 2026-04-18 pattern lock)

Every dept has a front-door CLAUDE.md. Sessionstart reads this FIRST as primary orientation
(new Stage 1.5). Workspace-root CLAUDE.md is fallback only.

| Code | Dept CLAUDE.md Path |
|---|---|
| govcon | `govcon/CLAUDE.md` |
| content | `content-creation/CLAUDE.md` |
| cyber | `cyber-services/CLAUDE.md` |
| products | `products/CLAUDE.md` |
| training | `training/CLAUDE.md` |
| ops | `master-brain/CLAUDE.md` |

**Fallback contract:** if `{dept}/CLAUDE.md` doesn't exist, fall back to workspace-root
`CLAUDE.md` and surface this as a drift finding in Stage 2.5 ("dept CLAUDE.md missing —
scaffold next").

**Dept CLAUDE.md intent:** 60-100 lines, dept-tuned. Mission / Current state / Canonical
files / Dept non-negotiables / Active skills / Escalation rules / Known gotchas / Cross-dept
notes. Overrides workspace-root where they conflict.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[current-state]]
- [[decisions]]

<!-- AUTOLINK-END -->
