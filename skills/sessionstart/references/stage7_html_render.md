# Stage 7 — HTML Render (cerebro-ops theme)

Added 2026-05-11 (Parity #2 — skills track architecture: cerebro-ops theme is house style for operator-facing HTML, used by `full-business-audit`, audit reports, and Command Center). sessionstart's text brief stays as-is in chat (Reversibility #5 — additive); HTML is the archivable / shareable artifact.

## Inputs

The HTML render consumes the same synthesized state Stage 3 already produced:
- Department + session shape (Stage 1)
- Dept CLAUDE.md framing (Stage 1.5)
- Brain reads + infra state (Stage 2)
- Ground-truth verification results + drift findings (Stage 2.5)
- Memory hygiene corrections (Stage 5)
- Cross-dept flags (Stage 4)

**Reproducibility #8 — render-target separation.** Synthesis is target-agnostic. Markdown brief and HTML render BOTH consume the same Stage 1–6 state. If they diverge, that's a render-layer drift bug.

## Rule

**Read the operator's house theme file first** (typically `master-brain/themes/house.md` or equivalent) before generating HTML. Drop the `:root` token block into `<style>` verbatim. Use `var(--*)` references throughout — never inline hex literals.

## Output Path

```
master-brain/state/briefs/{YYYY-MM-DD}-{dept}-sessionstart.html
```

If multiple sessionstarts fire on the same date (rare — Stage 0 short-circuit usually catches reopens), append `-{HHMM}` suffix: `2026-05-11-ops-sessionstart-1715.html`.

## Render Skeleton

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Session Brief — {{dept}} — {{date}}</title>
  <style>
    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --surface2: #21262d;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #3fb950;
      --yellow: #d29922;
      --orange: #e3b341;
      --red: #f85149;
      --purple: #bc8cff;
    }
    * { box-sizing: border-box; }
    body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.6; margin: 0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 32px 40px; }
    h1 { color: #fff; font-size: 24px; margin: 0 0 8px; }
    h2 { color: #fff; font-size: 18px; margin: 40px 0 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
    h3 { color: #fff; font-size: 16px; margin: 24px 0 12px; }
    .meta { color: var(--text-muted); font-size: 13px; margin-bottom: 24px; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px 24px; margin: 16px 0; }
    .card.muted { background: var(--surface2); }
    table { width: 100%; border-collapse: collapse; margin: 8px 0; }
    th { background: var(--surface2); color: var(--text); text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
    td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
    code, .mono { font-family: 'SF Mono', Menlo, Consolas, monospace; background: var(--surface2); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
    .badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }
    .badge-green  { background: rgba(63,185,80,0.15);  color: #3fb950; border: 1px solid rgba(63,185,80,0.3); }
    .badge-yellow { background: rgba(210,153,34,0.15); color: #d29922; border: 1px solid rgba(210,153,34,0.3); }
    .badge-red    { background: rgba(248,81,73,0.15);  color: #f85149; border: 1px solid rgba(248,81,73,0.3); }
    .badge-blue   { background: rgba(88,166,255,0.15); color: #58a6ff; border: 1px solid rgba(88,166,255,0.3); }
    .badge-purple { background: rgba(188,140,255,0.15); color: #bc8cff; border: 1px solid rgba(188,140,255,0.3); }
    ul { padding-left: 20px; margin: 8px 0; }
    li { margin: 4px 0; }
    a { color: var(--accent); }
    .footer { color: var(--text-muted); font-size: 12px; margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border); }
  </style>
</head>
<body>
  <div class="container">
    <h1>Session Brief — {{dept_display}} <span class="badge badge-green">{{state}}</span></h1>
    <div class="meta">{{date}} · session_shape: <code>{{shape}}</code> · {{operator_name}}</div>

    <!-- Memory Drift block — only render if Stage 2.5 found drift -->
    {{#drift_findings}}
    <h2>Memory Drift — Auto-Surfaced</h2>
    <div class="card">
      <table>
        <tr><th>Claim</th><th>Ground truth</th><th>Action</th></tr>
        {{#each drift}}
        <tr><td>{{old_claim}}</td><td>{{finding}}</td><td><span class="badge badge-{{tag_color}}">{{tag}}</span> {{action}}</td></tr>
        {{/each}}
      </table>
    </div>
    {{/drift_findings}}

    <h2>Infrastructure Snapshot</h2>
    <div class="card">{{infrastructure_snapshot_html}}</div>

    <h2>Incoming State</h2>
    <div class="card">{{incoming_state_html}}</div>

    <h2>Open Loops</h2>
    <div class="card">
      <ul>{{#each open_loops}}<li>{{this}}</li>{{/each}}</ul>
    </div>

    <h2>Pending Decisions</h2>
    <div class="card">{{pending_decisions_html_or_none}}</div>

    <h2>Pipeline Position</h2>
    <div class="card">{{pipeline_position_html}}</div>

    <h2>Cross-Dept Flags</h2>
    <div class="card">{{cross_dept_flags_html_or_omitted}}</div>

    <div class="footer">
      Rendered by <code>sessionstart</code> · theme <code>cerebro-ops</code> · source-of-truth: dept Brain + master-brain/awareness.md · regenerate by re-running <code>/sessionstart</code>
    </div>
  </div>
</body>
</html>
```

The double-curly placeholders are illustrative — the LLM authors the HTML inline at render time, dropping in the actual brief content. No template engine; this is a render contract, not runtime templating.

## Chat-side delivery

After the markdown brief, append a one-line link:

```
Brief also saved to [state/briefs/{date}-{dept}-sessionstart.html](master-brain/state/briefs/{date}-{dept}-sessionstart.html) (cerebro-ops theme).
```

## Conditional rendering

Sections obey the same hide-when-empty rule as the markdown brief:
- Memory Drift block — only if Stage 2.5 found drift
- Pending Decisions — `None` line if empty
- Cross-Dept Flags — omit the whole section if empty

## Layout selector (Phase 2 — 2026-05-17)

Two layouts ship under the same `cerebro-ops` theme — same tokens, same colors, same trust-tag chips. They differ only in the **Open Loops** section structure (the part operators actually scan first).

| Layout | When to pick | Open Loops render | Default |
|--------|--------------|-------------------|---------|
| `tabular` | Brief is short (≤ 5 open loops) or operator wants linear narrative | `<ul>` inside a `.card` | ✅ default |
| `kanban` | Brief has ≥ 6 open loops OR operator wants status-bucketed visual scan | `.kanban` grid + lanes | opt-in |

### Flag source — frontmatter

The selector is sourced from the latest closed session-note frontmatter (Stage 2 reads it during `LATEST_SESSION` parse) under an additive `render.layout` key:

```yaml
---
date: 2026-05-17
session_id: <slug>
dept: ops
session_shape: ops-infra
status: closed
render:
  layout: kanban   # default 'tabular' if absent
open_loops:
  - ...
---
```

Absence of `render.layout` ⇒ tabular default. Reversibility #5 — additive field, removing it falls back cleanly.

### Kanban skeleton

When `layout: kanban`, the Open Loops section replaces the `<ul>` block with a 4–5 lane grid. Lanes derive from open-loop status suffixes (the colon-tail convention already in use in session-note `open_loops:` frontmatter — `: queued`, `: blocked-on-X`, `: deferred`, `: in-progress`).

```html
<style>
  .kanban {
    display: grid;
    grid-template-columns: repeat(4, minmax(380px, 1fr));
    gap: 16px;
    overflow-x: auto;
  }
  .lane { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; display: flex; flex-direction: column; min-width: 0; }
  .lane-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 2px solid var(--border); }
  .lane-head .title { font-size: 14px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 0.8px; }
  .lane-head .count { font-size: 12px; color: var(--text-muted); }
  .lane-body { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
  .lane.lane-backlog .lane-head { border-bottom-color: var(--text-muted); }
  .lane.lane-ready    .lane-head { border-bottom-color: var(--accent); }
  .lane.lane-progress .lane-head { border-bottom-color: var(--purple); }
  .lane.lane-blocked  .lane-head { border-bottom-color: var(--red); }
  .lane.lane-done     .lane-head { border-bottom-color: var(--green); }
</style>
<div class="kanban">
  <div class="lane lane-backlog">
    <div class="lane-head"><span class="title">Backlog</span><span class="count">{{n_queued}}</span></div>
    <div class="lane-body">{{#each queued}}<div class="card">{{this}}</div>{{/each}}</div>
  </div>
  <div class="lane lane-progress">
    <div class="lane-head"><span class="title">In Progress</span><span class="count">{{n_in_progress}}</span></div>
    <div class="lane-body">{{#each in_progress}}<div class="card">{{this}}</div>{{/each}}</div>
  </div>
  <div class="lane lane-blocked">
    <div class="lane-head"><span class="title">Blocked</span><span class="count">{{n_blocked}}</span></div>
    <div class="lane-body">{{#each blocked}}<div class="card">{{this}}</div>{{/each}}</div>
  </div>
  <div class="lane lane-ready">
    <div class="lane-head"><span class="title">Deferred</span><span class="count">{{n_deferred}}</span></div>
    <div class="lane-body">{{#each deferred}}<div class="card">{{this}}</div>{{/each}}</div>
  </div>
</div>
```

### Lane bucketing rule

For each `open_loops[]` frontmatter entry, parse the colon-tail status and route:

| Status tail | Lane |
|-------------|------|
| `: queued` (default if no tail) | Backlog |
| `: in-progress` | In Progress |
| `: blocked-on-*` | Blocked (use full tail as sublabel) |
| `: deferred` | Deferred |
| `: ready` | Backlog (sorted to front) |

Done-lane intentionally omitted from sessionstart kanban — completed loops belong in the latest sessionend's "Accomplished" section, not the next session's open-loops snapshot.

### Reference template

Working prototype that already conforms to the kanban skeleton above:

- `master-brain/state/briefs/2026-05-16-EVE2-ops-sessionstart-kanban.html`

When rendering kanban, read that file as the visual reference (header bar + snapshot grid + lane structure). Other sections (Infrastructure Snapshot / Pending Decisions / Pipeline Position / Cross-Dept Flags) keep their tabular `.card` shape — Phase 2 only swaps the Open Loops section.

### Sessionend mirror

Sessionend Step 7.7 inherits this same selector verbatim — same frontmatter key, same lane bucketing, same prototype reference. See `master-brain/skills/sessionend/SKILL.md` §"Step 7.7 — Render HTML" → Layout selector subsection (added same date).

### Phase 3 (deferred)

Phase 3 = React + `kanban.db` interactive board (drag-and-drop, lane edits write back to session-note frontmatter). Phase 2 ships static HTML only. Decision to flip from static HTML to live React rests on whether operators actually use the kanban view enough to justify the runtime dependency.

## Trust tags

Per Reproducibility #8, each Stage 2.5 finding carries a trust tag (✅ verified / ⚠️ drifted / ❌ unverifiable). Render them as `badge-green` / `badge-yellow` / `badge-red` pills.

## Grade Color Mapping

If the brief surfaces an audit grade or pipeline-position grade, follow the canonical mapping from `audits/theme-cerebro-ops.md` §Grade Color Mapping:

| Grade | Token |
|---|---|
| A / A− | `--green` |
| B / B+ / B− | `--accent` |
| C / C+ | `--yellow` |
| D | `--orange` |
| F | `--red` |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[awareness]]
- [[feedback_house_style_html_reports_theme_cerebro_ops]]
- [[theme-cerebro-ops]]

<!-- AUTOLINK-END -->
