---
name: wit
description: "Record a small idea or design thought to doc/wits.md. Use when the user has a loose idea, observation, or future-facing thought they want to capture."
allowed-tools: [Read, Edit, AskUserQuestion]
---

# wit — Capture a design thought

The user has an idea or observation they want to land in `doc/wits.md`. Your job is to **interview** them until the intent is sharp, then write a concise entry.

## The file

Read `doc/wits.md` first to understand the existing format and entries.

Entries live under dated `##` sections, sorted date DESC (newest at top, right after the header block). Each entry is a checkbox line followed by indented detail lines.

## Interview

The user may provide the idea inline (e.g. `/wit we should cache device state`) or just invoke `/wit` bare.

Either way, ask clarifying questions using AskUserQuestion until you can answer ALL of these:

1. **What** — the concrete idea (feature, API shape, behavior, constraint)
2. **Why** — the motivation or problem it solves
3. **Decisions** — any choices already made or explicitly deferred

Keep the interview short. 1-3 questions max. If the user's initial description already covers everything, skip straight to writing. Do NOT over-interview obvious ideas.

## Write the entry

Each entry must be **very concise** — this is a scratchpad, not a design doc. But it must not lose intent, rationale, or decisions.

Format:

```markdown
## YYYY-MM-DD

- [ ] one-line summary of the idea
    — detail line: rationale, constraints, decisions. Use em-dash prefix for continuation lines. Multiple detail lines are OK if needed, but keep each short.
```

If there are already entries under today's `## YYYY-MM-DD` section, append to that section instead of creating a duplicate date header.

### Rules

- Use today's date. Get it from context or `date +%Y-%m-%d`.
- Sort sections date DESC — newest `##` section goes first (right after the file's top-level header block ending at the first `##`).
- Never modify existing entries.
- Never mark entries as done (`[x]`).
- The summary line should be concrete enough that someone reading it months later understands the idea without expanding context.
