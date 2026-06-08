#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

docker compose -f docker-compose.yml --profile jobs run --rm datajob-klauwscore

