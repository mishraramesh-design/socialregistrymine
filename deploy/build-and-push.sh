#!/usr/bin/env bash
# Builds and pushes every socialregistrymine service image to Docker Hub.
# Does NOT touch Sunbird RC or OpenG2P images — those are pulled from their own
# official registries per deploy/sunbird-rc/README.md and deploy/openg2p/README.md.
#
# Usage:
#   DOCKERHUB_USER=yourusername ./deploy/build-and-push.sh [tag]
#
# `tag` defaults to the short git commit hash. Every image is also tagged
# `latest`. Requires `docker login` to have already been run.

set -euo pipefail

if [[ -z "${DOCKERHUB_USER:-}" ]]; then
  echo "Set DOCKERHUB_USER, e.g.: DOCKERHUB_USER=yourusername $0" >&2
  exit 1
fi

TAG="${1:-$(git rev-parse --short HEAD)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SERVICES=(
  "consent-management"
  "connector-config"
  "registry-intelligence"
  "delivery-intelligence"
  "openg2p-sync"
  "sunbird-adapter"
  "api-gateway"
)

for service in "${SERVICES[@]}"; do
  image="${DOCKERHUB_USER}/socialregistrymine-${service}"
  echo "==> Building ${image}:${TAG}"
  docker build -t "${image}:${TAG}" -t "${image}:latest" "${REPO_ROOT}/services/${service}"
  echo "==> Pushing ${image}:${TAG} and :latest"
  docker push "${image}:${TAG}"
  docker push "${image}:latest"
done

frontend_image="${DOCKERHUB_USER}/socialregistrymine-frontend"
echo "==> Building ${frontend_image}:${TAG}"
docker build -t "${frontend_image}:${TAG}" -t "${frontend_image}:latest" "${REPO_ROOT}/frontend"
echo "==> Pushing ${frontend_image}:${TAG} and :latest"
docker push "${frontend_image}:${TAG}"
docker push "${frontend_image}:latest"

echo "==> Done. Images pushed under ${DOCKERHUB_USER}/socialregistrymine-*:${TAG} (and :latest)"
