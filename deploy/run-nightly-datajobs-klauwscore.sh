#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

docker compose --env-file .env -f docker-compose.yml --profile jobs run --rm datajob-klauwscore

