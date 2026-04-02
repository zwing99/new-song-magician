# New Song Magician

Small CLI for Planning Center Services that:

- looks up folder IDs by name
- lists upcoming plans in a folder
- lists linked song items only
- flags songs that have not been scheduled in the last N years
- shows the last time they were scheduled in the folder for songs that do not need review
- supports `WARNING` by default, `INFO` with `-v`, and `DEBUG` with `-vv`
- renders report output as GitHub-flavored Markdown tables

## Setup

You need Planning Center Services API credentials before running the script.

Option 1, bearer token:

```bash
export PCO_TOKEN=...
```

Then run commands normally:

```bash
uv run python main.py review-folder 123456
```

Option 2, application ID and secret:

```bash
export PCO_APP_ID=...
export PCO_SECRET=...
```

Then run the same commands:

```bash
uv run python main.py review-folder 123456
```

You can also pass credentials inline instead of exporting env vars:

```bash
uv run python main.py --token "$PCO_TOKEN" review-folder 123456
uv run python main.py --app-id "$PCO_APP_ID" --secret "$PCO_SECRET" review-folder 123456
```

Install dependencies with `uv`:

```bash
uv sync
```

Install dev tools too:

```bash
uv sync --group dev
```

Or use the Just recipes:

```bash
just sync
```

## Quality Checks

Before considering a change complete, run the full validation suite:

```bash
just check
```

That runs formatting checks, linting, type checking, and tests.
Pytest is configured in `pyproject.toml` to run verbosely and print coverage.

Format:

```bash
uv run --group dev ruff format .
```

Lint:

```bash
uv run --group dev ruff check .
```

Type check:

```bash
uv run --group dev ty check
```

Equivalent `just` commands:

```bash
just format
just format-check
just lint
just lint-fix
just typecheck
just test
just check
```

## Find A Folder

```bash
uv run python main.py lookup-folder "Sunday Worship"
```

## Review Upcoming Plans

Next 30 days:

```bash
uv run python main.py review-folder 123456
```

All future plans:

```bash
uv run python main.py review-folder 123456 --all-future
```

JSON output:

```bash
uv run python main.py review-folder 123456 --json-output
```

Change the review threshold:

```bash
uv run python main.py review-folder 123456 --review-window-years 3
```

## Notes

The report checks each upcoming song against the most recent prior `song_schedule` from a previous plan within the specified folder before the current time. Future plans are ignored when determining the last scheduled occurrence. If the previous schedule is older than the review window, or no prior schedule exists in that folder, the song is marked `REVIEW`.

The CLI requires either `PCO_TOKEN` or both `PCO_APP_ID` and `PCO_SECRET`. If neither is provided, it exits with a usage error.

Logs use Python's default logging format. The default level is `WARNING`; pass `-v` for `INFO` or `-vv` for `DEBUG`. Normal report output and `--json-output` still stay on stdout.

The song title `Doxology` is always ignored and will never appear in the report.

Human-readable report output is rendered with the `tabulate` library using GitHub-flavored Markdown tables.
