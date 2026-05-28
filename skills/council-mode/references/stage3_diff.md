# Stage 3 — Surface the Diffs

The diff report is the deliverable. Individual model outputs are raw material. The diff
is what the operator uses to make routing decisions and what becomes content.

---

## Diff Report Structure

```markdown
# Council Diff Report — [timestamp]

## Task
[full task as sent]

## Diff Question (from Stage 1)
"[what we set out to learn]"

## Participants
| Slot | Model | Status | Latency | Cost |
|---|---|---|---|---|
| C-claude | haiku-4-5 | ✓ | 1.2s | $0.002 |
| B-claude | sonnet-4-6 | ✓ | 3.8s | $0.009 |
| A-claude | sonnet+opus | ✓ | 22.4s | $0.046 |
| A+-claude | opus-4-7 | ✓ | 18.9s | $0.051 |
| C-local | llama3.1:8b | ✓ | 4.7s | $0 |
| B-local | qwen2.5:14b | ✓ | 19.3s | $0 |

## Headline Disagreements
(Top 3–5 axes where participants diverged. Ordered by material impact.)

1. **[Axis]** — [one-sentence description of the disagreement]
   - C-claude: [what it said]
   - B-claude: [what it said]
   - A+-claude: [what it said]
   - C-local: [what it said]

2. **[Axis]** — ...

## Failure Modes Surfaced
- **C-claude:** [specific failure observed, with quoted text if short]
- **B-claude:** [specific failure]
- **A-claude:** [specific failure]
- (etc.)

## Convergences (where all/most agreed)
- [thing 1] — signals this is either well-established knowledge or the task doesn't
  exercise model differences on this axis.

## Router Takeaway
(One paragraph: what did we learn about when to use which model for this task type?)

## Full Outputs
[Collapsed by default — each participant's full raw output.]
```

---

## How to Write the Headline Disagreements

The diff has to surface **material** disagreements, not stylistic ones. Rules:

- **Factual divergence > stylistic divergence.** If one model says "CAGE ABC12" and
  another says "CAGE ABC1Z", that's a headline disagreement. If one says "Dear Team" and
  another says "Hi team", that's noise.
- **Missing vs. padded > present vs. absent wording.** Haiku padding fake metadata is a
  diagnostic. Haiku not using an en-dash isn't.
- **Confidence calibration counts.** If Haiku says "definitely pursue" and Opus says
  "probably pursue with caveats," that's a disagreement on confidence — worth surfacing.
- **Call out hallucination by name.** If a model confabulates a fact, the diff must say
  "CONFABULATION: [model] invented [fact]" — loud and clear.

---

## Known Failure Modes (Reference Library)

This grows over time. As you run councils, record observed failure modes here so future
routing knows what to avoid.

### Haiku 4.5
- **Thin-prompt metadata padding.** On sparse prompts (no Cerebro context loaded), adds
  fake CAGE/UEI/NAICS values to fill space. Observed 2026-04-16 via `--compare`.
- **False confidence on edge-case rulings.** On ambiguous SDVOSB set-aside questions,
  answers with unearned certainty.

### Sonnet 4.6
- **Safe-generic drift.** On open-ended creative asks, regresses to a template.
- **Plan drift in long Tier A advisor loops.** After 3+ advisor exchanges, can lose the
  original plan framing.

### Opus 4.7
- **Over-elaboration.** Gives 5-point plans when 2 would do.
- **Hedge overload.** Can bury the recommendation under caveats.

### Llama 3.1:8b (local, Meta) — C-local
- (to be filled as observations accumulate)
- Chosen as C-local for fast daily-driver role on 24GB M5 — ~5GB Q4_K_M, runs alongside
  Claude Desktop + browser without memory pressure.
- Watch for: instruction-following drift on longer prompts (8B ceiling), slight
  preference for bulleted output where prose was asked.

### Qwen 2.5 14B (local, Alibaba) — B-local (internal only)
- (to be filled as observations accumulate)
- Swapped in 2026-04-17 PM-late replacing mistral-small:22b on internal surfaces.
  ~9GB footprint, 128K context, thermal-safer than prior 22B slot on M5 24GB.
- Watch for: occasional Mandarin-English register drift; `<think>` block leakage if
  `reasoning` flag is left on; tool-call serialization is not Qwen 3's improved format.
- **Internal only.** Swap to `mistral-small:22b` for any run captured on SHIPPED
  surfaces (GovCon OS default install, external YouTube, pitch decks).

### Phi4:14b (local, Microsoft) — B-alt
- (to be filled as observations accumulate)
- Third training lineage (Meta Llama / Alibaba Qwen / Microsoft Phi) for adversarial
  diversity. ~9GB footprint. Microsoft origin — different RLHF patterns than either
  Llama or Qwen, so catches failures the other two share.
- Watch for: over-structured step-by-step when concise answer was asked, strong
  preference for numbered lists.

### (Deprecated — reference only)
- `gemma4:e4b` was an earlier C-local pick; kept in the olw Karpathy smoke-test only per
  `project_olw_gemma_heavy_warning`. Not used in council-mode as of 2026-04-16.

---

## Router Takeaway — How to Write It

One paragraph. Structure:

> "For [this task type], [model X] failed on [axis A]. [Model Y] succeeded on [axis A]
> but failed on [axis B]. [Model Z] was cleanest overall but cost [N]. Going forward,
> route [this task type] to [chosen model], or use council if [specific condition]."

This paragraph is the part the operator keeps. It updates the routing heuristics in
advisor-mode's `stage1_classify.md` over time.

---

## When the Diff Is Filmable

If any of these land in a single run, it's worth capturing for EP02+:

- A model confabulates a fact that another model catches.
- Local (Ollama) beats Claude Haiku on cleanliness (already observed 2026-04-16).
- A tier-escalation paid off visibly (A caught what B missed on a decision).
- A tier-downgrade validated (B produced the same output as A+ — you could have saved
  the Opus call).

See `filmable_beats.md` for capture guidance.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[filmable_beats]]
- [[stage1_classify]]

<!-- AUTOLINK-END -->
