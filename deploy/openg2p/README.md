# OpenG2P — real instance for this pilot (archived repo, used deliberately)

**Read this first**: `OpenG2P/openg2p-erp-docker` was archived (read-only) in July
2026. It still runs — it's an Odoo v14-based stack — but receives no further
updates or security patches. This is fine for a phase-one pilot per your call;
before this becomes anything client-facing or long-lived, re-evaluate against
OpenG2P's current supported path (Kubernetes via `openg2p-helm`).

## 1. Clone and configure

```bash
cd ~   # next to socialregistrymine and sunbird-rc-core, not inside either
git clone https://github.com/OpenG2P/openg2p-erp-docker.git
cd openg2p-erp-docker

cp -r dot-docker-example .docker
```

Edit the files now under `.docker/`:
- `.docker/odoo.env` — set `ADMIN_PASSWORD`
- `.docker/db-access.env` — set `PGPASSWORD`
- `.docker/db-creation.env` — set matching `POSTGRES_PASSWORD`

Change every default before exposing this publicly — the documented default
Odoo login (`admin` / `admin`) must be changed immediately after first boot too.

## 2. Create the shared network (once per host — skip if already created for Sunbird RC)

```bash
docker network create social-registry-net
```

## 3. Bring up the reverse proxy, then the app, joined to the shared network

```bash
docker compose -p inverseproxy -f inverseproxy-none-ssl.yaml up -d

cp /path/to/socialregistrymine/deploy/openg2p/docker-compose.network.yml .
docker compose -f common.yaml -f prod.yaml -f docker-compose.network.yml up -d

# First-time only — initializes the database with the openg2p module:
docker compose -f common.yaml -f prod.yaml run --rm odoo odoo --stop-after-init -i openg2p
```

## 4. What our platform calls

`openg2p-sync` talks to `http://odoo:8069` on the shared network — already the
default in the root `.env.example`. Odoo's XML-RPC/JSON-RPC or REST API (depending
on which OpenG2P modules are installed) is what `openg2p-sync` should be pointed at
for the beneficiary bulk-create call — the exact endpoint path depends on which
OpenG2P beneficiary-registration module you install, which isn't pinned by this
scaffold; check the specific module's API docs before wiring the real payload shape
(our `openg2p-sync` service currently posts to `/api/beneficiaries/bulk`, a
placeholder contract — update it to match whatever the installed module actually
exposes).

## Verify

```bash
curl http://localhost:8069/web/login   # from the openg2p-erp-docker host
docker exec <our-openg2p-sync-container-id> curl -sv http://odoo:8069/web/login | head -20
```
