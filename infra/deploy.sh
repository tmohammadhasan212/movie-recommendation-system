#!/bin/sh
set -eu
image_sha="$1"
test -n "$image_sha"
mkdir -p backups
docker-compose exec -T db pg_dump -U recsys -Fc recsys > "backups/recsys-$(date -u +%Y%m%dT%H%M%SZ).dump"
export RECSYS_IMAGE_SHA="$image_sha"
export RECSYS_API_IMAGE="ghcr.io/${GHCR_OWNER}/recsys-api:${image_sha}"
export RECSYS_WEB_IMAGE="ghcr.io/${GHCR_OWNER}/recsys-web:${image_sha}"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker-compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
curl --fail --retry 10 --retry-delay 3 https://${APP_DOMAIN}/health/ready
