# Real-DPG Pilot Deployment

This directory wires our own platform (`services/`, `frontend/`) together with **real,
separately-deployed** instances of Sunbird RC, OpenG2P, and Inji, running as their own
Docker containers on a shared Docker network — not mocked, not forked. DIGIT is the
one exception — see below.

None of these DPGs' source is vendored into this repo. You clone each one's own
official repository next to (not inside) `socialregistrymine`, run *their* compose
files unmodified, and use a small network-attachment override (provided here) to join
them to a shared network our platform also joins. This keeps each DPG independently
upgradable from its own upstream.

## Status of each DPG (checked directly against upstream, September 2026)

| DPG | Repo | Status |
|---|---|---|
| **Sunbird RC** | [Sunbird-RC/sunbird-rc-core](https://github.com/Sunbird-RC/sunbird-rc-core) | Actively maintained. Official `docker-compose.yml`, ~23 services. |
| **OpenG2P** | [OpenG2P/openg2p-erp-docker](https://github.com/OpenG2P/openg2p-erp-docker) | **Archived (read-only) July 2026.** OpenG2P's current supported path is Kubernetes/Helm (`openg2p-helm`). This repo still runs (Odoo v14-based) but gets no further updates or security patches — deliberately used here as the simple pilot option per your call; revisit before this becomes a production dependency. |
| **Inji** (Certify + Verify) | [mosip/inji-certify](https://github.com/mosip/inji-certify) | Actively maintained. Official docker-compose demo stack (`docker-compose-injistack`), 5 services + an optional 6th (Verify, ships commented out). |
| **DIGIT** | [DIGIT-OSS](https://github.com/orgs/egovernments/repositories) | **Not deployed for this POC.** DIGIT's production path is Kubernetes/Helm with no equivalent lightweight docker-compose demo — a materially bigger lift than the other three. Per your call, `digit-mock` (in this repo, `services/digit-mock/`) stands in: it implements the exact `egov-workflow-v2` API `digit-adapter` calls, so the verification-routing story still demos end-to-end. Swap `DIGIT_BASE_URL` for a real cluster later — nothing else changes. |

## Directory layout

```
deploy/
├── README.md                        # this file — the master runbook
├── deploy-all-dpgs.sh                # one-shot automation of the clone+join-network+up steps
│                                     #   below for all three real DPGs — run on your VPS
├── docker-compose.hostinger.yml     # ready-to-paste file for Hostinger Docker Manager's
│                                     #   "Compose from URL" — pulls images, one public port (6561)
├── docker-compose.hostinger-networked.yml  # same, but joins social-registry-net so real
│                                     #   Sunbird RC/OpenG2P/Inji on the same VPS can be reached
├── docker-compose.images.yml        # override for the manual path: run OUR platform from
│                                     #   pushed images instead of building from source
├── sunbird-rc/
│   ├── README.md                    # clone + configure + join-network steps
│   └── docker-compose.network.yml   # override: attaches registry+nginx to the shared network
├── openg2p/
│   ├── README.md                    # clone + configure + join-network steps
│   └── docker-compose.network.yml   # override: attaches odoo to the shared network
├── inji/
│   ├── README.md                    # clone + configure + join-network steps
│   └── docker-compose.network.yml   # override: attaches certify-nginx + re-adds verify-service
├── docker-hub.md                    # build & push OUR OWN service images (not the DPGs)
└── hostinger-vps.md                 # VPS sizing, provisioning, bring-up order, verification
```

## Quickest path: Hostinger Docker Manager

If you just want this platform's own 10 services + frontend running on your Hostinger
VPS, pulling pre-built images — `deploy/docker-compose.hostinger.yml` is self-contained
(no external network, no prerequisite commands, nothing to build):

1. hPanel → your VPS → **Docker Manager** → **Compose**.
2. **Compose manually** — paste the full contents of `deploy/docker-compose.hostinger.yml`
   into the editor and deploy. This is the reliable option; use it if the repo is
   private (see below).
   - *Compose from URL* also works, pointed at this file's raw GitHub URL, but
     **only if the repo is public** — GitHub's raw-content URLs 404 on an
     unauthenticated fetch against a private repo, which is what "it failed"
     usually means here. Make the repo public first, or stick to pasting manually.
3. The whole platform is reachable on **port 6561** — nginx (inside the `frontend`
   container) serves the config console and reverse-proxies `/api/*` to `api-gateway`
   internally, so one port is all you need. Nothing else is published to the internet.

This does **not** include Sunbird RC, OpenG2P, or Inji — those stay separate
deployments per the sections below. Without them running, `sunbird-adapter`,
`openg2p-sync`, and `inji-adapter` just report "unreachable," which is expected
until you bring a given DPG up. `digit-adapter` is the exception: it's already
wired to `digit-mock` (bundled, no separate deployment), so the
verification-routing story works out of the box even in this quick path.

**Ready to connect real DPGs to this same Hostinger deployment?** Switch to
`deploy/docker-compose.hostinger-networked.yml` instead — identical stack, same
named volumes (so already-seeded data carries over under the same Docker
Manager stack), but `openg2p-sync`, `sunbird-adapter`, and `inji-adapter` also
join the external `social-registry-net` network so they can actually reach a
real Sunbird RC/OpenG2P/Inji running alongside them on the same VPS. That
network must exist first — `docker network create social-registry-net`, or run
`deploy/deploy-all-dpgs.sh` first, which creates it as part of bringing up each
DPG — otherwise `docker compose up` fails outright looking for a network that
doesn't exist yet.

## The shared network

Everything — our platform's containers and each DPG's containers — joins one external
Docker network so services can resolve each other by container name.

```bash
docker network create social-registry-net
```

Create this once per host, before bringing anything up.

## Bring-up order

1. `docker network create social-registry-net` (once)
2. Sunbird RC — see `sunbird-rc/README.md`
3. OpenG2P — see `openg2p/README.md`
4. Inji — see `inji/README.md` (creates its own additional `mosip_network` too)
5. Our own platform (this includes `digit-mock`, standing in for DIGIT — no
   separate deployment needed for it) — from the repo root:
   `docker compose up --build -d`. Its `docker-compose.yml` already joins
   `social-registry-net` and points every adapter at the real container DNS
   names — `http://registry:8091`, `http://odoo:8069`, `http://certify-nginx:80`,
   `http://verify-service:8080`, `http://digit-mock:8083` — see the root
   `.env.example`.

Steps 1–4 are automated by `deploy/deploy-all-dpgs.sh` — run it **on your VPS**
(it needs a real Docker daemon and clones each DPG's own multi-gigabyte repo,
neither of which this development environment has):

```bash
./deploy/deploy-all-dpgs.sh              # all three
./deploy/deploy-all-dpgs.sh sunbird-rc   # or just one
```

It clones each DPG next to this repo, copies in the network-attachment
override, and brings each stack up — but deliberately stops short of editing
secrets for you (it fetches each DPG's default `.env`/config with a loud
warning to change the passwords before exposing anything publicly) and stops
short of the one-time manual steps below (Sunbird RC schema registration,
confirming Inji Verify's path, wiring OpenG2P's beneficiary payload shape) —
see each DPG's own `README.md` for those.

## Verifying the wiring end to end

```bash
# From inside our api-gateway container (or docker exec into it):
curl http://registry:8091/health                                    # Sunbird RC
curl http://odoo:8069/web/login                                      # OpenG2P/Odoo
curl http://certify-nginx:80/.well-known/openid-credential-issuer    # Inji Certify
curl http://verify-service:8080/health                               # Inji Verify (path unconfirmed — see inji/README.md)

# From your own machine, through our gateway:
curl http://<host>:8000/api/sunbird/health
curl http://<host>:8000/api/openg2p-sync/sync/schedule
curl http://<host>:8000/api/inji/health
curl http://<host>:8000/api/digit/health
```

A golden record pushed via `POST /api/registry/golden-records/{id}` followed by
`POST /api/sunbird/golden-records/{id}/push` should now actually create an entity in
Sunbird RC's registry — check `docker logs registry` if it doesn't. A verification
case routed via `POST /api/digit/verification-cases/{id}/route`, checked again a
little later via `GET /api/digit/verification-cases/{id}/status`, should show
`digit_state` progress from `PENDING_ASSIGNMENT` toward `VERIFIED` (that's
`digit-mock`'s illustrative timeline, not a real workflow — see
`services/digit-mock/README.md`).
