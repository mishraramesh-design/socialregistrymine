#!/usr/bin/env bash
# One-shot automation of the real-DPG bring-up steps documented in
# deploy/README.md, deploy/sunbird-rc/README.md, deploy/openg2p/README.md, and
# deploy/inji/README.md. Run this ON YOUR VPS (or wherever docker/docker compose
# run), next to (not inside) the socialregistrymine checkout.
#
# What this automates: creating the shared networks, cloning each DPG's
# official repo unmodified, copying this platform's network override into it,
# and bringing each stack up.
#
# What this deliberately does NOT automate (you still do these by hand, once,
# per the linked README — they involve secrets or judgment calls this script
# shouldn't make for you):
#   - Editing each DPG's .env/config files to replace default passwords
#   - Registering Sunbird RC's Citizen JSON Schema
#   - Confirming Inji Verify's real verification path
#   - Wiring openg2p-sync's beneficiary payload to your installed OpenG2P module
#
# Usage:
#   ./deploy-all-dpgs.sh                 # clone + bring up all three
#   ./deploy-all-dpgs.sh sunbird-rc      # just one
#   ./deploy-all-dpgs.sh openg2p inji    # a subset
#   DPG_DIR=/opt/dpgs ./deploy-all-dpgs.sh   # clone elsewhere (default: sibling of this repo)
#
# Safe to re-run: skips cloning if the target directory already exists (pulls
# latest instead), and network creation is idempotent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DPG_DIR="${DPG_DIR:-$(cd "${REPO_ROOT}/.." && pwd)}"

log()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$1" >&2; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is not installed or not on PATH"
docker compose version >/dev/null 2>&1 || die "docker compose (v2 plugin) is required"

ensure_network() {
  local name="$1"
  if docker network inspect "$name" >/dev/null 2>&1; then
    log "Network '$name' already exists"
  else
    log "Creating network '$name'"
    docker network create "$name"
  fi
}

clone_or_update() {
  local url="$1" dir="$2"
  if [[ -d "$dir/.git" ]]; then
    log "Repo already cloned at $dir — pulling latest"
    git -C "$dir" pull --ff-only || warn "Could not fast-forward $dir — leaving it as-is"
  else
    log "Cloning $url -> $dir"
    git clone "$url" "$dir"
  fi
}

deploy_sunbird_rc() {
  log "Sunbird RC"
  local dir="${DPG_DIR}/sunbird-rc-core"
  ensure_network social-registry-net
  clone_or_update "https://github.com/Sunbird-RC/sunbird-rc-core.git" "$dir"

  if [[ ! -f "$dir/.env" ]]; then
    log "Fetching Sunbird RC's default .env"
    curl -fsSL -o "$dir/.env" \
      https://raw.githubusercontent.com/Sunbird-RC/sunbird-rc-core/main/.env
    warn "$dir/.env was just created with DEFAULT PASSWORDS."
    warn "Edit POSTGRES_PASSWORD, Keycloak admin credentials, and any other"
    warn "placeholder secret in $dir/.env BEFORE exposing this publicly."
  else
    log "$dir/.env already exists — leaving your edits alone"
  fi

  cp "${SCRIPT_DIR}/sunbird-rc/docker-compose.network.yml" "$dir/"
  log "Bringing up Sunbird RC (~23 services — this takes a few minutes)"
  (cd "$dir" && docker compose -f docker-compose.yml -f docker-compose.network.yml up -d)

  warn "One-time manual step still required: register the Citizen JSON Schema"
  warn "against the running registry service — see deploy/sunbird-rc/README.md #5."
  log "Sunbird RC: verify with 'docker compose -f $dir/docker-compose.yml ps'"
}

