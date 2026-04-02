# AGENTS

## Purpose

This repo contains a Planning Center Services CLI for reviewing upcoming plan songs within a folder.

## Current Structure

- `main.py` is a thin entrypoint only.
- `run-from-cron.sh` is the non-interactive wrapper for scheduled runs that load repo env vars and invoke `review-folder`.
- `new_song_magician/cli.py` owns Click commands and logging setup.
- `new_song_magician/client.py` owns the Planning Center HTTP client.
- `new_song_magician/gmail.py` owns Gmail OAuth loading and email delivery.
- `new_song_magician/reporting.py` owns folder lookup, scheduling logic, filtering, and Markdown table rendering.
- `new_song_magician/models.py` owns shared dataclasses.
- Tests are split by concern into `tests/test_cli.py`, `tests/test_client.py`, `tests/test_gmail.py`, and `tests/test_reporting.py`.

## Working Rules

- Keep changes small and targeted.
- Prefer updating existing code over adding parallel code paths.
- Preserve the current CLI behavior unless the task explicitly changes it.
- Keep human-readable output on stdout and progress logging on stderr.
- When adding delivery channels like email, keep stdout output separately controllable from side effects.
- Keep local OAuth secrets and token caches out of git; prefer repo-local ignored paths configured through env vars.
- Scheduled automation should use `run-from-cron.sh` or an equivalent wrapper instead of assuming cron loads `.envrc`.
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
- Keep tests split by concern instead of rebuilding a monolithic test file.

## Logging

- Default log level is `WARNING`.
- `-v` enables `INFO`.
- `-vv` enables `DEBUG`.
- Keep human-readable report output on stdout; logging should not replace report output.

## Current Behavior Notes

- The report checks the last scheduled occurrence within the specified folder only.
- Future plans are ignored when deciding the last scheduled occurrence.
- `Doxology` is always ignored.
- Brand-new songs with no prior in-folder schedule should remain explicitly visible as needing review.
- Song history lookups use an in-memory per-run `lru_cache` for history candidates; avoid adding persistent caching unless there is a clear stale-data strategy.
- `review-folder` prints human-readable output by default and supports `--print/--no-print` to control stdout independently from email sending.
- Human-readable reports now include clickable Planning Center links for the folder dashboard, plans, songs, and prior plans.
- Email output is HTML-first, styled for broad email-client compatibility, and includes song links plus arrangement and scheduled-key details when present on the plan item.

## Future Guidance

- Do not switch to `aiohttp` by default. The current code is sync and mostly sequential, and `httpx` is adequate for that shape.
- If performance work is needed, first introduce bounded concurrency for independent song-history lookups and possibly plan-item fetches.
- If async concurrency is added later, re-evaluate whether `httpx.AsyncClient` is sufficient before considering an `aiohttp` rewrite.

## Tooling

- Use `just` recipes when available.
- Use `uv` for Python environment and command execution.
- This repo includes the default dependency groups in normal `uv` commands, so do not add `--group dev` unless that behavior changes.
- When dependencies change, update the lockfile and environment with `uv lock` and `uv sync`.
- The current local setup expects Gmail OAuth client secrets and token cache paths to come from env vars such as `PCO_GMAIL_CREDENTIALS_FILE` and `PCO_GMAIL_TOKEN_FILE`.
- Use Ruff for formatting and linting.
- Use `ty` for type checking.
