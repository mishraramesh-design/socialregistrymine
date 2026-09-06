# Inji (Certify + Verify) — real instance for this pilot

Official repo, unmodified — [mosip/inji-certify](https://github.com/mosip/inji-certify),
its `docker-compose/docker-compose-injistack` demo stack. Verified directly
against their `docker-compose.yaml` (not guessed): 5 services (`database`,
`certify`, `certify-nginx`, `mimoto-service`, `inji-web`), plus a
`verify-service` that ships **commented out** in their file — Inji Verify
isn't part of the default demo, so we re-add it via an override rather than
editing their tracked file (same non-forking rule as Sunbird RC/OpenG2P).

## 1. Clone

```bash
cd ~   # next to socialregistrymine, sunbird-rc-core, etc. — not inside any of them
git clone https://github.com/mosip/inji-certify.git
cd inji-certify/docker-compose/docker-compose-injistack
```

## 2. Create the required networks

Their compose file declares its own network as **external** — it is not
auto-created, and `docker compose up` fails outright without this step
(the same class of gotcha that broke the Hostinger quick-deploy earlier):

```bash
docker network create mosip_network
docker network create social-registry-net   # skip if already created for Sunbird RC/OpenG2P
```

## 3. Bring it up, with Inji Verify enabled and joined to the shared network

```bash
cp /path/to/socialregistrymine/deploy/inji/docker-compose.network.yml .
docker compose -f docker-compose.yaml -f docker-compose.network.yml up -d
```

This starts the 5 default services plus `verify-service` (re-added from
their own commented block, unmodified).

## 4. What our platform calls

- `inji-adapter`'s `INJI_CERTIFY_BASE_URL` → `http://certify-nginx:80` (their
  nginx reverse-proxies to the `certify` backend on container port 8090 —
  host-mapped to 8091, but on the shared network you reach it via
  `certify-nginx`'s own container port, 80, not the host mapping).
- `inji-adapter`'s `INJI_VERIFY_BASE_URL` → `http://verify-service:8080`.
- `INJI_VERIFY_PATH` is still an **unconfirmed guess** (`/v1/verify/vc-verification`)
  — `verify-service`'s environment references `INJI_VP_SUBMISSION_BASE_URL=.../v1/verify`,
  which suggests the real path is closer to `/v1/verify` than what's currently
  configured; confirm against the running service's own API docs/OpenAPI spec
  once it's up, and update `INJI_VERIFY_PATH` accordingly.
- Credential issuance is OpenID4VCI discovery-based (`inji-adapter` fetches
  `/.well-known/openid-credential-issuer` from `INJI_CERTIFY_BASE_URL` to find
  the real `credential_endpoint`) — this should work against `certify-nginx`
  without further path guessing, since discovery is the whole point of that
  protocol.

## 5. Data source note

The `certify` service's default profile in this demo stack (`csvdp-farmer`) is
CSV-backed sample data (`farmer_identity_data.csv`), not wired to Sunbird RC —
this demo stack does **not** bundle or require Sunbird RC. That's fine for
proving credential issuance/verification works at all for the POC; wiring
Certify to actually issue credentials *for our platform's own golden records*
(rather than its bundled sample data) is real configuration work on Certify's
plugin system, not something this adapter or override does for you.

## Verify

```bash
docker compose ps                    # every service Up
curl http://localhost:8091/.well-known/openid-credential-issuer   # from the inji-certify host
```
