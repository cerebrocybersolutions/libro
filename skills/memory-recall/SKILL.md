---
name: memory-recall
description: >
  Reads your Libro Brain (session notes, decisions, awareness, dashboard) and tells
  you what you did or decided over a time window. Read-only and fully local. Use
  when you ask "what did I work on last week", "what did we decide about X", or
  "what is still open". Trigger on: "memory recall", "what did I do", "recap my week",
  "what did we decide", "what's still open".
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: ["brain-setup"]
    profile_vars: []
---

# Memory Recall

The skill that proves the memory is real. Your AI reads the Brain that Libro set up
on your machine and tells you what you have done, decided, or left open over a
window of time. Nothing is uploaded. The Brain sits on your disk.

## Where it reads

From your Brain root (the `--target` you installed into, `~/cerebro-brain` by default):

- `master-brain/sessions/` and each department's `brain/sessions/`: one note per work session, written by `sessionend`.
- `master-brain/decisions/decisions.md` and each department's `brain/decisions/`: the decisions log.
- `master-brain/awareness.md` and `master-brain/DASHBOARD.md`: the current picture.

On day one these are mostly empty templates, so recall has little to say. It gets
sharper every time you close a session with `sessionend`.

## What it does

1. Lists the session notes and decision entries in the window you ask for (file dates and the dates inside the notes).
2. Reads them, plus awareness and the dashboard for the current state.
3. Returns a short recap: what you worked on, what you decided, what is still open.
4. Quotes the file it got each point from, so you can open it and check.

## Scope

- **Reads:** your Brain folder only. Nothing leaves your machine.
- **Writes:** nothing. This skill is read-only by design.
- **Reaches:** nothing. Fully local.

## How to use it

Tell your AI:

> Use memory recall. What did I work on last week? Give me a short recap and anything still open.

Other ways to ask:

> What did we decide about pricing? Read the Brain and quote the decision with its file.

> Summarize everything in the Brain from this month, grouped by department.

> What did I say I would do but have not closed?

## Make it yours

- The more you write to the Brain, the sharper recall gets. Close each work session with `sessionend`, or add one line to the day's session note yourself.
- If you keep notes somewhere else too, name that folder in your ask and recall will read it alongside the Brain.
- Ask it to find gaps: loops opened in one session and never mentioned again.

*Ships with the Libro `libro-starter` profile. Your AI. Your machine. Your rules.*
