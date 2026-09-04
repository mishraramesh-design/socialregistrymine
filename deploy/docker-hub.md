# Docker Hub — building and pushing our own images

This covers **our own** 7 services + frontend only. Sunbird RC and OpenG2P are
pulled from their own official registries (`ghcr.io/sunbird-rc/*` and whatever
`openg2p-erp-docker`'s `common.yaml` references) — we never rebuild or republish
those.

## Tagging convention

```
<dockerhub-user>/socialregistrymine-<service>:<tag>
<dockerhub-user>/socialregistrymine-<service>:latest
```

e.g. `mishraramesh/socialregistrymine-consent-management:a1b2c3d`. `<tag>` defaults
to the short git commit hash so every pushed image is traceable back to the exact
commit it was built from.

## Build and push everything

```bash
docker login
DOCKERHUB_USER=yourusername ./deploy/build-and-push.sh
```

Or push a specific tag (e.g. for a release):

```bash
DOCKERHUB_USER=yourusername ./deploy/build-and-push.sh v0.2.0
```

## Running from the pushed images (instead of building on the VPS)

`docker-compose.yml` at the repo root builds from local source (`build: ./services/...`).
For a VPS deployment you generally want to *pull* pre-built images instead — smaller,
faster, and doesn't need the source tree or a build toolchain on the box. Use
`deploy/docker-compose.images.yml` as an override that replaces every `build:` with
an `image:` pointing at what you just pushed:

```bash
DOCKERHUB_USER=yourusername TAG=v0.2.0 \
  docker compose -f docker-compose.yml -f deploy/docker-compose.images.yml pull

DOCKERHUB_USER=yourusername TAG=v0.2.0 \
  docker compose -f docker-compose.yml -f deploy/docker-compose.images.yml up -d
```

(`docker-compose.yml`'s `build:` keys are simply ignored when an `image:` override
is present and `pull`/`up` are used without `--build`.)
