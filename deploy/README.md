# Real-DPG Pilot Deployment

This directory wires our own platform (`services/`, `frontend/`) together with **real,
separately-deployed** instances of Sunbird RC and OpenG2P, running as their own
Docker containers on a shared Docker network — not mocked, not forked.

Neither DPG's source is vendored into this repo. You clone each DPG's own official
repository next to (not inside) `socialregistrymine`, run *their* compose files
unmodified, and use a small network-attachment override (provided here) to join them
to a shared network our platform also joins. This keeps both DPGs independently
upgradable from their own upstreams.

## Status of each DPG (checked directly against upstream, September 2026)

| DPG | Repo | Status |
|---|---|---|
| **Sunbird RC** | [Sunbird-RC/sunbird-rc-core](https://github.com/Sunbird-RC/sunbird-rc-core) | Actively maintained. Official `docker-compose.yml`, ~23 services. |
| **OpenG2P** | [OpenG2P/openg2p-erp-docker](https://github.com/OpenG2P/openg2p-erp-docker) | **Archived (read-only) July 2026.** OpenG2P's current supported path is Kubernetes/Helm (`openg2p-helm`). This repo still runs (Odoo v14-based) but gets no further updates or security patches — deliberately used here as the simple pilot option per your call; revisit before this becomes a production dependency. |

## Directory layout

```
deploy/
├── README.md                        # this file — the master runbook
├── docker-compose.hostinger.yml     # ready-to-paste file for Hostinger Docker Manager's
│                                     #   "Compose from URL" — pulls images, one public port (6561)
├── docker-compose.images.yml        # override for the manual path: run OUR platform from
│                                     #   pushed images instead of building from source
├── sunbird-rc/
│   ├── README.md                    # clone + configure + join-network steps
│   └── docker-compose.network.yml   # override: attaches registry+nginx to the shared network
├── openg2p/
│   ├── README.md                    # clone + configure + join-network steps
│   └── docker-compose.network.yml   # override: attaches odoo to the shared network
├── docker-hub.md                    # build & push OUR OWN service images (not the DPGs)
└── hostinger-vps.md                 # VPS sizing, provisioning, bring-up order, verification
```

## Quickest path: Hostinger Docker Manager

If you just want this platform's own 9 services + frontend running on your Hostinger
VPS, pulling pre-built images (no git clone, no build step, no compose knowledge
needed beyond pasting a URL):

1. SSH into the VPS once and run `docker network create social-registry-net` (harmless
   if you're not running Sunbird RC/OpenG2P yet — just future-proofs joining them later).
2. hPanel → your VPS → **Docker Manager** → **Compose** → **Compose from URL**.
3. Paste the raw URL of `deploy/docker-compose.hostinger.yml` in this repo
   (`https://raw.githubusercontent.com/mishraramesh-design/socialregistrymine/main/deploy/docker-compose.hostinger.yml`)
   and deploy.
4. The whole platform is reachable on **port 6561** — nginx (inside the `frontend`
   container) serves the config console and reverse-proxies `/api/*` to `api-gateway`
   internally, so one port is all you need. Nothing else is published to the internet.

This does **not** include Sunbird RC, OpenG2P, DIGIT, or Inji — those stay separate
deployments per the sections below. Without them running, the adapters just report
"unreachable," which is expected until you bring a given DPG up.

## The shared network

Everything — our platform's containers and both DPGs' containers — joins one external
Docker network so services can resolve each other by container name.

```bash
docker network create social-registry-net
```

Create this once per host, before bringing anything up.

## Bring-up order

1. `docker network create social-registry-net` (once)
2. Sunbird RC — see `sunbird-rc/README.md`
3. OpenG2P — see `openg2p/README.md`
4. Our own platform — from the repo root: `docker compose up --build -d` (its
   `docker-compose.yml` already joins `social-registry-net` and points
   `sunbird-adapter`/`openg2p-sync` at the real container DNS names —
   `http://registry:8091` and `http://odoo:8069` respectively; see the root
   `.env.example`)

## Verifying the wiring end to end

```bash
# From inside our api-gateway container (or docker exec into it):
curl http://registry:8091/health           # Sunbird RC registry service reachable
curl http://odoo:8069/web/login            # OpenG2P/Odoo reachable

# From your own machine, through our gateway:
curl http://<host>:8000/api/sunbird/health
curl http://<host>:8000/api/openg2p-sync/sync/schedule
```

A golden record pushed via `POST /api/registry/golden-records/{id}` followed by
`POST /api/sunbird/golden-records/{id}/push` should now actually create an entity in
Sunbird RC's registry — check `docker logs registry` if it doesn't.
