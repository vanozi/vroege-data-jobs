#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

COMPOSE_FILES="-f docker-compose.yml"
ENV_FILE="${DASHBOARD_ENV_FILE:-.env}"

docker compose --env-file "$ENV_FILE" $COMPOSE_FILES --profile tools run --rm db-migrate
docker compose --env-file "$ENV_FILE" $COMPOSE_FILES --profile jobs run --rm datajob-uniform-agri
docker compose --env-file "$ENV_FILE" $COMPOSE_FILES --profile jobs run --rm datajob-klauwscore
