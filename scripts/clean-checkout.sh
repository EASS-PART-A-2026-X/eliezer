#!/usr/bin/env bash
# scripts/clean-checkout.sh: do what a grader does, on a fresh clone of one commit.
set -euo pipefail

if [ -n "$(git status --porcelain)" ]; then
  echo "FAIL: uncommitted changes. The grader cannot see them; commit first."
  git status --short
  exit 1
fi
sha="$(git rev-parse HEAD)"
echo "Testing commit $sha"
if [ "$sha" != "$(git rev-parse '@{u}' 2>/dev/null || true)" ]; then
  echo "WARNING: HEAD is not on GitHub yet (unpushed, or no upstream). Push it."
fi

source="$(git rev-parse --show-toplevel)"
if [ "${CLONE_FROM:-}" = "origin" ]; then
  source="$(git remote get-url origin)" # what the grader clones
fi
work="$(mktemp -d)"
project="clean-checkout-$$" # own project name: own containers, own volume
export BACKEND_PORT="${BACKEND_PORT:-8000}" FRONTEND_PORT="${FRONTEND_PORT:-8501}"

trap 'rm -rf "$work"' EXIT

git clone --quiet "$source" "$work" # committed files only: no .env, no .venv
cd "$work"
git checkout --quiet --detach "$sha" || {
  echo "FAIL: $sha is not in $source. Push it first."
  exit 1
}
if [ -e .env ]; then
  echo "FAIL: .env is committed. Rotate every key in it, then remove it."
  exit 1
fi
cp .env.example .env

cleanup() {
  status=$? # the exit status of the script, saved before anything else runs
  if [ "$status" -ne 0 ]; then
    echo "FAILED (exit $status). Last log lines from each service:"
    docker compose -p "$project" --project-directory "$work" logs --tail 80 || true
  fi
  docker compose -p "$project" --project-directory "$work" down -v --rmi local
  rm -rf "$work"
}
trap cleanup EXIT # from here on, also remove containers, volume and images

docker compose -p "$project" up --build --wait --wait-timeout 180
check() { curl --fail --silent --show-error --output /dev/null "$@"; }
check "http://localhost:$BACKEND_PORT/health"
check "http://localhost:$FRONTEND_PORT/_stcore/health"
check "http://localhost:$BACKEND_PORT/plants?q=rosemary"
check -F "photo=@ai-service/evals/images/rosemary.jpg;type=image/jpeg" \
  "http://localhost:$BACKEND_PORT/plants/identify"

for service in backend ai-service frontend; do
  (cd "$service" && uv sync --locked --quiet && uv run pytest --quiet)
done
echo "Clean checkout OK: $sha"
