# Hostinger VPS — sizing and provisioning

## Sizing (checked against Hostinger's current KVM tiers, Sept 2026)

| Tier | vCPU | RAM | Disk | Fits? |
|---|---|---|---|---|
| KVM 2 | 2 | 8 GB | 100 GB NVMe | No — below Sunbird RC's own stated 8 GB *floor*, before OpenG2P or our stack |
| KVM 4 | 4 | 16 GB | 200 GB NVMe | Tight. Workable only if you trim optional Sunbird RC services (see below) and cap Elasticsearch's heap |
| **KVM 8** | **8** | **32 GB** | **400 GB NVMe** | **Recommended** — comfortable headroom for all three stacks running together |

Source: [Hostinger VPS Hosting](https://www.hostinger.com/vps-hosting).

Why KVM 8: Sunbird RC's own compose file runs ~23 containers (Elasticsearch, two
Postgres-family databases across the three stacks, Keycloak, Vault, Kafka+Zookeeper,
Redis, ClickHouse, MinIO, plus a dozen application microservices), OpenG2P adds an
Odoo + Postgres + Traefik stack on top, and our own 7 services + frontend add modest
but real overhead. None of these are individually heavy, but the *count* adds up in
base memory (JVMs, Postgres connection pools, Elasticsearch's own overhead) well
before any real traffic.

**If you must run on KVM 4**: cap Elasticsearch's heap explicitly (Sunbird RC's
default `docker-compose.yml` doesn't do this for you, and ES 6.x will otherwise grab
much more than a 16 GB box can spare) — add `ES_JAVA_OPTS=-Xms1g -Xmx1g` to the `es`
service's environment before bringing it up — and consider disabling services your
pilot doesn't need yet (`bulk_issuance`, `digilocker-certificate-api`, `clickhouse`,
`metrics` are reasonable to defer). Don't run OpenG2P and the full Sunbird RC stack
simultaneously on KVM 4 without doing this.

## Provisioning

1. **Order a KVM 8 VPS**, Ubuntu 22.04 LTS image.
2. **Point a domain/subdomain** at it (e.g. `registry.yourdomain.gov`) — needed for
   TLS in step 5; a bare IP works for an internal pilot but isn't suitable to hand to
   real users.
3. **Install Docker + Compose plugin**:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER   # log out/in after this
   ```
4. **Firewall** — only expose what needs to be public. Everything else talks over
   `social-registry-net` internally.
   ```bash
   sudo ufw allow OpenSSH
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```
   Do **not** open Postgres (5432), Elasticsearch (9200), Keycloak's management port
   (9990), Vault (8200), or any other DPG internal port to the internet — they should
   only be reachable container-to-container on `social-registry-net`.
5. **Reverse proxy + TLS** for the two things end users/operators actually hit —
   our `frontend` (config console) and `api-gateway`. A minimal Caddy setup handles
   both with automatic Let's Encrypt certificates:
   ```
   # /etc/caddy/Caddyfile (if you install Caddy directly), or run Caddy as a container
   registry.yourdomain.gov {
     reverse_proxy /api/* localhost:8000
     reverse_proxy localhost:5173
   }
   ```
   Sunbird RC's own `nginx` service and OpenG2P's `inverseproxy` stack are for
   *their* internal routing between their own containers — don't expose those
   directly; only our gateway and frontend need a public TLS entry point.

## Bring-up order on the VPS

Follow `deploy/README.md`'s bring-up order exactly:

```bash
docker network create social-registry-net
```

Then Sunbird RC (`deploy/sunbird-rc/README.md`), then OpenG2P
(`deploy/openg2p/README.md`), then our platform — using pushed images rather than
building on the box (see `deploy/docker-hub.md`):

```bash
git clone https://github.com/mishraramesh-design/socialregistrymine.git
cd socialregistrymine
cp .env.example .env   # edit SUNBIRD_RC_BASE_URL / OPENG2P_BASE_URL if you changed service names
DOCKERHUB_USER=yourusername TAG=v0.1.0 \
  docker compose -f docker-compose.yml -f deploy/docker-compose.images.yml pull
DOCKERHUB_USER=yourusername TAG=v0.1.0 \
  docker compose -f docker-compose.yml -f deploy/docker-compose.images.yml up -d
```

## Verification checklist

```bash
docker ps                                       # every container Up/healthy
docker exec socialregistrymine-api-gateway-1 curl -s http://localhost:8000/health
curl -sk https://registry.yourdomain.gov/api/health   # through the reverse proxy + TLS
```

Confirm the cross-stack wiring specifically (this is the part that's easy to get
subtly wrong — network name typos, wrong internal ports):

```bash
docker exec socialregistrymine-sunbird-adapter-1 curl -sv http://registry:8091/ | head
docker exec socialregistrymine-openg2p-sync-1 curl -sv http://odoo:8069/web/login | head
```

## Ongoing operations (not covered here, worth planning before go-live)

- **Backups**: at minimum, the Postgres volumes for Sunbird RC's `db`, OpenG2P's
  `db`, and our own SQLite volumes. None of this is automated by this repo.
- **Secrets**: every default password in Sunbird RC's `.env` and OpenG2P's
  `.docker/*.env` files must be changed — this repo doesn't do that for you.
- **Updates**: Sunbird RC is actively maintained — track their releases. OpenG2P's
  compose repo is archived (see `deploy/openg2p/README.md`) and won't receive
  updates; plan its replacement before this is more than a pilot.
