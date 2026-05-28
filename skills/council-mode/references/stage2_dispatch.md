# Stage 2 — Parallel Dispatch

Council mode fans out the same task to all selected participants simultaneously, then
waits for all responses before producing the diff.

---

## Dispatch Model

```
                       ┌────────────────────┐
                       │   council_run.py   │
                       │   (orchestrator)   │
                       └──────────┬─────────┘
                                  │  fan out in parallel
          ┌──────────────┬────────┼────────┬──────────────┐
          ▼              ▼        ▼        ▼              ▼
       C-claude       B-claude  A-claude  A+-claude    C-local   B-local
      (Haiku)        (Sonnet) (Sonnet+  (Opus       (Ollama    (Ollama
                              Opus adv)  solo)      gemma4)    qwen2.5)
          │              │        │        │          │          │
          └──────────────┴────────┼────────┴──────────┴──────────┘
                                  │  collect all
                                  ▼
                       ┌────────────────────┐
                       │   Diff Report       │
                       │   (Stage 3 output)  │
                       └────────────────────┘
```

---

## Concurrency Rules

- Claude participants use `asyncio` with the Anthropic async client (or thread pool).
- Ollama participants hit `http://localhost:11434/api/generate` — no rate limit concerns,
  but run sequentially if resource-constrained (single GPU).
- **Cap simultaneous Claude calls at 3** to avoid rate-limit bursts.
- **Timeout each participant at 120s.** Log timeout as a failure mode — it IS a failure
  mode worth surfacing in the diff.

---

## Participant Selection Strategy

| Goal | Roster |
|---|---|
| Full comparison study | All 6 (default) |
| Local-only data-sensitive work | C-local + B-local |
| Claude-tier comparison only | C-claude, B-claude, A-claude, A+-claude |
| Cheap compare | C-claude + C-local |
| Plan-grade compare | A-claude + A+-claude + B-local |
| Smoke test | B-claude + C-local |

---

## Budget Math

Rough per-run cost estimate (full roster, 1K input / 500 output tokens each):

| Participant | Cost |
|---|---|
| C-claude | ~$0.003 |
| B-claude | ~$0.011 |
| A-claude (advisor budget: 3) | ~$0.050 |
| A+-claude | ~$0.054 |
| C-local | $0 |
| B-local | $0 |
| **Full roster total** | **~$0.12 per council run** |

Advisor-budget impact: 1 Tier A council participant = 3 advisor calls against the daily
20-call cap. Two full councils per day hits the advisor ceiling.

---

## Error Handling

If a participant fails (API error, timeout, Ollama unreachable):
- **Do not retry.** The failure IS data.
- Log `"status": "failed"` + reason in the participant's slot.
- The diff report notes: "Participant X failed with [reason]" — this often exposes
  deployment issues (e.g., Ollama not running, API key expired).

If the majority of participants fail: halt, do NOT produce a diff, alert the operator.

---

## Logging

Each run appends one block to `master-brain/skills/council-mode/logs/council_runs.md`:

```markdown
## 2026-04-16 14:32 — Council run

**Task:** [first 80 chars]
**Participants:** C-claude, B-claude, A-claude, C-local
**Cost:** $0.061
**Advisor calls:** 3
**Duration:** 14.2s
**Failures:** none

[Link to full diff report]
```

Diff reports themselves are verbose — store them in `logs/diffs/council-YYYY-MM-DD-HHMM.md`
and link from the run log.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[council-YYYY-MM-DD-HHMM]]
- [[council_runs]]

<!-- AUTOLINK-END -->
