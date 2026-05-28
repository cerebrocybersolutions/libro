# Filmable Beats — Orchestrator Mode

Orchestrator mode is natively filmable because the tier-labeled progression of subtasks
is visually clean content. This file lays out the beats worth capturing and the edit
structure that works for EP02+ footage.

---

## Why Orchestrator Footage Hits Differently Than Council

Council footage = side-by-side model outputs. It's comparison content. Audience gets to
see disagreement.

Orchestrator footage = a timeline. A chain. It's a **journey** — "watch this task get
handled by Haiku, Sonnet, then Opus — and here's where it had to escalate."

Where council surfaces failure modes across models, orchestrator surfaces the **tier
ladder as a workflow**. That's a different narrative beat, and it's arguably closer to
what Cerebro actually sells — "we route around failure on your behalf."

---

## EP02 Hook Candidates (pick one)

These are hook lines that work as voiceover or lower-third at the top of an orchestrator
segment:

1. *"Most AI agents try to pick the best model. I'm going to show you a system that
   picks the cheapest model that passes — and escalates only when it has to."*
2. *"This task just ran across four different models. Only one of them had to work hard.
   That's the whole point."*
3. *"Watch the tier escalate in real-time when the cheap model hallucinates."*
4. *"Every step is a decision: can the $0.002 model handle this, or do I pay for $0.05?"*

Pick the hook that matches the subtask that actually escalated in the chain being
filmed. Don't script the hook before running the chain — let the chain pick the hook.

---

## Three-Beat Edit Structure (20–40 second orchestrator clip)

**Beat 1 — The Decomposition Reveal (5–8s)**
Show the plan-file JSON on screen. Voiceover: "Four subtasks. Four different tiers. One
task."

**Beat 2 — The Chain Running (10–20s)**
Show the terminal output as subtasks execute. Key visual: the tier label changing per
step. The escalation moment — if one happened — gets a slight pause in the edit.

**Beat 3 — The Escalation Payoff or The Clean Run (5–10s)**
Two different endings depending on what the chain did:

- *Escalation happened:* zoom on the escalation log line. Voiceover: "C-local failed
  the fact check. Re-dispatched to C-claude. Caught it." Cut.
- *Clean run:* show the total cost ($X) vs. what it would have cost on A+ end-to-end
  ($Y). Voiceover: "Full pipeline: [$X]. If I'd run everything at the ceiling: [$Y]."
  Cut.

---

## Capture Checklist (Before Running)

| Item | Why |
|---|---|
| Screen recording on, terminal sized so output is readable | Obvious |
| Brain workspace path visible in terminal title | Viewer learns the architecture |
| No secrets in environment — scrub `env | grep KEY` first | Self-explanatory |
| Plan-file opened in editor beside terminal | Split-screen shows decomposition |
| Timestamp readable on screen | Accountability, authenticity |
| Have a fallback task queued if this one runs too fast/too slow | Don't waste the take |

---

## Content Angles by Use Case

| Chain being filmed | Best angle |
|---|---|
| Solicitation pursue/no-bid | "How I triage government contracts at scale" |
| Vendor quote request pipeline | "Sourcing agent that knows when to escalate" |
| Cross-dept synthesis (Brain query) | "Chief of Staff routing its own workload" |
| Content repurpose pipeline | "One video idea becomes five outputs at three tiers" |
| COR submission packet chain | "How a tier ladder delivers a federal contract packet" |

---

## What Makes a Chain Filmable vs. Not

**Filmable:**
- At least one tier escalation occurred (pays off the "route around failure" thesis)
- Total chain duration 30–120s (long enough to show the progression, short enough to
  cut cleanly)
- Each subtask's output is visible on-screen (not truncated)
- Final output is specific and real (a real solicitation, a real vendor email) — not a
  toy example

**Not filmable (don't capture):**
- Every subtask passed on first try — no tension
- Chain halted with no recovery — viewer feels bad, no payoff
- Subtask outputs are too long to fit on screen without clever editing
- Task is something that would reveal client/contract info — substitute anonymized

---

## Pairing With Council Mode

The strongest EP02 segment pairs council + orchestrator:

1. Open with council — "Here's what happens when I run this on every model"
2. Diff report surfaces which tier is the floor for which subtask
3. Cut to orchestrator — "Now watch me turn that knowledge into a plan"
4. Chain runs, escalates, lands
5. Close: "Council taught me where they fail. Orchestrator runs the production line."

This is the "comparison → automation" arc that makes the system feel like a real
pipeline, not a demo. It also positions Cerebro's work as **infrastructure**, not
prompts — which is the positioning pillar (see markdown 4D chess thesis).

---

## Don't-Film List

- Any chain that touches a live client conversation, negotiation, or PII
- Any chain that writes to a production tracker, sends an actual email, or executes
  irreversible action (these stay behind the scenes)
- Any chain whose plan file contains Brain internals that shouldn't be public
  (credential references, specific contract dollar amounts, private comms)

Orchestrator is a work tool first, content second. When those conflict, work wins.
