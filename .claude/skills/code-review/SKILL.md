---
name: code-review
description: "Review changed code for correctness, readability, testability, security, and adherence to project conventions. Checks multiple perspectives and flags issues with concrete suggestions."
allowed-tools: [Read, Glob, Grep, Bash, Agent]
---

# code-review — Multi-Perspective Code Review

Review the specified code (files, diff, or staged changes) from multiple perspectives, flagging issues with concrete suggestions.

## Steps

### 1. Determine what to review

- If the user specifies files or a diff range, use that.
- If nothing is specified, review the current uncommitted changes: run `git diff HEAD` (and `git diff --cached` for staged changes).
- Read every file that has changes. Do not review code you haven't read.

### 2. Read project conventions

Read `doc/dev.md` to load the current review checklist and project conventions. These are authoritative — violations are must-fix, not nits.

Also read `CLAUDE.md` for project-specific rules (Web UI rules, o11y conventions, etc.).

### 3. Review from each perspective

Evaluate every changed file against all perspectives listed in the "Code Review Checklist" section of `doc/dev.md`, plus the conventions defined earlier in that file (Principles, o11y, pytest, dotenv) and the project-specific rules in `CLAUDE.md`.

Only report findings that are actionable — skip a perspective if there's nothing to flag.

### 4. Report findings

Present findings grouped by file path. For each finding:

1. **File and line reference** — `path/to/file.py:42`
2. **Perspective** — which review lens caught it (e.g. Correctness, Convention)
3. **Issue** — one-line description
4. **Suggestion** — concrete fix or direction (show code when helpful)

Use the severity levels from `doc/dev.md`.

### 5. Summary

End with a brief summary:
- Total findings by severity
- Overall assessment (ship it / needs changes / needs rethink)
- If the code is clean, say so — don't invent issues.

## Rules

- Do not suggest changes you haven't verified against the actual code.
- Do not flag things that are already handled correctly.
- Do not add noise — if the code is good, the review should be short.
- Convention violations from `doc/dev.md` and `CLAUDE.md` are must-fix, not nits.
