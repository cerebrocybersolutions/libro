# Stage 1 — Decompose

Orchestrator-mode runs a compound task as a chain of subtasks. The chain is only as good
as the decomposition. This stage defines how to split a task well enough that each step
has (a) a defensible tier assignment and (b) a gate that can actually be evaluated.

---

## The Decomposition Discipline

A good subtask has five fields. If any are missing, the chain will drift.

| Field | What it answers | If missing |
|---|---|---|
| `id` | How do downstream steps reference this? | Chain can't compose |
| `description` | What is this step doing? | Gate can't be defined |
| `inputs` | Which prior outputs (by id) does this step need? | Token bloat, bias |
| `tier` | Which advisor-mode tier runs this? | No routing decision |
| `gate` | What makes the output acceptable? | No escalation trigger |

Optional but recommended:

| Field | Use when |
|---|---|
| `escalate_to` | Explicit escalation target if gate fails (overrides default) |
| `max_escalations` | Default 1. A+ subtasks are always 0. |
| `timeout_sec` | Override default 120s — local 22B models may need 180s |
| `notes` | Anything a human reviewer should know |
| `parents` | List of subtask IDs (or 0-based indices) this step depends on. Empty list = run in parallel with other parent-less tasks. Adopted from Hermes v0.14 `kanban_decompose.py` parent-index DAG (HM09-P1C cross-walk). Stage 4 executor sequential today; schema lands now so wire-up is mechanical when parallel execution ships. |

---

## Fanout=false Collapse — Single-Task Pass-Through (HM09-P1C)

When the decomposer determines a task is genuinely one unit of work, it should NOT force a multi-subtask plan. Return a fanout=false envelope instead:

```json
{
  "fanout": false,
  "rationale": "<one sentence on why no decomposition helps>",
  "tightened_title": "<tightened title for the single task>",
  "tightened_body": "<concrete spec for a single worker>",
  "tier": "<advisor-mode tier>",
  "gate": "<acceptance criteria>"
}
```

The orchestrator then dispatches one advisor-mode call against the tightened spec — no chain machinery, no gate-cascade complexity. Makes orchestrator-mode a strict superset of advisor-mode: same call surface, decomposer decides.

**When to emit fanout=false:**
- Task is a single canonical operation (read one file, draft one email, parse one JSON)
- No meaningful intermediate gates
- No tier-routing benefit (whole task fits one tier)

**Pattern donor:** Hermes v0.14 `tools/hermes-agent/hermes_cli/kanban_decompose.py` lines 95-104 + commit `1345dda0c`.

---

## Decomposer Output — JSON Schema (machine-consumption shape)

The table form above is human-readable. The machine-consumption form is JSON, mirroring Hermes' rigid contract:

```json
{
  "fanout": true,
  "rationale": "<one sentence on why this decomposition>",
  "subtasks": [
    {
      "id": "fetch",
      "description": "pull solicitation PDF text from SAM.gov",
      "tier": "C-local",
      "gate": "has_title AND has_naics",
      "inputs": [],
      "parents": [],
      "escalate_to": "C-claude",
      "max_escalations": 1
    }
  ]
}
```

Render parity: human-readable table + JSON schema both render from the same Stage 1 output state. Reproducibility #8 render-target separation. No preamble, no closing remarks, no code fences in the JSON output.

---

## Good vs. Bad Decompositions

**Good — solicitation pursue/no-bid:**
1. `fetch` — pull solicitation PDF text from SAM.gov (C-local, gate: has_title + has_naics)
2. `extract_facts` — parse NAICS, set-aside, deadline, PoP, scope (C-local, gate: 5/5 fields populated)
3. `score_fit` — score against Cerebro's capabilities matrix (B-claude, gate: score + rationale present)
4. `competitive_read` — search awarded history for incumbents (C-claude, gate: ≥2 data points or explicit "none found")
5. `decision` — pursue / no-bid / need-more-info (A-claude, gate: recommendation + confidence + 3 reasons)

Each subtask is single-purpose. Each gate is binary. Escalation targets are obvious.

**Bad — same task, poorly decomposed:**
1. `analyze` — "look at the solicitation and tell me what to do" (B-claude, gate: "is it good?")

