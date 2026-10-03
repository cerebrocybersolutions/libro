---
name: decision
description: >
  Takes a yes/no question plus the facts and returns a verdict with the reason
  behind it. Use when you want a recommendation you can act on, not a pile of
  information. Trigger on: "decision skill", "should I", "make the call",
  "go or skip", "yes or no on this", "give me a verdict".
audience: operator
metadata:
  libro:
    libro_ready: true
    requires: []
    profile_vars: []
---

# Decision

Most AI hands you information. This skill hands you a call. Give it a question with
a yes or no answer and the facts it needs, and it weighs them against your criteria
and returns a verdict with the reason behind it.

## What it does

1. Takes your question and the facts you give it.
2. Weighs the facts against the criteria you set.
3. Returns a verdict: yes or no, go or skip.
4. Gives the one or two reasons that drove the call, so you can sanity-check it.
5. Says what fact would flip the verdict, so you know what to double-check.

## Scope

- **Reads:** the question and facts you provide, plus any file you point it at.
- **Writes:** nothing by default. Ask it to log the decision to your Brain's `decisions/decisions.md` if you want a record.
- **Reaches:** nothing. This skill reasons over what you give it.

## How to use it

Tell your AI:

> Use the decision skill. Question: `<yes/no question>`. Facts: `<the facts>`. My criteria: `<what matters>`. Give me the verdict and the reason.

Examples:

> Use the decision skill. Question: should I take this meeting? Facts: `<who, why, when>`. Criteria: it moves a real project forward or I owe the person. Verdict and reason.

> For each item in today's brief, use the decision skill. Question: is this worth an hour this week? Criteria: it serves a current goal and nobody else will do it. Return go or skip and one reason each.

## Make it yours

- Point it at any recurring yes/no you face. This is the step that turns a chatbot into something that does work.
- Stack it on the daily brief: the brief ranks the items, decision calls each one.
- Keep the criteria short and honest. Vague criteria give vague verdicts.
- Log the calls you act on. A month later, memory-recall can show you which calls held up.

*Ships with the Libro `libro-starter` profile. Your AI. Your machine. Your rules.*
