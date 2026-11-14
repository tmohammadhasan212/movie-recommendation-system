#!/bin/sh
set -eu
image_sha="${1:-}"
case "$image_sha" in
  *[!0-9a-f]*|'') echo "image SHA must be a full lowercase Git commit SHA" >&2; exit 2 ;;
esac
if [ "${#image_sha}" -ne 40 ]; then
  echo "image SHA must contain exactly 40 characters" >&2
  exit 2
fi
: "${GHCR_OWNER:?GHCR_OWNER is required}"
: "${APP_DOMAIN:?APP_DOMAIN is required}"

export RECSYS_IMAGE_SHA="$image_sha"
export RECSYS_API_IMAGE="ghcr.io/${GHCR_OWNER}/recsys-api:${image_sha}"
export RECSYS_WEB_IMAGE="ghcr.io/${GHCR_OWNER}/recsys-web:${image_sha}"

compose() {
  docker-compose -f docker-compose.yml -f docker-compose.prod.yml "$@"
}

compose pull api migrate worker scheduler web

api_revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$RECSYS_API_IMAGE")"
web_revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$RECSYS_WEB_IMAGE")"
if [ "$api_revision" != "$image_sha" ] || [ "$web_revision" != "$image_sha" ]; then
  echo "release image revision does not match requested Git SHA" >&2
  exit 1
fi

mkdir -p backups
docker-compose exec -T db pg_dump -U recsys -Fc recsys > "backups/recsys-$(date -u +%Y%m%dT%H%M%SZ).dump"
compose run --rm migrate
compose up -d
curl --fail --retry 10 --retry-delay 3 "https://${APP_DOMAIN}/health/ready"
