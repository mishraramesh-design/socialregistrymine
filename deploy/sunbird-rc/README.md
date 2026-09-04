# Sunbird RC — real instance for this pilot

Official repo, unmodified. We clone it next to `socialregistrymine`, not inside it.

## 1. Clone and configure

```bash
cd ~   # or wherever you keep the two repos side by side
git clone https://github.com/Sunbird-RC/sunbird-rc-core.git
cd sunbird-rc-core

# Their .env — download and review; sets RELEASE_VERSION, DB creds, Keycloak
# admin creds, etc. Change every default password before exposing this publicly.
curl -O https://raw.githubusercontent.com/Sunbird-RC/sunbird-rc-core/main/.env
```

Read their `.env` fully and change:
- `POSTGRES_PASSWORD`
- Keycloak admin credentials
- Any other placeholder secret

## 2. Create the shared network (once per host)

```bash
docker network create social-registry-net
```

## 3. Bring it up, joined to the shared network

```bash
cp /path/to/socialregistrymine/deploy/sunbird-rc/docker-compose.network.yml .
docker compose -f docker-compose.yml -f docker-compose.network.yml up -d
```

This is the **full** ~23-service stack (Postgres, Elasticsearch, Keycloak, MinIO,
Kafka+Zookeeper, Redis, Vault, ClickHouse, plus registry/claims/identity/credential/
OID4VC/notification/etc. microservices, fronted by nginx). See
`deploy/hostinger-vps.md` for what this actually costs in RAM before you provision
a box for it.

## 4. What our platform calls

`sunbird-adapter` talks directly to the `registry` service's entity API on the
shared network — `http://registry:8091` — bypassing nginx, since we only need
registry CRUD, not the full credential/OID4VC surface nginx fronts. This is already
the default in the root `.env.example`.

## 5. Register the Citizen schema

Sunbird RC generates CRUD APIs per registered JSON Schema — it doesn't ship one for
"Citizen" out of the box. Before `sunbird-adapter`'s first push will succeed, register
a schema matching the canonical citizen/family attributes from the root `README.md`,
per Sunbird RC's own schema-registration docs (`POST` a JSON Schema to the registry's
schema endpoint). This is a one-time setup step per deployment, not something our
adapter does for you.

## Verify

```bash
docker compose ps                # every service should be "healthy" or "running"
docker logs registry --tail 50   # confirm it started without errors
```

Exact health-endpoint paths vary by service version — check the `healthcheck:`
command each service defines in `docker-compose.yml` rather than assuming `/health`
everywhere. Once `docker compose ps` shows `registry` healthy, confirm reachability
from our platform's network:

```bash
docker exec <our-sunbird-adapter-container-id> curl -sv http://registry:8091/ | head -20
```
