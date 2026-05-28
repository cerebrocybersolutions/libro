# Stage 2.5 — Ground-Truth Verify (NEW in v2)

## Why this stage exists

On 2026-04-17, sessionstart v1 opened an Ops session telling the operator the ruflo-main ingest
filter was P1. Reality: the gap was already MITIGATED — ruflo-main had been moved to
`knowledge-vault/raw/processed/`, which Karpathy's `ingest.py` filters via path-parts.
Memory was stale because the file move happened outside a session where memory gets updated.

v1 surfaced memory verbatim with no verification. Stage 2.5 closes that class of drift.

**The contract:** every "P1 / aging / still open" claim gets one filesystem probe before
being surfaced in the brief. Drift goes to Stage 5 for hygiene. Confirmed-open items go
to Stage 3 for the brief.

---

## What to verify (prioritized)

### 1. Memory entries flagged as P1 or "next session"

For each memory file flagged P1 in Stage 2 (example: `project_ruflo_ingest_filter_gap.md`):
- Read the memory body (only now, not in Stage 2)
- Extract the falsification claim — "the filter is NOT shipped", "the skill is NOT installed", "X does NOT exist"
- Run the 1-line filesystem check that would resolve it

**Examples of falsification probes:**

| Memory claim | Probe | Drift signal |
|---|---|---|
| "ruflo-main not filtered" | `find master-brain/knowledge-vault -type d -name ruflo-main` | Result in `raw/processed/` = MITIGATED |
| "Tier 3 rename not done" | `ls govcon/` vs. `ls -d */brain 2>/dev/null` | If some depts have `brain/`, partial drift |
| "Skill X has no source-of-truth seed" | `ls master-brain/skills/X/SKILL.md` | File exists = CLOSED |
| "Heartbeat not wired" | `grep -l heartbeat master-brain/skills/*/Scripts/*.py` | Match = WIRED |
| "olw heavy = qwen2.5:14b" | `grep heavy master-brain/knowledge-vault/wiki.toml` | Current value = ground truth |
| "dept CLAUDE.md exists" (NEW v2.1 — Gap 4) | `ls {dept}/CLAUDE.md` | Missing = dept not scaffolded for per-dept pattern — surface as drift, recommend scaffold next |

### 2. Aging decisions (3+ sessions open)

For each decision in `decisions.md` that's been open across multiple session dates:
- Scan intermediate session files for any accomplishment that would have implicitly resolved it
- Example: "CMMC as lead service" open 4 sessions — check all 4 intermediate session files
  for any line containing "CMMC" or "lead service." If a decision was made and not written
  back to decisions.md, that's drift (surface for hygiene).

### 3. Awareness.md HIGH flags

Same principle — if awareness.md says "GovCon has HIGH flag X," spot-check the implied
source (a pipeline file, a session file, a DASHBOARD entry) and only surface the flag if
it still matches reality.

### 4. Session closure status (NEW in v2.1 — Gap 1)

For the most recent session file found in Stage 2 (dept Brain), verify whether it was
properly closed by sessionend or left hanging mid-session.

**Closure markers (all three must be present for a clean close):**
- `## Accomplished` or `### Accomplished` block (L2 or L3 — both accepted)
- `## Open Loops — Next Session` or `### Open Loops — Next Session` block (L2 or L3 — both accepted)
- `*Closed:* YYYY-MM-DD HH:MM` line (or equivalent closure timestamp) near the bottom

**Probe:**

```bash
# Check most recent session file for all three closure markers
# Regex tolerates both L2 (##) and L3 (###) Accomplished + Open Loops headers
# (B5-regex fix 2026-05-11 — closes false-positive UNCLOSED risk on L2-header sessions)
SESSION=$(ls -t {dept}/brain/sessions/*.md 2>/dev/null | head -1)
grep -c -E '^#{2,3} Accomplished|^#{2,3} Open Loops — Next Session|^\*Closed:' "$SESSION"
```

Count interpretation:
- 3 = clean close → surface "Incoming State" from `### Open Loops — Next Session`
- 1–2 = partial close → flag as UNCLOSED in Stage 3 brief, hand off to Stage 6 for (a)/(b)/(c) handling
- 0 = never written → treat as first session for dept

**If UNCLOSED:** do NOT auto-roll open loops forward. The previous session's state is
ambiguous — only the operator can resolve whether to (a) retroactive-close it now, (b) adopt its
WIP as today's intent, or (c) start fresh and archive the hanging file. Stage 6 asks.

### 5. Infrastructure probes (ops-infra / mixed sessions only)

Run these in parallel when session shape warrants:

