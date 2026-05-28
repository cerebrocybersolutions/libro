# Stage 3 — Execute
## Advisor Dispatch

**Purpose:** Run the task using the configuration from Stage 2. Three execution paths
depending on context. The path chosen does not change the tier logic — only the delivery
mechanism.

**Input required:** Config block + task + Opus plan (if Tier A/A+)
**Output:** Task result + execution metadata (model used, advisor calls, time)

---

## Three Execution Paths

### Path 1 — Operator Mode (within active Claude Code session)

Use when: the operator is in a live Claude Code session and the task came in conversationally.

The skill does not call an external API. Instead, I (Claude in the current session)
adopt the behavior profile for the assigned tier:

| Tier | Behavior profile |
|---|---|
| C | Answer directly, one pass, no hedging |
| B | Structure first, show reasoning, one self-review |
| A | PLAN FIRST (present plan, wait, then execute following Opus plan structure) |
| A+ | Extended reasoning trace, confidence levels, the operator approval required |

**Tier A operator sequence:**
```
Step 1: "PLAN (Tier A — Opus advisory mode):"
         [numbered plan based on what Opus would recommend given the task]
Step 2: [Present plan — wait for the operator's implicit or explicit go-ahead]
Step 3: "EXECUTING PLAN:"
         [Follow the plan step by step — no improvising from the plan]
Step 4: "SELF-REVIEW:"
         [Did the output follow the plan? Flag any deviations.]
Step 5: Hand off to Stage 4 (log the dispatch)
```

**NEVER in operator mode:**
- Skip the plan presentation for Tier A
- Start executing before the plan is shown
- Mix tier behaviors (don't use Tier B speed on a Tier A task)

---

### Path 2 — API Mode (Python script execution)

Use when: the operator triggers a script via the terminal or any shell to run a task
programmatically — batch processing, automated workflows, testing the harness.

**Script to call:** `Scripts/dispatch_advisor.py`

```bash
# Tier C
python dispatch_advisor.py --tier C --task "Format this JSON: {...}"

# Tier B
python dispatch_advisor.py --tier B --task "Write a proposal for CMMC audit service"

# Tier A
python dispatch_advisor.py --tier A --task "Should we pursue SAMPLE-2026-00001?" --max-uses 3

# Tier A+ (requires --confirm flag)
python dispatch_advisor.py --tier A+ --task "Full architecture review" --confirm
```

**What the script does:**
1. Loads config from Stage 2 based on `--tier`
2. Sets `ANTHROPIC_API_KEY` from environment
3. Builds the messages array with system prompt and task
4. Calls `client.beta.messages.create()` with advisor tool if Tier A
5. Streams the response (so the operator sees output as it generates)
6. Writes execution metadata to `logs/daily_usage.md`
7. Prints tier, model used, advisor calls consumed, estimated cost

**API key setup check (run before any API call):**
```python
import os
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not set.")
    print("Set it with: export ANTHROPIC_API_KEY=your_key_here")
    print("Or add it to your shell profile (~/.zshrc or ~/.bash_profile)")
    sys.exit(1)
```

---

### Path 3 — Dashboard Artifact Mode

Use when: the operator wants to test the skill live in the browser, demonstrate it for
content, or compare tiers side-by-side.

Trigger: the operator says "open the dashboard" or "show me the artifact"

The dashboard artifact (React/HTML, built separately) provides:
- Task input field
- Tier auto-classification display (scoring breakdown)
- Model selector (override allowed)
- Live API call with streaming output
- Advisor call counter vs. budget gauge
- Per-tier cost estimate
- Session log viewer

To generate the dashboard artifact, invoke:
```
Build the advisor-mode dashboard artifact
```
Claude will generate the full React component. the operator provides his API key in the
dashboard UI — it is never stored, only used client-side for the session.

---

## Execution Checklist (all paths)

Before executing ANY task at ANY tier:

- [ ] Stage 1 classification was completed (tier is assigned, not assumed)
- [ ] Stage 2 config is set (model, max_uses, system prompt)
- [ ] For Tier A: Opus plan is written and presented (not skipped)
- [ ] For Tier A+: the operator has given explicit approval
- [ ] API key is set (Path 2 only — checked before first call)
- [ ] Brain context loaded (surfaced in Brain Check, not ignored)

---

## Output Format (all paths)

```
EXECUTION RESULT
────────────────
Tier:           [C / B / A / A+]
Model:          [model name(s)]
Advisor calls:  [N of max_uses, or N/A]
Task:           [one-line summary]

[Task output here]

Metadata:
  Est. cost:    ~$[X.XX]
  Tokens in:    [N]
  Tokens out:   [N]
  Advisor tok:  [N, or N/A]
```

---

## Handoff to Stage 4

Pass to `stage4_monitor.md`:
- Tier used
- Model(s) used
- Advisor calls consumed (exact count)
- Estimated cost
- Task type (for pattern tracking)
- Timestamp

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[daily_usage]]
- [[stage4_monitor]]

<!-- AUTOLINK-END -->
