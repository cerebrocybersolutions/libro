# Stage 2 — Chain Execution

Once the plan is decomposed (Stage 1), chain execution runs the subtasks in order. Each
subtask dispatches to its tier, output is gate-checked, and the next subtask consumes the
declared inputs. This file describes how execution works, the sequencing rules, and the
failure handling.

---

## Execution Loop (per subtask)

```
for subtask in plan.subtasks:
    prompt       = build_prompt(subtask, prior_outputs)
    result       = advisor_dispatch(subtask.tier, prompt)
    gate_passed  = evaluate_gate(subtask.gate, result.text)

    if gate_passed:
        prior_outputs[subtask.id] = result
        continue

    # Gate failed — attempt escalation
    if subtask.escalations_used >= subtask.max_escalations:
        HALT — alert the operator, dump chain state
    if subtask.tier == "A+-claude":
        HALT — A+ never auto-escalates (irreversible work)

    result_esc = advisor_dispatch(subtask.escalate_to, prompt)
    if evaluate_gate(subtask.gate, result_esc.text):
        prior_outputs[subtask.id] = result_esc
        continue

    HALT — double failure signals decomposition error
```

---

## Sequencing Rules

1. **Strictly sequential by default.** Subtasks run in plan-file order. Parallel
   execution is a Stage 4 feature (executor not yet implemented; schema landed 2026-05-20
   via HM09-P1C cross-walk). The decomposer can now emit a `parents` field per subtask
   (list of subtask IDs or 0-based indices) expressing data dependencies as a DAG.
   Subtasks with empty `parents` are parallel-eligible; subtasks with non-empty `parents`
   wait until every parent completes. Executor wire-up is mechanical when Stage 4 ships —
   loop over topological strata instead of plan-file order. Pattern donor: Hermes v0.14
   `kanban_decompose.py` parent-index DAG.

2. **Each subtask sees only its declared `inputs`.** The chain engine builds the subtask
   prompt from (a) the subtask description, (b) its declared input outputs, and (c) the
   brain-context slice if requested. It does NOT pass prior outputs the subtask didn't
   declare.

3. **Failures halt the chain.** Orchestrator is not best-effort. If a subtask double-
   fails, downstream subtasks don't run — their dependencies are invalid.

4. **Chain state persists across halts.** On halt, the chain writes a state file
   (`logs/chains/[timestamp]-[plan-name].state.json`) so the operator can review,
   fix the plan, and resume.

---

## Gate Evaluation

Gates are evaluated locally (no LLM call) using one of four gate types. Keep them cheap
and deterministic.

| Gate type | Example | How evaluated |
|---|---|---|
| `contains` | "output contains 'NAICS' and 'deadline'" | Substring match |
| `regex` | "output matches `^\{.*\}$` (JSON)" | Regex compile + search |
| `json_schema` | "output is valid JSON with keys: naics, deadline, pop" | json.loads + key presence |
| `length_range` | "output between 200 and 800 chars" | len() bounds |

**Gates that are NOT supported:**

- LLM-as-judge gates — adds cost, adds failure surface, defeats the point. If you need
  a judge, the subtask belongs in council-mode, not orchestrator-mode.
- Human-review gates — orchestrator is automation. If a step needs a human eye, mark the
  subtask `halt_for_review: true` and design the chain to stop there.

---

## Prompt Construction

Each subtask prompt is assembled as:

```
[system: Cerebro operator context — same as advisor-mode]

Task: [top-level chain task, one sentence]

Subtask: [this subtask.description]

Prior outputs:
  [input_id_1]: <output text or declared slice>
  [input_id_2]: <output text>

Acceptance criteria: [subtask.gate, plain-language translation]

Respond with only the output that satisfies the criteria. No preamble.
```

Keeping the prompt shape identical across subtasks makes the chain log readable and
reduces model-specific prompt-format drift.

---

## Escalation Mechanics

Escalation is dispatch-again-at-higher-tier. It is NOT retry-same-tier. If a gate fails
at B-claude and the target is A-claude, the re-dispatch uses A-claude's full tier
mechanics (including the advisor tool if A-tier is configured that way). The escalated
call's cost is logged separately so the chain-run report shows "escalation cost" as a
distinct line item.

| Tier | Escalates to (default) | Notes |
|---|---|---|
| C-local | C-claude | If local model confabulated, paid tier fixes it |
| C-claude | B-claude | Most common escalation in practice |
| B-claude | A-claude | Advisor tool gets loaded at A |
| A-claude | A+-claude | Strategic → ceiling |
| A+-claude | HALT | Never auto-escalates — irreversible work |

Plan files can override these defaults with the `escalate_to` field per subtask.

---

## Concurrency Constraints

Even though the chain is sequential by design, the orchestrator respects the same
hardware rules as council-mode for any local dispatches:

- Only one Ollama model loaded at a time — if a chain uses both `llama3.1:8b` and
  `phi-4:14b`, the engine unloads the smaller before loading the larger to avoid
  memory pressure. Current fleet posture: Senior Advisor `gemma4:31b-instruct-q5_K_M`
  serves on `prime` (32GB, RTX 3080) with ~10GB headroom — no co-tenancy management
  needed for typical chains. OpenClaw was uninstalled 2026-04-19 PM (RAM-squat + bad
  close); prior "close OpenClaw before heavy chain steps" guidance is retired.
  `OLLAMA_KEEP_ALIVE=1m` mandatory across the fleet.
- Claude tier calls are sequential by default in orchestrator-mode (one subtask at a
  time). No thread-pool.

---

## Error Handling

| Error | Engine response |
|---|---|
| API timeout | Treat as gate fail → escalate |
| API 429 (rate limit) | Back off 30s, retry same tier once, then escalate |
| Ollama connection refused | Subtask fails → escalate to paid tier, log OLLAMA_DOWN |
| Gate parse error (malformed gate field) | HALT — plan bug, not runtime error |
| Input reference to missing prior output | HALT — decomposition error |

Errors are NOT silent. Every error writes a row to the chain log with the subtask id,
the error, and whether it was recovered.

---

## Chain-Run Artifact

Every chain run produces an artifact at
`logs/chains/[timestamp]-[plan-name].chain.md`:

```markdown
# Chain Run — [timestamp] — [plan-name]

## Task
[top-level task]

## Timeline
| # | Subtask | Tier | Gate | Escalated? | Cost | Latency |
|---|---|---|---|---|---|---|
| 1 | fetch | C-local | ✓ | — | $0 | 3.2s |
| 2 | extract_facts | C-local | ✗ → C-claude ✓ | yes | $0.002 | 11.8s |
| 3 | score_fit | B-claude | ✓ | — | $0.009 | 4.1s |
| 4 | decision | A-claude | ✓ | — | $0.046 | 18.9s |

## Totals
- Duration: 38.0s
- Cost: $0.057
- Escalations: 1 (subtask 2, C-local → C-claude)
- Advisor calls consumed: 2 (from A-claude subtask)

## Full Outputs (collapsed by default)
### 1. fetch — C-local
[output]
### 2. extract_facts — C-claude (post-escalation)
[output]
...
```

This artifact is the unit of content for EP02+ — it's a visual tier-ladder with clear
escalation moments.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[.chain]]

<!-- AUTOLINK-END -->
