---
name: code-work
description: "Implement a milestone or task from a project plan. Reads the plan, picks up the next task, writes code + tests, runs them, and marks it done."
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent]
---

# code-work — Implement a Plan Task

Pick up a milestone or task from a project's plan doc, implement it with tests, and mark it done.

## Steps

### 1. Load the plan and conventions

- Read the plan doc specified by the user.
- Read `doc/dev.md` for project-wide coding conventions.
- Read `CLAUDE.md` for project-specific rules.
- Read the `Makefile` to understand how to run tests and install deps.

### 2. Determine what to work on

- If the user specifies a task or milestone, use that.
- If not, pick the first unchecked `- [ ]` item in the plan.
- Read all existing code that the task will touch or depend on before writing anything.

### 3. Implement

Write code that follows these rules:

- **Readable, testable, minimal.** Only implement what the task asks for. Don't refactor surrounding code, add speculative features, or over-abstract.
- **Match existing patterns.** Read neighboring code and follow the same style, naming, imports, and structure. New code should look like it was written by the same person.
- **Stable APIs.** Exported functions get a short docstring and a stable signature. Internal helpers do not need docstrings.
- **Comments are for "why".** Use code for "what" and "how". Only comment when the reason behind a choice isn't obvious.
- **Follow plan-level notes.** The plan doc may include project-specific conventions or constraints — read and follow them.

### 4. Write tests

Every task that adds or changes behavior must include tests.

- Test file naming: `TESTEE_test.py`.
- Tests live **beside** the testee module (same directory), not in a separate `tests/` tree.
- Test behavior, not implementation. Prefer round-trip tests over mocking internals.
- Keep tests fast and independent.

### 5. Run tests

- Run `make test` to execute the test suite.
- All tests must pass before the task is considered done. If a test fails, fix the code or the test — don't skip or delete it.
- Run `make format` before finishing.

### 6. Update the plan

In the plan doc, change `- [ ]` to `- [x]` for the completed task. Do not modify other tasks.

### 7. Summarize

Tell the user:
- Which task was completed
- What files were created or changed
- Any design decisions you made (and why)
- Anything you noticed that affects upcoming tasks

## Rules

- Do not start coding before reading the existing code that your task touches.
- Do not change code outside the scope of the current task.
- Do not mark a task done if tests don't pass.
- If a task is ambiguous or blocked by an unresolved design decision in the plan, stop and ask the user rather than guessing.
- One task per invocation. If the user asks for a whole milestone, work through tasks sequentially — finish and verify each one before starting the next.
