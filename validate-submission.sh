#!/usr/bin/env bash
set -euo pipefail

SPACE_URL="${1:?Usage: ./validate-submission.sh <space-url> [env-dir]}"
ENV_DIR="${2:-.}"
SPACE_URL="${SPACE_URL%/}"

run_openenv_validate() {
  if command -v openenv >/dev/null 2>&1; then
    openenv validate --url "$SPACE_URL" --verbose
    return
  fi

  if [ -x "../.venv/Scripts/openenv.exe" ]; then
    ../.venv/Scripts/openenv.exe validate --url "$SPACE_URL" --verbose
    return
  fi

  echo "FAIL: openenv CLI not found in PATH or ../.venv/Scripts/openenv.exe"
  exit 1
}

echo "[1/3] Checking HF Space is live and reset endpoint responds"
RESET_CODE="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SPACE_URL/reset" -H "Content-Type: application/json" -d '{}')"
if [ "$RESET_CODE" != "200" ]; then
  echo "FAIL: Expected /reset HTTP 200, got $RESET_CODE"
  exit 1
fi
echo "PASS: /reset returned 200"

echo "[2/3] Building Docker image (timeout 600s when available)"
if command -v timeout >/dev/null 2>&1; then
  timeout 600 docker build -t submission-check "$ENV_DIR"
else
  docker build -t submission-check "$ENV_DIR"
fi
echo "PASS: docker build succeeded"

echo "[3/3] Running openenv validate"
run_openenv_validate
echo "PASS: openenv validate succeeded"

echo "All pre-submission checks passed."
