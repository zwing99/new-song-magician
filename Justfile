set shell := ["zsh", "-cu"]

default:
  @just --list

sync:
  uv sync --group dev

format:
  uv run --group dev ruff format .

format-check:
  uv run --group dev ruff format --check .

lint:
  uv run --group dev ruff check .

lint-fix:
  uv run --group dev ruff check --fix .

typecheck:
  uv run --group dev ty check

test:
  uv run --group dev pytest

check: format-check lint typecheck test
