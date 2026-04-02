# AGENTS

## Purpose

This repo contains a Planning Center Services CLI for reviewing upcoming plan songs within a folder.

## Working Rules

- Keep changes small and targeted.
- Prefer updating existing code over adding parallel code paths.
- Preserve the current CLI behavior unless the task explicitly changes it.
- Keep human-readable output on stdout and progress logging on stderr.
- Keep this `AGENTS.md` file up to date when repo workflow, tooling, or completion expectations change.

## Completion Standard

A feature or bug fix is not complete until it has been validated locally.

Run:

```bash
just check
```

That must pass before considering work complete. It covers:

- formatting check
- linting
- type checking
- pytest unit tests with coverage output

If you intentionally skip any part of validation, call that out clearly.

## Testing Guidance

- Add or update pytest coverage for behavior changes.
- Prefer mocking Planning Center API calls in tests rather than hitting the network.
- Cover edge cases when business rules change, especially folder scoping, future-plan handling, and never-scheduled songs.

## Tooling

- Use `just` recipes when available.
- Use `uv` for Python environment and command execution.
- Use Ruff for formatting and linting.
- Use `ty` for type checking.
