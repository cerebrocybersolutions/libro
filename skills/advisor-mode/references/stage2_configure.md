# Stage 2 — Configure
## Advisor Dispatch

**Purpose:** Take the tier assignment from Stage 1 and produce a complete configuration
block ready for the executor. Set the model pair, budget, and behavioral constraints
before a single token is generated toward the actual task.

**Input required:** Tier label + task description from Stage 1
**Output:** Full configuration block passed to Stage 3

---

## Configuration by Tier

### Tier C — Haiku 4.5

```python
config = {
    "model": "claude-haiku-4-5",
    "max_tokens": 2048,
    "tools": [],                     # No advisor tool
    "betas": [],
    "system": SYSTEM_PROMPT_C,       # See advisor_prompt_templates.md
    "task_description": "[task]",
    "advisor_max_uses": None,        # N/A
    "extended_thinking": False,
    "tier": "C"
}
```

**Behavioral instructions for operator mode (within Claude Code):**
- Answer directly and concisely
- Do not overthink; do not hedge
- Single pass — no self-review unless output is a deliverable file
- Target completion: under 60 seconds

---

### Tier B — Sonnet 4.6

```python
config = {
    "model": "claude-sonnet-4-6",
    "max_tokens": 8096,
    "tools": [],                     # No advisor tool
    "betas": [],
    "system": SYSTEM_PROMPT_B,       # See advisor_prompt_templates.md
    "task_description": "[task]",
    "advisor_max_uses": None,        # N/A
    "extended_thinking": False,
    "tier": "B"
}
```

**Behavioral instructions for operator mode:**
- Structure your response before writing
- Think through the steps; show your reasoning briefly
- One self-review pass before final output
- Flag any assumptions made

---

### Tier A — Sonnet 4.6 + Opus 4.7 Advisor

```python
config = {
    "model": "claude-sonnet-4-6",        # Executor
    "advisor_model": "claude-opus-4-7",  # Advisor
    "max_tokens": 16000,
    "tools": [
        {
            "type": "advisor_20260301",
            "name": "advisor",
            "max_uses": 3               # Default — never set below 2
        }
    ],
    "betas": ["advisor-tool-2026-03-01"],
    "system": SYSTEM_PROMPT_A,           # See advisor_prompt_templates.md
    "task_description": "[task]",
    "advisor_max_uses": 3,
    "advisor_prompt": ADVISOR_PROMPT_A,  # See advisor_prompt_templates.md
    "extended_thinking": False,          # Enable at A+ only
    "tier": "A"
}
```

**Behavioral instructions for operator mode:**
- STOP before executing. Produce a written plan first.
- Format: "PLAN: [numbered steps]" — present to the operator before proceeding
- Only begin execution after plan is confirmed (explicit or implicit from context)
- After execution: brief self-review — did the output follow the plan?
- Log advisor call count to Stage 4

**Tier A sequence (in order, no shortcuts):**
1. Sonnet reads task + Brain context
2. Sonnet calls advisor tool → Opus produces plan + decision criteria
3. Sonnet presents plan to the operator (in operator mode) or executes plan (in API mode)
4. Sonnet executes following Opus's plan explicitly
5. Sonnet self-reviews output against plan
6. Stage 4 logs the dispatch

---

### Tier A+ — Opus 4.7 Solo

```python
config = {
    "model": "claude-opus-4-7",
    "max_tokens": 32000,
    "tools": [],
    "betas": ["interleaved-thinking-2025-05-14"],   # Extended thinking
    "thinking": {
        "type": "adaptive",                # Required on Opus 4.7 (enabled returns 400)
        "effort": "high"                   # low | medium | high — replaces budget_tokens
    },
    "system": SYSTEM_PROMPT_APLUS,       # See advisor_prompt_templates.md
    "task_description": "[task]",
    "advisor_max_uses": None,
    "extended_thinking": True,
    "tier": "A+"
}
```

**Behavioral instructions for operator mode:**
- Extended reasoning is active — take the time needed
- Do not rush to an answer; work through the problem fully
- Produce a written reasoning trace before the final recommendation
- Present conclusions with explicit confidence levels
- **Requires the operator approval before dispatching**

---

## Budget Override Rules

| Condition | Action |
|---|---|
| Time-sensitive task (deadline in <2 hours) | Reduce `max_uses` to 2 |
| Simple Tier A task (clearly bounded) | `max_uses` = 2 |
| Complex Tier A task (multi-part, strategic) | `max_uses` = 3 (default) |
| Exploratory / unknown complexity | `max_uses` = 3 |
| the operator requests more depth | `max_uses` = 4 (log as override) |

---

## Handoff to Stage 3

Pass to `stage3_execute.md`:
- Full config block (tier, model, max_uses, system prompt key)
- Task description (verbatim from Stage 1)
- Opus plan (if Tier A — do not proceed to execution without it)
- Brain context relevant to the task

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[advisor_prompt_templates]]
- [[stage3_execute]]

<!-- AUTOLINK-END -->