```bash
# Ollama alive + what's loaded
curl -s --max-time 2 http://localhost:11434/api/tags | head -c 500
curl -s --max-time 2 http://localhost:11434/api/ps | head -c 500

# OLW lockfile / recent activity (if Karpathy package writes one — check its codebase first)
ls -la master-brain/knowledge-vault/.olw.lock 2>/dev/null
find master-brain/knowledge-vault/wiki -type f -mmin -10 2>/dev/null | head -5

# Advisor stack portability
python3 master-brain/skills/advisor-mode/Scripts/dispatch_advisor.py --dry-run 2>&1 | tail -5

# Circuit breakers
cat master-brain/state/circuit-breakers.json 2>/dev/null | head -20

# wiki.toml ground truth for olw heavy model
grep -E '^(fast|heavy)\s*=' master-brain/knowledge-vault/wiki.toml
```

**Important:** infra probes that would contend with a running long-process (Ollama, OLW)
must be read-only. Never `olw run`, never dispatch a live advisor call. `--dry-run` only.

### 6. Supply-chain advisory probe (H19 — added 2026-05-12)

```bash
# Returns count of unacked supply-chain hits; non-zero = surface in brief.
# Wire a supply-chain advisory probe of your choice; below is a stub.
cerebro-doctor --section supply-chain 2>/dev/null || echo "0 unacked supply-chain advisory hits"
```

Non-zero hit count = surface in brief with severity + advisory_id. Zero = silent.

---

## Output format from Stage 2.5

Produce a structured findings object for Stage 3 and Stage 5:

```
## Verification Results

### ✅ Confirmed (surface in brief as-is)
- item: description

### ⚠️ Drift (surface in hygiene block, auto-correct)
- item: claim was X, reality is Y, new memory body draft: "..."

### ❌ Resolved (remove from brief, log correction)
- item: memory said open, reality shows resolved on DATE via session SESSION-NAME

### 🔧 Infra state (Stage 3 snapshot block)
- Ollama: [status]
- OLW: [status]
- Advisor stack: [status]
- Circuit breakers: [status]
- olw heavy model: [value from wiki.toml]
```

---

## Timing budget

Stage 2.5 should complete in under 10 seconds total. If any single probe is slow (Ollama
timeout, large grep), skip it and mark as "unverified — surface as-is with warning."

Never block the brief for more than 10s. A slightly noisy brief beats a delayed brief.

---

## Interaction with existing feedback memories

This stage operationalizes multiple existing feedback memories:
- `feedback_cite_config_not_memory.md` — ground-truth from file, not memory
- `feedback_preempt_known_gaps.md` — scan memory for open gaps that would bite the run
- `feedback_check_skill_docs_before_config_guess.md` — verify before guessing

When surfacing a drift finding, cite the feedback memory that predicted it would matter.
This strengthens the feedback loop — the operator sees which rules paid off this session.

## Audit-self-drift register (NEW 2026-04-30 sessionstart)

**Canonical doc:** the operator's audit-self-drift register, if maintained.

Stage 2.5 should consult this register before pasting any Tier A prescription and before
declaring any closure event. The register catalogs:

- **Classification drifts D1–D5** — already-done / misclassified-archived / already-synced /
  misread / vacuum-not-executed. Probes here reject the prescription pre-Tier-A assignment.
- **Closure-ceremony drifts C1–C2** — README-index-closure (handoff body footer ≠ index row)
  and Tier-C-trigger-fire (ledger row stays parked despite trigger satisfied by prior commit).

Run probes 1–7 in the register's probe checklist before queueing the prescription. Append
historical-instances log on every Stage 2.5 hit. Register seeded from NIGHT-2 (5 instances)
+ NIGHT-3 (1 instance) + 2026-04-30 sessionstart (3 instances).

---

## Recursion-rule (NEW in v2.2 — Corrections 7 + 9 class)

### Why this rule exists

On 2026-04-18, two corrections fired with memory-of-source trust instead of
filesystem-of-source trust:

- **Correction 7** (knowledge-vault drift fix): I authored a "Rajiv Pant three-repo
  architecture" note as remediation for a missing-file claim, then in post-task
  verification globbed the canonical vault and found a sibling note already existed at
  `rajiv-pant-three-repo-ai-agent-skills-architecture.md`. The triggering "absence" was
  itself a memory claim that I did not falsify before acting.
- **Correction 9** (post-compaction restated install): I told the operator "install the updated
  `multistage-skill-framework.skill` zip via Save-Skill UI" twice in one session, sourced
  from a stale "the operator action required" line in a context-summary that survived
  compaction. The skill was already installed.

**Common shape:** the *correction itself* (or *restatement itself*) inherited the trust
level of its source. When the source was memory or context-summary prose, the new claim
should have memory-level trust — but I treated it as ground truth because I was the one
authoring the next write.

**The fix:** verify-before-firing applies recursively. Stage 2.5's discipline does not
stop at the boundary of "Stage 2.5 emits a finding" — it follows the finding into Stage 5
auto-corrections, into the brief restatements in Stage 3, and into any rollup writeback.

