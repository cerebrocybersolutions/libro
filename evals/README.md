# Evals

> **LEGACY — 2026-07-26.** advisor-mode is retired upstream and ships marked LEGACY;
> this harness evaluates a retired classifier and is kept for reference. `--mock` is
> offline and safe. **The default (live) mode calls the Anthropic API and bills your
> key.** Prefer `--mock`. The durable part is the tier heuristic in the skill's banner,
> not this dispatcher.

Evaluation harness for Libro's routing logic. Start with the advisor-mode task
classifier, which decides what model tier a task should run on.

## Why evaluate routing

The advisor-mode classifier scores each task on complexity, reversibility,
cross-department impact, and stakes, then assigns a tier:

| Tier | Total score | Model |
|------|-------------|-------|
| C    | 0–2  | Haiku |
| B    | 3–5  | Sonnet |
| A    | 6–9  | Sonnet + Opus advisor |
| A+   | 10–12 | Opus (operator approval) |

Routing quality is asymmetric. **Under-classifying** a high-stakes task (routing
it to a weaker, cheaper model) is the dangerous failure. **Over-classifying** is
merely wasteful. The harness measures both, separately.

## Run it

Offline (no API key, deterministic — runs in CI):

```bash
python evals/eval_dispatch.py --mock
```

Live (calls the real classifier via Claude Haiku):

```bash
export ANTHROPIC_API_KEY=...
python evals/eval_dispatch.py
```

JSON output for tooling:

```bash
python evals/eval_dispatch.py --mock --json
```

## Metrics

- **exact accuracy** — predicted tier equals expected tier.
- **adjacent accuracy** — prediction within one tier. The classifier's conflict
  rule says "when unsure, pick the higher tier," so off-by-one-up is acceptable.
- **under-classified** — predicted a *lower* tier than expected. The unsafe error.
- **over-classified** — predicted a *higher* tier than expected. Safe but wasteful.
- **confusion matrix** — rows are expected tiers, columns are predicted.

## CI gates

Fail the build on quality regressions:

```bash
python evals/eval_dispatch.py --mock --min-adjacent 0.9 --max-under 1
```

`--min-adjacent` fails if adjacent accuracy drops below the threshold.
`--max-under` fails if too many tasks are routed too weak.

## Add cases

`cases/dispatch_cases.json` is a list of labeled tasks:

```json
{ "task": "Should we pursue SAMPLE-2026-00001?", "expected": "A", "note": "why" }
```

Add real tasks with the tier you'd expect a careful operator to assign. Cases
that don't match a fast-track keyword are the most valuable — they test judgment,
not string matching.

## Modes

- `--mock` uses the documented fast-track keyword rules as a local classifier.
  It is intentionally simple; misses in mock mode show where keyword routing is
  brittle and where real model judgment is required.
- The live classifier lives in `skills/advisor-mode/Scripts/classify_task.py`.
