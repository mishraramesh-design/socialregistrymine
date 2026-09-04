# Docker Hub — building and pushing our own images

This covers **our own** 7 services + frontend only. Sunbird RC and OpenG2P are
pulled from their own official registries (`ghcr.io/sunbird-rc/*` and whatever
`openg2p-erp-docker`'s `common.yaml` references) — we never rebuild or republish
those.

## Tagging convention

One Docker Hub repo, one tag per service — matches a repo you create once by hand
(e.g. `mishramesh/mysocial`) rather than needing eight separate repos:

```
<dockerhub-username>/<repo>:<service>-<tag>
<dockerhub-username>/<repo>:<service>-latest
```

e.g. `mishramesh/mysocial:consent-management-a1b2c3d` and
`mishramesh/mysocial:consent-management-latest`. `<tag>` defaults to the short git
commit hash (the CI workflow uses the full `github.sha`) so every pushed image is
traceable back to the exact commit it was built from. `<repo>` defaults to
`mysocial`; override with `DOCKERHUB_REPO` if you named yours differently.

## Automatic builds via GitHub Actions (already wired)

`.github/workflows/docker-publish.yml` builds and pushes all 8 images on every push
to `main` that touches `services/**` or `frontend/**`, using the `DOCKERHUB_USERNAME`
and `DOCKERHUB_TOKEN` repository secrets — already set on this repo. Nothing further
to configure; just push to `main` (or trigger it manually from the Actions tab —
it has `workflow_dispatch` enabled). If your Docker Hub repo isn't named `mysocial`,
add a repository **variable** (not secret) named `DOCKERHUB_REPO` under
Settings → Secrets and variables → Actions → Variables.

## Manual build and push (local machine, if you need it outside CI)

```bash
docker login
DOCKERHUB_USERNAME=mishramesh ./deploy/build-and-push.sh
```

Or push a specific tag (e.g. for a release):

```bash
DOCKERHUB_USERNAME=mishramesh ./deploy/build-and-push.sh v0.2.0
```

## Running from the pushed images (instead of building on the VPS)

`docker-compose.yml` at the repo root builds from local source (`build: ./services/...`).
For a VPS deployment you generally want to *pull* pre-built images instead — smaller,
faster, and doesn't need the source tree or a build toolchain on the box. Use
`deploy/docker-compose.images.yml` as an override that replaces every `build:` with
an `image:` pointing at what CI (or the script above) just pushed:

```bash
DOCKERHUB_USERNAME=mishramesh TAG=v0.2.0 \
  docker compose -f docker-compose.yml -f deploy/docker-compose.images.yml pull

DOCKERHUB_USERNAME=mishramesh TAG=v0.2.0 \
  docker compose -f docker-compose.yml -f deploy/docker-compose.images.yml up -d
```

(`docker-compose.yml`'s `build:` keys are simply ignored when an `image:` override
is present and `pull`/`up` are used without `--build`. Use the CI-built `-latest`
tags if you don't want to pin a specific `TAG`.)
