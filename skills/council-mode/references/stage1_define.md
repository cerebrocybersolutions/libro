# Stage 1 — Define the Council Task

Council runs are only as good as the task framing. A bad task produces six identical
outputs (no signal) or six wildly different outputs that can't be meaningfully diffed.

---

## Task Framing Checklist

Before dispatching, confirm the task:

- [ ] **Is specific enough that a diff is meaningful.** "Write me a vendor email" is too
      open — every model will produce a reasonable email. "Write a vendor quote request
      for {{vendor_name}} for solicitation {{solicitation_id}} using {{operator_cage}}"
      has enough specificity that factual misses will surface in the diff. (Resolve
      placeholders from `~/.cerebro/profile.yaml` + the live task context.)
- [ ] **Is not a simple lookup.** Council is waste on "what's 2+2." Any single tier will
      answer.
- [ ] **Has at least one axis where models could plausibly diverge.** Examples: factual
      recall, reasoning depth, hallucination pressure, format adherence, tone.
- [ ] **Is written in a form all participants can handle.** If including Brain context,
      keep it ≤ 8K tokens so Haiku can read it.
- [ ] **Names what you want to LEARN from the diff.** Write it down before running.

---

## Task Types That Produce Good Council Signal

| Task type | Why it diffs well | Watch for |
|---|---|---|
| Solicitation fit analysis | Factual recall + strategic reasoning combine | Haiku confabulating NAICS codes, Opus over-explaining |
| Vendor outreach draft | Tone + specificity | Sonnet safe-generic, Opus overlong |
| Strategic "pursue / no-bid" call | Reasoning + confidence calibration | Haiku false-confident, Opus appropriately hedged |
| Code review | Correctness + thoroughness | Local models missing security issues, Claude over-flagging |
| Brain update synthesis | Compression + faithful reproduction | Haiku dropping nuance, Sonnet re-organizing |

---

## Task Types That Waste Council

- Simple formatting ("turn this JSON into YAML")
- Single-fact lookup ("what's the operator's CAGE code")
- Binary yes/no with clear answer
- Anything that's been answered definitively in the Brain already

If the task is routine, dispatch through advisor-mode Tier C. Don't council it.

---

## Write Down Your Diff Question

Before running, answer in one sentence: **"I'm running this council to learn WHAT?"**

Good diff questions:
- "Will any model catch that the set-aside conflicts with the NAICS code?"
- "Which model pads fake metadata when asked for a summary with no source data?"
- "Does local Ollama hold up on a plan-grade reasoning task?"

Bad diff questions:
- "Which model is best?" (council doesn't answer this)
- "Will they all agree?" (convergence is boring — not the point)

The diff question becomes the first line of the diff report. It's also the hook line if
the run gets filmed.
