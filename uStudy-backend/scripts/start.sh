#!/bin/sh

set -eu

: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8000}"
: "${UVICORN_WORKERS:=6}"
: "${UVICORN_LIMIT_CONCURRENCY:=600}"
: "${UVICORN_BACKLOG:=2048}"
: "${UVICORN_TIMEOUT_KEEP_ALIVE:=75}"
: "${UVICORN_LOG_LEVEL:=info}"

echo "Starting uvicorn with workers=${UVICORN_WORKERS}, limit_concurrency=${UVICORN_LIMIT_CONCURRENCY}, backlog=${UVICORN_BACKLOG}"

exec uvicorn main:app \
  --host "${UVICORN_HOST}" \
  --port "${UVICORN_PORT}" \
  --workers "${UVICORN_WORKERS}" \
  --limit-concurrency "${UVICORN_LIMIT_CONCURRENCY}" \
  --backlog "${UVICORN_BACKLOG}" \
  --timeout-keep-alive "${UVICORN_TIMEOUT_KEEP_ALIVE}" \
  --log-level "${UVICORN_LOG_LEVEL}"
