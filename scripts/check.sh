#!/usr/bin/env bash
# Runs the offline checks of .github/workflows/checks.yml, for work not yet pushed.
# Every step runs even after one fails, and the failed ones are listed last.
#
# Not covered, because it needs Docker, a database or the network:
#   - the `db` tests, which CI runs without `-n`. Here only the offline layer runs: not db, not model.
#   - `uv sync --locked` is replaced by `uv run --locked --extra dev`, which also fails on a stale uv.lock.
#
# A pass is recorded against the hash of the working tree, in the git directory, so a second
# run on an unchanged tree ends at once. --force runs the checks anyway.
set -u
cd "$(dirname "$0")/.." || exit 2

force=
case "${1:-}" in
  "") ;;
  --force) force=1 ;;
  *)
    echo "usage: scripts/check.sh [--force]" >&2
    exit 2
    ;;
esac

git_dir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || git_dir=
stamps="$git_dir/semantic-lab-checked"

# The tree a commit of everything here would have, ignored files aside. It works on a copy of
# the index, so the real index stays as it is. Prints nothing and fails outside a checkout.
working_tree() {
  local index copy status=1
  [ -n "$git_dir" ] || return 1
  index="$(git rev-parse --git-path index 2>/dev/null)" || return 1
  copy="$(mktemp "$git_dir/semantic-lab-check-index.XXXXXX")" || return 1
  if { [ ! -f "$index" ] || cp -p "$index" "$copy"; } &&
    GIT_INDEX_FILE="$copy" git add -A >/dev/null 2>&1; then
    GIT_INDEX_FILE="$copy" git write-tree
    status=$?
  fi
  rm -f "$copy"
  return $status
}

tree="$(working_tree)" || tree=

if [ -z "$force" ] && [ -n "$tree" ] && [ -e "$stamps/$tree" ]; then
  echo "==> already checked: this exact tree passed; --force runs the checks again"
  exit 0
fi

failed=
step() {
  local line
  line="$(printf '%q ' "$@")"
  echo "==> $line"
  "$@" || failed="$failed
    $line"
}

step uv run --locked --extra dev ruff check
step uv run --locked --extra dev mypy
step uv run --locked --extra dev pytest -n auto -m "not db and not model"

if [ -n "$failed" ]; then
  echo "==> failed:$failed"
  # A forced run that fails takes back an earlier pass on this tree.
  [ -n "$tree" ] && rm -f "$stamps/$tree"
  exit 1
fi
echo "==> all checks passed"

# The hash is taken again because a file edited during the run may not be what the checks saw.
if [ -z "$tree" ]; then
  echo "==> could not hash the working tree, so this pass is not recorded"
elif [ "$(working_tree)" != "$tree" ]; then
  echo "==> the working tree changed during the run, so this pass is not recorded"
elif ! { mkdir -p "$stamps" && touch "$stamps/$tree"; }; then
  echo "==> could not record this pass in $stamps"
fi
