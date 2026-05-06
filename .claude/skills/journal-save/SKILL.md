---
name: journal-save
description: "Please create or update journals/YYYYMMDD-{pid}-{topic}.md to document this session's work. Especially the intention, investigations, quirks, experiments, actual changes."
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# journal-update — Document This Session's Work

Create or update a journal entry capturing what happened in this conversation — the intent, investigations, discoveries, quirks, experiments, and actual changes made.

## Steps

### 1. Determine the journal filename

The filename format is: `journals/YYYYMMDD-p{PID}-{topic}.md`

- Get the Claude Code PID via `echo $PPID` (stable across all bash calls in a session)
- Infer a 2-3 word kebab-case topic from the session's work (e.g. `ws-protocol`, `webui-layout`, `executor-refactor`). Prefer the verb-object pattern. The topic should always be inferable from the conversation — never use `unknown`.

Example: `journals/20260324-p3593122-ws-protocol.md`

### 2. Find or create the journal file

One PID may have multiple journals (the user can `/clear` and start a new topic within the same Claude Code process). Search for all journals with this PID:

```
journals/*-p${PPID}-*.md
```

If matches exist:
1. Read the first ~10 lines of each match (frontmatter + title) to understand its topic
2. If the current session's work fits an existing file's topic, update that file (append a new dated section — don't rewrite history)
3. If the current work is a clearly different topic from all existing files, create a new file

If no matches exist, create a new file.

### 3. Gather context

Run `echo $HOST $USER` to find hostname and username to populate the frontmatter with. Then collect the following from the conversation history — do NOT run extra exploratory commands:

- **Intent**: What did the user ask for? What was the goal?
- **Investigations**: What did we read, search, or explore to understand the problem?
- **Discoveries / Quirks**: Anything surprising, non-obvious, or worth remembering (gotchas, undocumented behavior, edge cases).
- **Experiments**: Anything we tried that didn't work, and why.
- **Changes**: What files were actually created, modified, or deleted? Summarize the substance of each change.
- **Open threads**: Anything unfinished, deferred, or worth revisiting.

### 4. Write the journal entry

Use this template:

```markdown
---
date: {YYYY-MM-DD HH:MM}
branch: {current git branch}
host: {hostname}
user: {username}
tldr: {One-sentence summary of the session's outcome}
---

# Journal: {brief title}

## Intent

{What the user wanted to accomplish.}

## What happened

{Narrative of the work — investigations, key decisions, pivots. Keep it concise but useful to future-you skimming old entries. Use subsections if the session covered multiple distinct topics.}

## Discoveries / Quirks

{Bullet list of non-obvious things learned. Omit this section if nothing surprising came up.}

## Changes

{Bullet list of files changed and what was done to each. Group by topic if the session touched multiple areas.}

## Open threads

{Anything left unfinished or worth revisiting. Omit if everything is wrapped up.}
```

### 5. Guidelines

- Be concise but specific. The journal is for the user to skim later, not a transcript.
- Focus on *why* and *what was surprising*, not mechanical play-by-play.
- Use code references (`file:line`) where they help.
- If updating an existing entry, append a new dated section rather than rewriting history.
- Don't editorialize or add filler — if a section has nothing useful, omit it.
