#!/usr/bin/env bash
# Builds and pushes every socialregistrymine service image to a single Docker Hub
# repo, one tag per service (matches the repo you create by hand — see
# deploy/docker-hub.md). Does NOT touch Sunbird RC or OpenG2P images — those are
# pulled from their own official registries per deploy/sunbird-rc/README.md and
# deploy/openg2p/README.md.
#
# Usage:
#   DOCKERHUB_USERNAME=mishramesh ./deploy/build-and-push.sh [tag]
#   DOCKERHUB_USERNAME=mishramesh DOCKERHUB_REPO=mysocial ./deploy/build-and-push.sh v0.2.0
#
# `tag` defaults to the short git commit hash. Every image is also tagged
# `<service>-latest`. Requires `docker login` to have already been run.
# In CI, prefer the GitHub Actions workflow at .github/workflows/docker-publish.yml
# instead — it does the same thing on every push using the DOCKERHUB_USERNAME/
# DOCKERHUB_TOKEN repo secrets.

set -euo pipefail

if [[ -z "${DOCKERHUB_USERNAME:-}" ]]; then
  echo "Set DOCKERHUB_USERNAME, e.g.: DOCKERHUB_USERNAME=mishramesh $0" >&2
  exit 1
fi

REPO="${DOCKERHUB_REPO:-mysocial}"
TAG="${1:-$(git rev-parse --short HEAD)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${DOCKERHUB_USERNAME}/${REPO}"

SERVICES=(
  "consent-management"
  "connector-config"
  "registry-intelligence"
  "delivery-intelligence"
  "openg2p-sync"
  "sunbird-adapter"
  "digit-mock"
  "digit-adapter"
  "inji-adapter"
  "demo-seeder"
  "api-gateway"
)

for service in "${SERVICES[@]}"; do
  echo "==> Building ${IMAGE}:${service}-${TAG}"
  docker build \
    -t "${IMAGE}:${service}-${TAG}" \
    -t "${IMAGE}:${service}-latest" \
    "${REPO_ROOT}/services/${service}"
  echo "==> Pushing ${IMAGE}:${service}-${TAG} and :${service}-latest"
  docker push "${IMAGE}:${service}-${TAG}"
  docker push "${IMAGE}:${service}-latest"
done

echo "==> Building ${IMAGE}:frontend-${TAG}"
docker build \
  -t "${IMAGE}:frontend-${TAG}" \
  -t "${IMAGE}:frontend-latest" \
  "${REPO_ROOT}/frontend"
echo "==> Pushing ${IMAGE}:frontend-${TAG} and :frontend-latest"
docker push "${IMAGE}:frontend-${TAG}"
docker push "${IMAGE}:frontend-latest"

echo "==> Done. Images pushed under ${IMAGE}:<service>-${TAG} (and :<service>-latest)"
