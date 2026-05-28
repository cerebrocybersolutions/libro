# Session-End HTML Render (cerebro-ops theme)

Added 2026-05-11 (Parity #2 — skills track architecture: cerebro-ops theme is house style for operator-facing HTML, used by `full-business-audit`, audit reports, and Command Center). sessionend's markdown summary still lands in the dept Brain at `sessions/YYYY-MM-DD-{topic}-{dept}.md` (Reversibility #5 — additive); HTML is the archivable / shareable render.

## Inputs

The HTML render consumes the same synthesized state the markdown session note already captures:
- Session frontmatter (`date`, `session_id`, `dept`, `session_shape`, `status`, `decisions_made`, `open_loops`, `principles_touched`)
- Accomplished list
- Decisions Made
- What Went Well / What Went Wrong / How to Improve
- Open Loops — Next Session
- Cross-Dept Notes
- Step 7.5 Writeback ribbon results (Lockstep #3 enforcement signals)
- Step 7.75 CC handoff status, if generated

**Reproducibility #8 — render-target separation.** Synthesis is target-agnostic. Markdown session note and HTML render BOTH consume the same Step 1–7 state. If they diverge, that's a render-layer drift bug.

## Rule

**Read the operator's house theme file first** (typically `master-brain/themes/house.md` or equivalent) before generating HTML. Drop the `:root` token block into `<style>` verbatim. Use `var(--*)` references throughout — never inline hex literals.

## Output Path

```
master-brain/state/briefs/{YYYY-MM-DD}-{dept}-sessionend.html
```

When multiple sessions for the same dept fire on the same date, the session-note filename already disambiguates with a topic slug (`2026-05-11-skill-automation-ops.md`). The HTML follows the same slug:

```
master-brain/state/briefs/{YYYY-MM-DD}-{topic}-{dept}-sessionend.html
```

## Render Skeleton

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Session End — {{dept_display}} — {{date}} — {{topic}}</title>
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
    .principle-pill { display: inline-block; background: rgba(188,140,255,0.15); color: #bc8cff; border: 1px solid rgba(188,140,255,0.3); padding: 2px 10px; border-radius: 20px; font-size: 12px; margin: 2px 4px 2px 0; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Session End — {{dept_display}} <span class="badge badge-blue">closed</span></h1>
    <div class="meta">
      {{date}} · <code>{{session_id}}</code> · shape: <code>{{session_shape}}</code> · {{operator_name}}
    </div>

    <h2>Accomplished</h2>
    <div class="card">
      <ul>{{#each accomplished}}<li>{{this}}</li>{{/each}}</ul>
    </div>

    <h2>Decisions Made</h2>
    <div class="card">{{decisions_made_html_or_none}}</div>

    <h2>What Went Well</h2>
    <div class="card muted">{{what_went_well_html}}</div>

    <h2>What Went Wrong</h2>
    <div class="card muted">{{what_went_wrong_html_or_none}}</div>

    <h2>How to Improve</h2>
    <div class="card muted">{{how_to_improve_html_or_none}}</div>

    <h2>Open Loops — Next Session</h2>
    <div class="card">
      <ul>{{#each open_loops}}<li>{{this}}</li>{{/each}}</ul>
    </div>

    <h2>Principles Touched</h2>
    <div class="card">
      {{#each principles_touched}}<span class="principle-pill">{{this}}</span>{{/each}}
    </div>

    <!-- Step 7.5 Writeback Guard ribbon — only render if ribbon was generated -->
    {{#writeback_ribbon}}
    <h2>Writeback Ribbon (Lockstep #3)</h2>
    <div class="card">
      <table>
        <tr><th>Surface</th><th>Status</th><th>Note</th></tr>
        {{#each ribbon}}
        <tr><td>{{surface}}</td><td><span class="badge badge-{{color}}">{{status}}</span></td><td>{{note}}</td></tr>
        {{/each}}
      </table>
    </div>
    {{/writeback_ribbon}}

    <!-- Step 7.75 CC handoff — only if dirty tree generated one -->
    {{#cc_handoff}}
    <h2>Claude Code Handoff (Step 7.75)</h2>
    <div class="card">
      <p>Commit-batch queued: <a href="../../handoffs/{{handoff_filename}}"><code>{{handoff_filename}}</code></a> <span class="badge badge-yellow">queued</span></p>
      <p>{{handoff_summary}}</p>
    </div>
    {{/cc_handoff}}

    <h2>Cross-Dept Notes</h2>
    <div class="card">{{cross_dept_notes_html_or_none}}</div>

    <div class="footer">
      Rendered by <code>sessionend</code> · theme <code>cerebro-ops</code> · source: <code>{{session_note_path}}</code> · regenerate by re-running <code>/sessionend</code>
    </div>
  </div>
</body>
</html>
```

The double-curly placeholders are illustrative — the LLM authors the HTML inline at render time. No template engine; this is a render contract, not runtime templating.

## Chat-side delivery

After the markdown wrap, append a one-line link:

```
Session also saved to [state/briefs/{date}-{topic}-{dept}-sessionend.html](master-brain/state/briefs/{date}-{topic}-{dept}-sessionend.html) (cerebro-ops theme).
```

## Conditional rendering

Sections obey the same hide-when-empty rule as the markdown session note:
- Decisions Made — `None` if empty
- What Went Wrong — omit card if empty
- How to Improve — omit card if empty
- Writeback Ribbon — omit if no ribbon generated
- CC handoff — omit if `git status` was clean
- Cross-Dept Notes — `None` if empty

## Trust tags / status badges

- Writeback Ribbon surface statuses: `PASS` → `badge-green`, `LAG` / `DRIFT` → `badge-yellow`, `FAIL` → `badge-red`
- CC handoff status: `queued` → `badge-yellow`, `fired` → `badge-green`, `parked` → `badge-blue`
- Session status: `closed` → `badge-blue` (we just closed it), `open` → `badge-yellow`

## Grade Color Mapping

If the session note carries a grade (audit close-out sessions do), follow the canonical mapping from `audits/theme-cerebro-ops.md` §Grade Color Mapping:

| Grade | Token |
|---|---|
| A / A− | `--green` |
| B / B+ / B− | `--accent` |
| C / C+ | `--yellow` |
| D | `--orange` |
| F | `--red` |

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[2026-05-11-skill-automation-ops]]
- [[feedback_house_style_html_reports_theme_cerebro_ops]]
- [[theme-cerebro-ops]]

<!-- AUTOLINK-END -->
