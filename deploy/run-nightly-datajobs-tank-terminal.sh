#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

COMPOSE_FILES="-f docker-compose.yml"
ENV_FILE="deploy/dashboard.env"

docker compose --env-file "$ENV_FILE" $COMPOSE_FILES --profile jobs run --rm datajob-tank-terminal

