# Products — Dept CLAUDE.md (starter)

*Dept-scoped front door for the Products project. Overrides workspace-root `CLAUDE.md` for product sessions.*

*Last updated: (operator: populate on first edit).*

---

## Dept folder layout

```
products/
├── CLAUDE.md            # this file — dept front door
├── brain/               # dept Brain (sessions, decisions, drafts, pipeline)
│   ├── sessions/
│   ├── decisions/
│   ├── drafts/
│   └── pipeline/current-state.md
└── (operator: add product-line sub-folders here, e.g. one folder per shipped product)
```

(operator: populate — adjust layout to match your dept's actual structure)

---

## Mission

(operator: populate — one paragraph. What is this dept's commercial output? Who is the customer? What is the line between this dept and the others?)

## Current state

(operator: populate — 3-6 bullets. What is shipped? What is in build? What is blocked and on whom?)

## Canonical files for this dept

- `products/brain/sessions/YYYY-MM-DD-products.md` — session notes
- `products/brain/decisions/decisions.md` — decision log (top-append, newest-first)
- `products/brain/drafts/` — pre-ship packaging drafts
- (operator: add any per-product canonical docs, e.g. install runbooks, tuning playbooks)

## Dept non-negotiables (beyond root)

1. (operator: populate — what rule applies inside this dept that doesn't apply company-wide? Example: "Every shipped product must pass an externalization gate before it leaves the workspace.")
2. (operator: populate — second rule, if any)

## Active skills

- (operator: list the skills this dept actively uses — keep aligned with mission-control/skills/)

## When to escalate out of Products

- **To the human operator:** (operator: populate — pricing, customer calls, naming, commercial terms)
- **To Ops:** (operator: populate — any change that affects more than just shipped product)
- **To other depts:** (operator: populate — which depts feed this one?)

## Known gotchas

- (operator: populate — fill this in as you accumulate them; one line per gotcha is enough)

## Cross-dept notes

- (operator: populate — which depts are upstream/downstream of this one?)

<!-- AUTOLINK-START — Obsidian wikilink graph backfill (idempotent; safe to re-run) -->

## References (auto-wikilinks)

- [[YYYY-MM-DD-products]]
- [[current-state]]
- [[decisions]]

<!-- AUTOLINK-END -->