One blob. No gates. No tier earning. This is a single advisor-mode call, not an
orchestrator chain.

---

## Subtask Sizing Heuristic

A subtask is the right size if a human could write a 2-sentence gate for it.

| Symptom | Fix |
|---|---|
| Gate requires more than 2 sentences | Subtask too large — split it |
| Gate is "output is correct" | Not a gate — define specific acceptance criteria |
| Two subtasks have identical gates | Merge them |
| Subtask needs inputs from 4+ prior steps | Chain is too deep — flatten or introduce a summarize step |

---

## Tier-Assignment Heuristics (Starting Points)

These are earned through council runs over time. Start conservative — one tier up from
where you think the floor is — and let chain logs pull tiers down once they prove out.

| Subtask signature | Start tier | Pull-down candidate |
|---|---|---|
| Deterministic parse / extract | C-local | n/a (already floor) |
| Schema fill from text | C-local | C-claude if local confabulates |
| Write a reply to a vendor | B-claude | C-claude after 5 clean runs |
| Classify a document type | C-claude | C-local after council confirms |
| Score a solicitation 1–10 | B-claude | C-claude if gate keeps passing |
| Compare two options with trade-offs | A-claude | B-claude only if council confirms |
| Strategic recommendation across depts | A-claude | not advisable to pull down |
| Pursue/no-bid / accept/reject / hire/fire | A+-claude | never pull down — irreversible |

---

## Inputs Discipline — What NOT to Pass

A subtask's `inputs` field references prior outputs by `id`. Do not pass:

- The full original task description — the subtask should only see what it needs to do
  its job. Pass the task to the chain, not to every subtask.
- The chain history — this biases downstream reasoning toward prior framings.
- Raw context Brain dumps — if a subtask needs Brain context, it should be a specific
  named slice (e.g., `brain: govcon/pipeline`) not the whole tree.

If a subtask truly needs the full chain context, the decomposition is wrong. Add a
`summarize_context` subtask that consolidates relevant priors, then feed its output
forward.

---

## Plan-File Format

Plans live in `Scripts/plans/*.json`. Schema:

```json
{
  "name": "solicitation_eval",
  "version": "1",
  "description": "SAM.gov solicitation pursue/no-bid pipeline",
  "subtasks": [
    {
      "id": "fetch",
      "description": "Pull solicitation PDF text from SAM.gov",
      "inputs": ["@task.url"],
      "tier": "C-local",
      "gate": "output contains both 'Title' and 'NAICS' tokens",
      "escalate_to": "C-claude",
      "max_escalations": 1
    },
    {
      "id": "extract_facts",
      "description": "Extract NAICS, set-aside, deadline, PoP, scope",
      "inputs": ["fetch"],
      "tier": "C-local",
      "gate": "output is valid JSON with 5 non-null keys",
      "escalate_to": "C-claude"
    },
    {
      "id": "score_fit",
      "description": "Score solicitation fit vs Cerebro capabilities",
      "inputs": ["extract_facts"],
      "tier": "B-claude",
      "gate": "output contains numeric score 1-10 and rationale paragraph",
      "escalate_to": "A-claude"
    },
    {
      "id": "decision",
      "description": "Pursue / no-bid / need-more-info recommendation",
      "inputs": ["extract_facts", "score_fit"],
      "tier": "A-claude",
      "gate": "output contains recommendation, confidence 1-5, and 3 reasons",
      "escalate_to": "A+-claude",
      "max_escalations": 1
    }
  ]
}
```

---

## When to NOT Decompose

Not every task deserves a chain. Signals to stop:

- Single-step tasks — go straight to advisor-mode.
- Research/exploratory tasks where you don't know the shape of the answer — use
  council-mode instead, let the diff teach you what the decomposition should be.
- Tasks where every subtask would be A-claude or A+-claude — just call the tier directly.
- Tasks where the total chain cost > one Opus call — orchestrator's cost edge disappears.

The decomposition is the cheap part of the system. The dispatch is the expensive part.
Cheap decomposition, expensive dispatch, quality gates — that's the whole architecture.
