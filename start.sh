#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
export PYTHONPATH="${PWD}:${PYTHONPATH}"
exec python -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT}"
