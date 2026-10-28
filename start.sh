#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  docker run --rm -v "$PWD:/project" -w /project python:3.11-slim python scripts/setup.py
fi
docker compose up -d --build --wait --wait-timeout 240
printf '\nMo http://localhost:8010 (hoac APP_PORT trong .env). Tai khoan quan tri: xem .env\n'
