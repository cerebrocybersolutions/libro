---
name: daily-brief
description: >
  Reads one source you choose and hands back a short, ranked summary so you do not
  have to scroll. Use when you want a fast briefing on a feed of items: news, job
  or grant listings, a folder of notes, an inbox export, a reading pile.
  Trigger on: "daily brief", "brief me on", "rank these for me", "top 5 from",
  "what matters in", "summarize this feed".
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: []
    profile_vars: []
---

# Daily Brief

Your AI reads one source you care about and returns a short, ranked summary. It is
the first real task most people hand an AI they run themselves. Swap the source,
keep the shape, and this one skill covers a dozen jobs.

## What it does

1. Reads the source you point it at: a URL, a file, a folder, or pasted text.
2. Pulls out the items that matter and drops the noise.
3. Ranks them by how much they matter to you, using the priorities you set.
4. Returns a short brief: the top items, one line each, most important first.

## Scope

- **Reads:** the one source you name. Nothing else.
- **Writes:** nothing by default. Ask it to save the brief to a file if you want a record.
- **Reaches:** the network only if your source is a URL.

## How to use it

Tell your AI:

> Run the daily brief on `<your source>`. I care about `<what matters to you>`. Give me the top 5, one line each, ranked.

Examples:

> Run the daily brief on my `notes/` folder. I care about open questions and anything with a due date. Top 5, ranked.

> Run the daily brief on this week's newsletter export. I care about anything that changes the tools I use. Top 5, one line each, with the link.

## Make it yours

- Change the source line and you have a new skill: a job feed, a grants feed, a competitor watch, a reading pile.
- Tell it the format you want: bullets, a table, or a paragraph.
- Once you trust the ranking, ask it to save each brief as a dated file in your Brain so memory-recall can find it later.
- Pair it with the `decision` skill: the brief ranks the items, decision makes a call on each one.

*Ships with the Libro `libro-starter` profile. Your AI. Your machine. Your rules.*
