# Stage 4 — Cross-Dept Flag Check (verify-before-surface)

## Purpose

the operator is about to go heads-down in one department. Before he does, surface anything from
other departments that is genuinely urgent — the kind of thing that would be bad to miss
while focused elsewhere.

This is NOT a company-wide brief. That's what `/ceo-brief` is for.
This is a quick peripheral scan: "anything I should know before I tune everything else out?"

## Source

Read `master-brain/awareness.md` — specifically the **Active now**, **Blockers**, and **Next**
lines for every department OTHER than the one being briefed.

Do NOT re-read all department Brain files here — that would make this too slow.
awareness.md is the synthesized view and is sufficient for flag DETECTION.

## Verify before surfacing (NEW in v2)

Before surfacing any flag as HIGH, run a 1-line spot-check against the implied source.
awareness.md can lag reality the same way memory can.

Example verify patterns:
- Flag says "GovCon deadline SOL-XXXXXXX <date>" → `grep SOL-XXXXXXX govcon/brain/pipeline/current-state.md` to confirm still in pipeline
- Flag says "Content channel name blocking production" → check `content-creation/brain/decisions/decisions.md` for a recent "Resolved" marker
- Flag says "Cyber Services lead-service decision HIGH" → check most recent `cyber-services/brain/sessions/*.md` for any resolution line

If the verify check contradicts the flag (flag says open, reality shows resolved), don't
surface it — add to Stage 5 hygiene list as a "awareness.md drift" finding.

## What Qualifies as a Flag

**Include:**
- A deadline within 7 days (check for specific dates in awareness.md)
- A decision explicitly called out as HIGH or blocking revenue across 2+ sessions
- Something in another dept that directly depends on what the operator does in today's dept
  (e.g., "Content blocked until channel name picked" → flag if working in GovCon)
- A department that just went 🔴 or has a new critical blocker since last session

**Do NOT include:**
- Routine pending decisions that have been sitting without urgency
- Things "in progress" normally
- Anything already in the primary department's brief
- Department status updates that don't require action

## Output Format

Only output this section if at least one flag qualifies AND passed verification:

```
## ⚠️ Cross-Dept Flags
- **[Dept]:** [1-line — what's urgent and what happens if ignored]
- **[Dept]:** [...]
```

Maximum 3 bullets. If you have 5 candidates, pick the 3 most urgent.
If nothing qualifies: omit this section entirely. Don't write "No flags" or "All clear."
Absence IS the all-clear.

## Examples

Good flag (verified):
- **GovCon:** SOL-XXXXXXX due in 8 days — Go/No-Go still open. Confirmed in pipeline/current-state.md.

Good flag (verified):
- **Cyber Services:** Lead-service decision open 4 sessions — blocking revenue activation. Confirmed unresolved in cyber-services/brain/decisions/.

Not a flag (too routine, even if awareness.md mentioned it):
- BlackBox: Buyer validation not yet started — forcing function set for May 14

Not a flag (awareness drift — would have been v1 failure mode):
- Training: Class date not yet set [surface only if deadline genuinely approaching]

## Placement

Cross-dept flags come AFTER the Infrastructure Snapshot + dept brief, BEFORE intent capture.
This order: machine state, dept picture, peripheral awareness, commit to today's work.
Interrupting the dept brief with other-dept info breaks focus.

## Drift handoff

Any flag that fails verification gets handed to Stage 5 as a "awareness.md drift" finding.
Stage 5 will note it for awareness.md refresh (usually deferred to the next sessionend).

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[awareness]]
- [[current-state]]
- [[decisions]]

<!-- AUTOLINK-END -->
