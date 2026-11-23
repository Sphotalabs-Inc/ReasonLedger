#!/usr/bin/env bash
# The release gate (docs/releasing.md): everything that must be green before a version is
# uploaded. A published version number can never be reused, so run this on a clean tree.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "error: working tree has uncommitted changes; uv build packages what is on disk" >&2
  exit 1
fi

# Untracked files elsewhere in a working copy are ordinary, so they are not refused above. Under
# packages/ they are not ordinary: a build reads the directory, not the git index, so an
# untracked file there can end up in a published archive.
if [ -n "$(git status --porcelain --untracked-files=all -- packages)" ]; then
  echo "error: untracked files under packages/ could be packaged; commit or remove them" >&2
  exit 1
fi

echo "==> ruff"
uv run ruff check packages
uv run ruff format --check packages

echo "==> mypy"
uv run mypy packages/core/src packages/cli/src packages/mcp/src

echo "==> phases 1-5"
uv run pytest -m "phase_1 or phase_2 or phase_3 or phase_4 or phase_5"

echo "==> dists"
./scripts/check_dists.sh

echo "==> Release gate passed"
