# Filmable Beats — Council Mode

Council runs are natively good content. The side-by-side structure reads well on screen,
and the "route around failure, not pick the best" thesis has a clear visual hook.

---

## The Core Visual (EP02 Hook)

Split-screen terminal or web view: **same prompt** sent to 4–6 panels at once. Hit enter.
Watch the outputs land at different speeds (Haiku first, Opus last). Camera-ready.

---

## Film Checklist — Before Hitting Enter

- [ ] Prompt is a real Cerebro task (solicitation eval, vendor email, bid decision) —
      not a toy example.
- [ ] Roster is locked (typically full 6-participant).
- [ ] Dry-run has been done off-camera to confirm wiring works.
- [ ] Terminal theme has enough contrast for screen recording.
- [ ] Diff report gets opened on camera after completion — that's the punchline.
- [ ] "Diff question" from Stage 1 is stated on camera before running (sets the hook).

---

## Three-Beat Edit Structure

**Beat 1 — The Setup (~30s)**
The operator frames the task + the diff question: "I'm going to ask all 6 models the
same question about [sample opportunity]. The diff question is: will any model catch
the qualifying constraint?" Kills the "watch which one wins" framing up front.

**Beat 2 — The Run (~60s, with timelapse if slow)**
Hit enter. Show the latencies differ. Show participant failures if any (an Ollama timeout
is content, not a bug). Watch all land.

**Beat 3 — The Diff (~90s)**
Scroll through headline disagreements. Point at specific failure modes. "Haiku made up
a CAGE code. Sonnet was safe but missed the set-aside math. Opus caught it but took 3x
longer. Here's what that tells me about routing." End with the router takeaway.

---

## Content Angles By Use Case

| Use case | Hook line | What's in frame |
|---|---|---|
| Haiku padding exposed | "Watch Haiku make up facts when it doesn't have enough context." | Side-by-side with Sonnet or local Ollama (cleaner) |
| Local beats cloud on something | "The free model running on my laptop just caught something GPT-4-tier missed." | Local output highlighted, Claude output faded |
| Escalation payoff | "Tier B said ship it. Tier A said wait. Tier A+ said here's why." | Progressive reveal of each tier's confidence |
| Downgrade validation | "Same output on Haiku as Opus — that's $50 of Opus calls I can stop making." | Cost comparison overlay |

---

## What NOT to Film

- Full roster runs on routine tasks (6 dispatches of "write a formal email" has no
  disagreement signal — boring content).
- Live API key entry. Council mode assumes the key is set via env var. If filming
  setup, redact the key or use the dry-run.
- Failed council runs where most participants errored. That's a tooling bug, not
  content. Fix off-camera.
- Anything where the diff question wasn't pre-stated — the video has no hook without it.

---

## Tie-In to EP02

EP02 is the Advisor Dispatch deep dive. Council mode is the **closing demo** of that
episode — the payoff for having built the tier system in the first place. Structure:

1. (EP02 intro) — "Here's why routing matters."
2. (Live tier-A run) — pick a real bid decision, run advisor-mode Tier A on camera.
3. (Council callback) — "But how did we know Tier A was the right tier? Because we
   ran the council." Cut to a council run of the same task.
4. (Router takeaway) — "This is how the routing gets smarter every week."

Or: council can carry its own standalone episode if EP02 gets long. Call it EP03 and
lead with a Haiku-caught-padding clip.

---

## Post-Run Content Capture

After any council run that surfaces a new failure mode, update
`references/stage3_diff.md` "Known Failure Modes" section. That file becomes the script
library for future videos — each entry is a potential 60-second clip.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[stage3_diff]]

<!-- AUTOLINK-END -->