deploy_openg2p() {
  log "OpenG2P"
  local dir="${DPG_DIR}/openg2p-erp-docker"
  ensure_network social-registry-net
  clone_or_update "https://github.com/OpenG2P/openg2p-erp-docker.git" "$dir"

  if [[ ! -d "$dir/.docker" ]]; then
    log "Seeding $dir/.docker from their example config"
    cp -r "$dir/dot-docker-example" "$dir/.docker"
    warn "$dir/.docker/{odoo,db-access,db-creation}.env were just created with"
    warn "DEFAULT/BLANK passwords. Set ADMIN_PASSWORD and matching PGPASSWORD /"
    warn "POSTGRES_PASSWORD in those files BEFORE exposing this publicly, and"
    warn "change the default Odoo login (admin/admin) after first boot."
  else
    log "$dir/.docker already exists — leaving your edits alone"
  fi

  cp "${SCRIPT_DIR}/openg2p/docker-compose.network.yml" "$dir/"

  log "Bringing up OpenG2P's reverse proxy"
  (cd "$dir" && docker compose -p inverseproxy -f inverseproxy-none-ssl.yaml up -d)

  log "Bringing up OpenG2P (Odoo), joined to the shared network"
  (cd "$dir" && docker compose -f common.yaml -f prod.yaml -f docker-compose.network.yml up -d)

  log "Initializing the openg2p module (first run only — safe to re-run)"
  (cd "$dir" && docker compose -f common.yaml -f prod.yaml run --rm odoo \
    odoo --stop-after-init -i openg2p)

  warn "openg2p-sync currently posts to a placeholder '/api/beneficiaries/bulk'"
  warn "contract — confirm the real endpoint for whichever OpenG2P beneficiary"
  warn "module you install, per deploy/openg2p/README.md #4."
  log "OpenG2P: verify with 'curl http://localhost:8069/web/login' on this host"
}

deploy_inji() {
  log "Inji (Certify + Verify)"
  local dir="${DPG_DIR}/inji-certify"
  ensure_network mosip_network
  ensure_network social-registry-net
  clone_or_update "https://github.com/mosip/inji-certify.git" "$dir"

  local stack_dir="$dir/docker-compose/docker-compose-injistack"
  [[ -d "$stack_dir" ]] || die "Expected $stack_dir — inji-certify's layout may have changed; check deploy/inji/README.md"

  cp "${SCRIPT_DIR}/inji/docker-compose.network.yml" "$stack_dir/"
  log "Bringing up Inji Certify + Verify, joined to the shared network"
  (cd "$stack_dir" && docker compose -f docker-compose.yaml -f docker-compose.network.yml up -d)

  warn "INJI_VERIFY_PATH is an unconfirmed guess — check the running"
  warn "verify-service's own API docs and update .env if needed, per"
  warn "deploy/inji/README.md #4."
  log "Inji: verify with 'curl http://localhost:8091/.well-known/openid-credential-issuer' on this host"
}

main() {
  local targets=("$@")
  if [[ ${#targets[@]} -eq 0 ]]; then
    targets=(sunbird-rc openg2p inji)
  fi

  log "Deploying real DPGs into: ${DPG_DIR}"
  log "Targets: ${targets[*]}"

  for t in "${targets[@]}"; do
    case "$t" in
      sunbird-rc) deploy_sunbird_rc ;;
      openg2p) deploy_openg2p ;;
      inji) deploy_inji ;;
      *) die "Unknown target '$t' — expected sunbird-rc, openg2p, and/or inji" ;;
    esac
  done

  log "Done. Point this platform's adapters at these DPGs:"
  echo "  - sunbird-adapter:  SUNBIRD_RC_BASE_URL=http://registry:8091   (already the .env.example default)"
  echo "  - openg2p-sync:     OPENG2P_BASE_URL=http://odoo:8069          (already the .env.example default)"
  echo "  - inji-adapter:     INJI_CERTIFY_BASE_URL=http://certify-nginx:80, INJI_VERIFY_BASE_URL=http://verify-service:8080"
  echo
  echo "This platform's own services (docker-compose.yml / deploy/docker-compose.hostinger.yml)"
  echo "already join 'social-registry-net' where each adapter lives, so no changes are needed there —"
  echo "just restart the relevant adapter container once its DPG is confirmed healthy, so it"
  echo "picks up a live connection instead of its earlier 'unreachable' state."
}

main "$@"
