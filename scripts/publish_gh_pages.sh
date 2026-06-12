#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-public}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source directory not found: $SOURCE_DIR" >&2
  exit 1
fi

REMOTE_URL="$(git config --get remote.origin.url || true)"
if [[ -z "$REMOTE_URL" ]]; then
  echo "No origin remote configured." >&2
  exit 1
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

cp -R "$SOURCE_DIR"/. "$WORK_DIR"/
cd "$WORK_DIR"

git init --quiet
git checkout -b gh-pages --quiet
git config user.name "${GIT_AUTHOR_NAME:-github-actions[bot]}"
git config user.email "${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
git add -A

if git diff --cached --quiet; then
  echo "No generated files to publish."
  exit 0
fi

COMMIT_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
git commit --quiet -m "Publish market data ${COMMIT_TIME}"

if [[ -n "${GITHUB_TOKEN:-}" && -n "${GITHUB_REPOSITORY:-}" ]]; then
  REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
fi

git remote add origin "$REMOTE_URL"
git push --force origin gh-pages
