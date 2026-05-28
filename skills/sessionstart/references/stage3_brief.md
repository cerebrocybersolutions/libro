# Stage 3 — Department Head Brief

## The Mental Model

You are the department head briefing the operator before he walks into the room. You've managed
this department between sessions. You know everything. the operator just arrived. Give him the
fastest possible accurate picture — what happened, what's waiting, what needs a decision,
AND what the machine is doing — so he can start working in under 60 seconds.

## Output Template

```
🟢 [Department Name] — Session Brief | [YYYY-MM-DD]

## Memory Drift (auto-corrected)                    ← only if Stage 2.5 found any
- ⚠️ [memory-file-name]: [old claim] → [new state]. Corrected in memory.

## ⚠️ Unclosed Session (NEW v2.1 — Gap 1)           ← only if Stage 2.5 closure-check flagged UNCLOSED
Last session file `[filename]` is missing closure markers ([count]/3 present).
State is ambiguous — do NOT auto-roll forward. Stage 6 will ask:
  (a) Retroactive-close last session with what you remember ending on
  (b) Adopt its WIP as today's intent and keep going
  (c) Start fresh — archive the hanging file untouched

## Infrastructure Snapshot
- Fleet: fleet-node-a [✅/⚠️/❌] · fleet-node-b [✅/⚠️/❌] · fleet-node-c [✅/⚠️/❌]   ← ALWAYS surface (Stage 2 §4.1 fleet_probe)
- [Additional 1-3 lines: Ollama, OLW, advisor, circuit breakers — only for ops-infra / mixed sessions]

## Incoming State
[1-2 sentences. Concrete outputs from last session — not effort, not planning, actual things that exist now.]

## Open Loops
- [ ] [Verbatim from last session's Open Loops, filtered by Stage 2.5 verification]
- [ ] [...]
[If none remaining after verification: omit section]

## Pending Decisions
- ⚡ [Decision title] — open [X days / X sessions] — HIGH
- [Decision title] — open [X days] — MEDIUM
[Sort HIGH first. Verified-open only. If none: omit section.]

## Pipeline Position
[1 sentence. Where pipeline stands right now. What's active, next, blocked.]
[Omit if no pipeline for this dept.]

## ⚠️ Cross-Dept Flags                              ← Stage 4 output, only if flags qualify
- [Dept]: [1-line flag]
```

## Section Guidance

### Memory Drift (NEW in v2)

Surface AT TOP so the operator sees it before the brief body.
Default is auto-corrected — the old claim was wrong, the new claim is in memory, corrections
logged to `master-brain/state/memory-corrections.log`. Offer one-line rollback if he disagrees.
Keep each correction to 1 line — details are in the log.

### Unclosed Session (NEW in v2.1 — Gap 1)

Surface IMMEDIATELY AFTER Memory Drift, BEFORE Infrastructure Snapshot. The reason: if the
last session wasn't closed, the entire "Incoming State" below is unreliable — the operator needs
to see that caveat before reading anything downstream.

- Reference the filename explicitly (e.g., `2026-04-17-ops.md`)
- State how many of the 3 closure markers were present (0, 1, or 2)
- Do NOT render Incoming State, Open Loops, or Pending Decisions from that file — those
  sections are held pending the operator's Stage 6 answer
- List the three options (a)/(b)/(c) inline so the operator can answer without paging back

### Infrastructure Snapshot (NEW in v2)

Only appears for session shape = `ops-infra` or `mixed`. Format example:

```
## Infrastructure Snapshot
- Ollama: running, qwen2.5:14b + gemma4:e4b loaded
- OLW: active run in progress (started HH:MM, ~N files processed)
- Advisor stack: portable ✅ | Circuit breakers: 0 tripped | Heartbeat: wired (council + orchestrator)
- Known drift: none (Tier 3 rename closed 2026-04-18 PM — all 6 depts on `brain/`)
```

Each line is ONE concise fact. If something is unverified, say so: `Ollama: unverified (probe timeout)`.

### Incoming State

ONE look backward — what did last session accomplish? 1-2 sentences max.
Example: "Last session: govcon-vendor-quoting skill built. 3 vendor drafts staged."
If nothing concrete: "Last session was planning/research — no deliverables."

### Open Loops

Copy from last session file's `Open Loops — Next Session` section, **filtered by Stage 2.5
verification**. Items that Stage 2.5 marked ❌ resolved are dropped (with correction noted
in the Memory Drift block). Items marked ⚠️ drift get updated wording. ✅ confirmed items
pass through verbatim.

Checkboxes `[ ]` make them actionable.

### Pending Decisions

Verified-open only. Age by comparing decisions.md date header to today.
Be specific about urgency — don't mark everything HIGH. Examples:
- ⚡ "Go/No-Go on SAMPLE-2026-00001" — open 3 days — HIGH (deadline Apr 22)
- "Channel name" — open 6 sessions — HIGH (blocking content production)
- "govcon-vendor-quoting vs tracker-update skill first" — open 1 session — LOW

### Pipeline Position

One sentence from `[dept]/brain/pipeline/current-state.md`. Orientation, not status report.
Example: "10 opps scored for Apr 22-23 window. Cable Assembly blocked on vendor quotes."

## Tone

Crisp. Military briefing style — state facts, give picture, hand off.
No filler ("Great news!", "Let's dive in!", "Here's what we've got:").
No repetition of things the operator already knows.

## Length Target

Entire brief readable in 30 seconds. If longer, cut.
Memory Drift + Infra Snapshot together should be ≤5 lines. Dept body ≤10 lines. Flags ≤3 bullets.

## Order matters

1. Memory Drift (surfaces corrections before anything else — if I fixed something, he sees it first)
2. Infrastructure Snapshot (machine state before dept work — he needs to know if Ollama is running before deciding to kick off a council run)
3. Incoming State → Open Loops → Pending Decisions → Pipeline (dept work orientation)
4. Cross-Dept Flags (peripheral scan)
5. Intent capture (stage 6)

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[2026-04-17-ops]]
- [[current-state]]
- [[decisions]]

<!-- AUTOLINK-END -->
