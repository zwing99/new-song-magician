set shell := ["zsh", "-cu"]

default:
  @just --list

sync:
  uv sync

format:
  uv run ruff format .

format-check:
  uv run ruff format --check .

lint:
  uv run ruff check .

lint-fix:
  uv run ruff check --fix .

typecheck:
  uv run ty check

test:
  uv run pytest

check: format-check lint typecheck test
