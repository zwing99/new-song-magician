# New Song Magician

Small CLI for Planning Center Services that:

- looks up folder IDs by name
- lists upcoming plans in a folder
- lists linked song items only
- flags songs that have not been scheduled in the last N years
- shows the last time they were scheduled in the folder for songs that do not need review
- can send the rendered report through Gmail to one or more recipients
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

Or use the Just recipes:

```bash
just sync
```

If you plan to send reports with Gmail, the Google client libraries are included in the main
dependencies. A first Gmail-enabled run will open a browser for OAuth consent and cache a token
locally.

## Quality Checks

Before considering a change complete, run the full validation suite:

```bash
just check
```

That runs formatting checks, linting, type checking, and tests.
Pytest is configured in `pyproject.toml` to run verbosely and print coverage.

Format:

```bash
uv run ruff format .
```

Lint:

```bash
uv run ruff check .
```

Type check:

```bash
uv run ty check
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

Email the human-readable report and still print it to stdout:

```bash
uv run python main.py review-folder 123456 \
  --email worship@example.com \
  --email music@example.com
```

Email the report without printing it locally:

```bash
uv run python main.py review-folder 123456 \
  --email worship@example.com \
  --no-print
```

Use an env var for the recipient list:

```bash
export PCO_REVIEW_FOLDER_EMAILS="worship@example.com music@example.com"
uv run python main.py review-folder 123456
```

Change the review threshold:

```bash
uv run python main.py review-folder 123456 --review-window-years 3
```

## Gmail Setup

To send email with the Gmail API, create OAuth credentials for a desktop app and point the CLI at
the downloaded client secrets file.

1. Create or select a Google Cloud project.
2. Enable the Gmail API for that project.
3. Configure the OAuth consent screen for your account or Workspace org.
4. Create an OAuth client ID for a Desktop app.
5. Download the client credentials JSON file.

Place the downloaded file somewhere local, then either use the defaults:

```bash
mv ~/Downloads/client_secret_*.json ./gmail-oauth-client-secret.json
```

Or configure explicit paths:

```bash
export PCO_GMAIL_CREDENTIALS_FILE=/absolute/path/to/client-secret.json
export PCO_GMAIL_TOKEN_FILE=/absolute/path/to/.gmail-token.json
export PCO_GMAIL_FROM="Worship Team <worship@example.com>"
```

On the first run that includes `--email`, the CLI starts a local browser-based OAuth flow using the
`https://www.googleapis.com/auth/gmail.send` scope. After you approve access, it writes the refresh
token cache to `PCO_GMAIL_TOKEN_FILE` or `.gmail-token.json` by default. Later runs reuse and
refresh that token automatically.

Useful Google references:

- Gmail send API: <https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send>
- Gmail sending guide: <https://developers.google.com/workspace/gmail/api/guides/sending>
- Gmail Python quickstart: <https://developers.google.com/workspace/gmail/api/quickstart/python>

## Scheduling With Cron

The repo includes a non-interactive wrapper script for cron and similar schedulers:

```bash
./run-from-cron.sh
```

That script:

- changes into the repo root
- loads `.envrc` if present
- uses `PCO_REVIEW_FOLDER_FOLDER_ID` if set, or accepts the folder ID as its first argument
- runs `review-folder` with `--no-print`

Example manual run:

```bash
./run-from-cron.sh
```

Or with an explicit folder ID:

```bash
./run-from-cron.sh 342915
```

Example cron entry for every Friday at 5:00 AM on a machine set to `America/Chicago`:

```cron
0 5 * * 5 cd /Users/zacoler/src/new-song-magician && ./run-from-cron.sh
```

If `uv` is not on cron's default `PATH`, use an explicit path in the cron entry or in the script
environment.

## Notes

The report checks each upcoming song against the most recent prior `song_schedule` from a previous plan within the specified folder before the current time. Future plans are ignored when determining the last scheduled occurrence. If the previous schedule is older than the review window, or no prior schedule exists in that folder, the song is marked `REVIEW`.

The CLI requires either `PCO_TOKEN` or both `PCO_APP_ID` and `PCO_SECRET`. If neither is provided, it exits with a usage error.

Logs use Python's default logging format. The default level is `WARNING`; pass `-v` for `INFO` or `-vv` for `DEBUG`. Normal report output and `--json-output` still stay on stdout.

Human-readable `review-folder` output prints by default. Pass `--no-print` to suppress stdout output,
which is useful when you only want to email the report. JSON output also respects `--no-print`.

The song title `Doxology` is always ignored and will never appear in the report.

Human-readable report output is rendered with the `tabulate` library using GitHub-flavored Markdown tables.
