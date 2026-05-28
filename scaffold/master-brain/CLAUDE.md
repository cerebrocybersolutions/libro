# Mission Control — Workspace-Root CLAUDE.md (starter)

*Front door for any session opened at this workspace root. Department-scoped projects override this file with a dept-specific `CLAUDE.md` (see Section 9). This file does not replace your Brain, awareness layer, or auto-memory — it points at them so the session opens with its bearings.*

*Last updated: (operator: populate on first edit).*

---

## 1. Who is operating

(operator: populate — one paragraph. Who is the operator? What is the business they're running? What is their working style — terse vs. verbose, deep vs. broad, infrastructure-first vs. revenue-first? What background should be assumed and what should be over-explained?)

---

## 2. The two-surface rule (Claude Code / Operator)

Route work by capability, not by weight:

- **Claude Code** — the executor. Owns file edits, skill authoring, in-workspace Python, decision docs, session notes, HTML artifact generation, `git`, any local model runtime (Ollama / vLLM / etc.), filesystem operations, credential rotation. If it's runnable, Claude Code does it.
- **Operator (you)** — relationship + decision layer. Customer-facing conversations, sign-offs, hard strategic calls. Anything where the relationship IS the work.

Default rule: relationship-bearing or sign-off-bearing work → operator. Everything else → Claude Code.

(operator: populate — adjust this rule if your surface mix is different)

---

## 3. Operating mode

(operator: populate — one paragraph. What posture is the business in right now? Build-mode, ship-mode, growth-mode, harvest-mode? What does that mean for how work gets routed?)

---

## 4. Orientation reads (in order)

When you open a session, orient in this order:

1. **`mission-control/DASHBOARD.md`** — company state, department status table, open decisions
2. **`mission-control/awareness.md`** — narrative layer, per-dept last-session summaries, active blockers
3. **Latest session file** — `mission-control/sessions/YYYY-MM-DD-*.md`, most recent
4. **Relevant dept Brain** — `{dept}/brain/sessions/` and `{dept}/brain/decisions/decisions.md` for the dept you're in

(operator: populate — add any SOP docs, governance docs, or naming-convention docs that should be in the orientation chain)

---

## 5. Department boundaries

(operator: populate — list your active departments. Each one gets its own folder, its own Brain, its own CLAUDE.md. Example shape:)

```
mission-control/             # ops + chief-of-staff + company-wide skills
products/                    # commercial-product packaging layer
govcon/                      # government contracting
content-creation/            # distribution layer
cyber-services/              # service lines
training/                    # courses + materials
```

**Rule:** do not write department data into `mission-control/`. Mission Control is strategic (decisions, dashboards, company-wide SOPs, shared skills). Department execution detail goes into the department's own Brain folder.

Department Brain structure:
```
{dept}/brain/
  sessions/YYYY-MM-DD-{dept}.md
  decisions/decisions.md
```

---

## 6. Non-negotiables

1. **Credentials.** Never paste API keys, tokens, passwords, or app-specific secrets into any file, commit, or chat paste. Environment variables or OS keychain only. If a credential accidentally appears, rotate immediately.
2. **Naming.** (operator: populate — one rule. Example: "Full kebab-case for all new files and folders.")
3. **File-structure discipline.** Do not create new top-level silos — integrate into existing folders.
4. **Git.** Never force-push the default branch. Commit messages describe what changed and why.
5. (operator: populate — add any other company-wide rules that apply to every session)

---

## 7. Session rituals

This workspace runs `/sessionstart` and `/sessionend` skills that read + write Brain files in a structured format. When working in Claude Code:

- If the operator says "pick up where we left off" or similar, read the latest session file and any unclosed session files
- At the end of a session, either run the sessionend skill or hand the operator a summary they can paste into a sessionend

---

## 8. When in doubt

- **Cite the file, not memory, for mutable state.** If memory says X and the file says Y, the file wins
- **Solve hard problems now, not later.** Don't defer with runbooks when you can push through end-to-end
- (operator: populate — add your own escalation patterns as they accumulate)

---

## 9. Per-department CLAUDE.md

Each dept-scoped project reads its dept `CLAUDE.md` first, and this workspace-root file is the fallback. Dept files are slimmer and tuned to the work that happens there.

Dept CLAUDE.md status:

- `mission-control/CLAUDE.md` — Ops (this file)
- `products/CLAUDE.md` — (operator: populate status)
- `govcon/CLAUDE.md` — (operator: populate status)
- `content-creation/CLAUDE.md` — (operator: populate status)
- `cyber-services/CLAUDE.md` — (operator: populate status)
- `training/CLAUDE.md` — (operator: populate status)

---

*Changes to this file should also update `mission-control/awareness.md` and be logged in `mission-control/decisions/decisions.md`.*

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[awareness]]
- [[decisions]]

<!-- AUTOLINK-END -->
