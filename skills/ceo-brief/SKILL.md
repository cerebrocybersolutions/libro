---
name: ceo-brief
description: >
  CEO-level cross-department briefing for {{operator_name}} at {{company_name}}.
  Reads all department Brain sessions and decisions, synthesizes into a structured brief
  covering what moved, what's stuck, pending decisions, and upcoming deadlines.
  Use this skill whenever {{operator_name}} says: "brief me", "what's the state of the company",
  "morning brief", "company status", "what happened", "catch me up", "how are we doing",
  "daily brief", "what do I need to know", or at the end of any sessionend to close the loop.
  Also triggers on: "what's moving", "macro view", "give me a company update".
  This is the Chief of Staff brain — always run it when the operator needs a
  company-wide picture, even if they don't say "brief" explicitly.
  NOTE: backlog-lane intents (aging / pending / unresolved decisions) route to
  cross-dept-decisions, not here. See {brain_root}/AGENTS.md §Known DRY pairs.
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: ["brain-setup"]
    profile_vars: ["operator_name", "company_name", "brain_root", "operator_departments"]
---

# CEO Brief — Chief of Staff Skill

Synthesizes all active department activity into a CEO-level briefing. The
operator should never have to hunt across department Brains to know what's
happening — this skill does that for them.

---

## COMPANY PROFILE

```
Company:   {{company_name}}  |  {{company_type}}
Operator:  {{operator_name}} |  {{operator_email}}
Brain:     {brain_root}/
Dashboard: {brain_root}/mission-control/DASHBOARD.md
```

*Loaded from `~/.cerebro/profile.yaml` at runtime (populated by first-run wizard). Never prompt for this information.*

---

## BRAIN CHECK — Always Run First

Load before generating any brief:
1. `{brain_root}/mission-control/DASHBOARD.md` — current department status table and red flags
2. Last ops session from `{brain_root}/mission-control/sessions/` — any cross-dept decisions or context
3. `{brain_root}/mission-control/state/circuit-breakers.json` — orchestration routing health (only surface if open/half-open — see "Routing Health" below)

---

## THE 4 STAGES

Route based on what the operator asked for:

| Operator says | Stage | Reference |
|---|---|---|
| "brief me" / "what's happening" / morning | **Full Brief** | `references/stage1_full_brief.md` |
| "what decisions are pending" | **Decisions Only** | `references/stage2_decisions.md` |
| "how is [dept] doing" | **Dept Drill-Down** | `references/stage3_dept_drilldown.md` |
| "what's due soon" / deadlines | **Deadline Scan** | `references/stage4_deadlines.md` |

Default (no qualifier): run **Full Brief**.

---

## BRIEF OUTPUT FORMAT

Always use this exact structure — concise, scannable, no fluff:

```
## CEO Brief — [Day, Date]

### 🟢 What Moved
[Dept]: [1 line — what actually happened, concrete outcome]

### 🔴 What's Stuck / Red Flags
[Dept]: [1 line — what's blocked and why]

### ⚡ Decisions Needed From {{operator_name}}
1. [Decision] — [Dept] — aging X days
2. [Decision] — [Dept] — deadline context

### 📅 Upcoming Deadlines (next 14 days)
- [Date] | [item] | [Dept] | [Status]

### 🔌 Routing Health (orchestration stack)
- [tier / task-class] | [state: open / half-open] | [hours since open / probe due]

### 💡 One Insight
[Single most important observation — pattern, risk, or opportunity across departments]
```

Keep each section to 3 bullets max. If there's nothing to report in a section, omit it.
Give signal, not noise.

**Routing Health is OFF by default.** Include it ONLY when the circuit-breaker state
file at `{brain_root}/mission-control/state/circuit-breakers.json` has one or more entries
in state `open` or `half-open`. If every breaker is `closed` (or the file is absent),
omit the section entirely.

---

## KEY RULES

1. **Read the actual session files, not just DASHBOARD.md.** The dashboard is a snapshot;
   sessions have the real detail. Always read the last 1–2 session entries from each dept
   that has been active in the last 7 days.

2. **Surface aging decisions.** Any decision that's been open for 7+ days without resolution
   is a red flag. Name the decision, name the department, name how many days it's been open.

3. **Never generate a brief without reading the Brain first.** A brief written from memory
   is stale by definition. Always load fresh context.

4. **One Insight is required.** Don't skip it. This is the Chief of Staff's job — connecting
   dots the operator might not see because they're heads-down in a single department.

5. **If a department has had no sessions in 7+ days, flag it.** Dormant departments aren't
   moving. Check `{brain_root}/mission-control/DASHBOARD.md` for dept posture context before
   recommending activation of any dept marked as deprioritized.

6. **Check circuit-breaker state on every full brief.** If any breaker is open or
   half-open, the orchestrator is diverting traffic — surface it in "Routing Health"
   with tier, task-class, state, and hours-since-opened.

---

## DEPARTMENT PATHS — Read These for Full Briefs

```
{operator_departments} — configured in brain.config.yml at install time

# Example structure:
#   {dept}/brain/sessions/           ← session logs
#   {dept}/brain/decisions/decisions.md   ← dept decision log
#   mission-control/sessions/           ← ops/cross-dept sessions
#   mission-control/decisions/          ← company-wide decisions
```

*All paths relative to `{brain_root}` (populated by first-run wizard at install time).*

---

## RENDER TARGETS

ceo-brief is the **engine** for cross-department briefing. The synthesis step
(load Brain, score aging, extract insight) is target-agnostic. The **render**
step varies by surface:

| Target | Consumer | Format | Status |
|---|---|---|---|
| **Text brief** | Chat session, sessionend/sessionstart ritual | Markdown per BRIEF OUTPUT FORMAT above | ✅ shipping |
| **HTML dashboard** | Operator's local browser | Interactive HTML with expandable dept cards + decision-queue widget + deadline timeline | 🟡 building |
| **Export artifact** | Exec summary, one-pager | Document output | 🔴 deferred |

**Rule:** the Brain → synthesis step is a single code path. Adding a render target
means extending the render step only, not re-reading the Brain.

---

## AFTER THE BRIEF

Always offer:
> "Want to drill into any department, or should I surface the aging decisions list?"

If the operator says yes to aging decisions, run Stage 2 (Decisions Only) inline.

---

## Scope Contract

| Dimension | Scope |
|-----------|-------|
| Read paths | All dept session folders (`{dept}/brain/sessions/`), `{brain_root}/mission-control/awareness.md`, `{brain_root}/mission-control/DASHBOARD.md`, `{brain_root}/mission-control/decisions/`, `~/.cerebro/profile.yaml` |
| Write paths | **None.** Read-only synthesizer — renders current state, never mutates it. |
| MCP / tool surface | Python stdlib for brief synthesis; HTML rendering for dashboard (localhost-only) |
| Network egress | None for text brief; dashboard uses localhost rendering only |
| Surface | Claude Code |
| Credentials | None for text brief; dashboard reads `~/.cerebro/profile.yaml` for operator identity |
| Escalation trigger | If dept session frontmatter drift ≥20%, emit `[DRIFT]` warning to stderr |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[DASHBOARD]]
- [[awareness]]
- [[decisions]]
- [[stage1_full_brief]]
- [[stage2_decisions]]
- [[stage3_dept_drilldown]]
- [[stage4_deadlines]]

<!-- AUTOLINK-END -->