### The rule

**Any claim about file or skill state that is about to be repeated, written, or acted
on — including by an auto-correction — gets one filesystem probe before the write.**

Three triggers always require a probe:

1. **Absence claims:** "X does NOT exist", "Y is missing", "skill Z is NOT installed", "no
   file at PATH". Probe: `ls PATH` or `test -e PATH` or `find ROOT -name NAME`.
2. **Pending-action claims:** "the operator action required: install / commit / send / approve
   / decide". Probe: the falsification of *whether the action is still required* — usually
   `ls` for the artifact the action would produce, or a `grep` for its imprint in
   downstream state.
3. **Post-compaction restatements:** anything that survives a context-summary boundary
   and gets restated. Treat the entire claim as memory-class until probed.

### `verify_correction()` checklist (apply before any Stage 5 mutation)

For each candidate correction queued in Stage 2.5:

```
1. What is the source claim being corrected? (write it down verbatim)
2. What is the falsification probe for the source claim?
   (ls / grep / test / find — the same shape as Stage 2.5 §1 probes)
3. Run the probe. Capture stdout + exit code.
4. Does the probe confirm the source is wrong (drift / contradicted)?
   YES → proceed to Stage 5 mutation, log probe output to
         memory-corrections.log alongside the correction body
   NO  → the correction is itself a false positive; do NOT mutate;
         log the false-positive to memory-corrections.log so the
         pattern is visible next session
   AMBIGUOUS → surface to the operator, do NOT auto-mutate
```

### Probe patterns for the three triggers

| Trigger | Source claim shape | Probe |
|---|---|---|
| Absence | "file X does NOT exist" | `ls X 2>&1 ; test -e X && echo EXISTS \|\| echo MISSING` |
| Absence | "skill Y is NOT installed" | `ls master-brain/skills/Y/SKILL.md 2>&1` — source-of-truth folder is authoritative; the platform-side install directory may be read-only and is not authoritative |
| Pending-action | "operator action required: install Z.skill" | `ls Z.skill 2>&1 ; ls master-brain/skills/Z/SKILL.md 2>&1` — both must exist for the install to be pending; both missing means already installed and zip cleaned up |
| Pending-action | "operator action required: commit X" | `git -C ROOT log --oneline -- PATH 2>&1 \| head -5` |
| Post-compaction restatement | "[anything from a prior context-summary]" | re-run the relevant Stage 2.5 §1 probe from scratch, do NOT trust the summary phrasing |

### Where the rule lands across the brief

- **Stage 2.5:** runs the recursion guard before queuing any finding for Stage 5.
- **Stage 5 (Memory Hygiene):** the `verify_correction()` checklist gates the
  log-and-mutate step; false-positives get logged-and-skipped, not log-and-mutated.
- **Stage 3 (Brief delivery):** any restatement of a "pending action" claim from
  prior-session prose is treated as memory and verified before printing.
- **Anywhere in-session:** any time a claim of the three trigger shapes is about to be
  *written* — to DASHBOARD, awareness, a rollup, the user message — verify first.

### Co-implementation with Cerebro Principles Framework

The recursion-rule is one write that satisfies four principles at once:

- **Reversibility (#5):** log-before-mutate already required; recursion-rule extends the
  log to include the probe output, so a rollback can reconstruct *why* the correction was
  considered necessary in the first place.
- **Observability (#6):** false-positive corrections become visible because they hit the
  log even when no mutation lands.
- **Reproducibility (#8):** the probe is the verifiable input; the correction (or its
  rejection) is reproducible from {source claim, probe command, probe output}.
- **Least-Privilege (#7):** Stage 5's mutation authority is scoped to "probe-confirmed
  drift only" — it cannot escalate from a memory-only signal.

### Anti-patterns

- **Trusting the context-summary across compaction.** Compaction is lossy by design. Any
  imperative phrasing surviving compaction ("you need to install X") is a memory claim.
- **Treating "I just authored this 30 seconds ago" as ground truth.** Correction 8
  (self-caught) showed that even in-session author-state can drift; glob first.
- **Logging the correction *after* the mutation.** Reversibility #5 says log first; the
  recursion-rule extends this — log the *probe* before the mutation too.

### Decision doc

Recursion-rule canonical reference: operator's decision log entry for the
stage 2.5 recursion guard.

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[2026-04-18-stage25-recursion-rule]]
- [[Awareness]]
- [[SKILL]]
- [[audit-self-drift-register]]
- [[awareness]]
- [[decisions]]
- [[feedback_check_skill_docs_before_config_guess]]
- [[feedback_cite_config_not_memory]]
- [[feedback_preempt_known_gaps]]
- [[project_ruflo_ingest_filter_gap]]
- [[rajiv-pant-three-repo-ai-agent-skills-architecture]]

<!-- AUTOLINK-END -->
