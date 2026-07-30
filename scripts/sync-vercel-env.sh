#!/usr/bin/env bash
# Sync KEY=VALUE file into Vercel project env. Does not echo secret values.
# Usage: ./scripts/sync-vercel-env.sh .env.prod production
set -euo pipefail

ENV_FILE="${1:-.env.prod}"
TARGET="${2:-production}"
SKIP_KEYS="${SKIP_KEYS:-HOST PORT VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_EMAIL CLOUDFLARE_ZONE_ID CUSTOM_DOMAIN CUSTOM_DOMAIN_WWW}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ -z "${VERCEL_TOKEN:-}" ]]; then
  echo "VERCEL_TOKEN is required" >&2
  exit 1
fi

is_skipped() {
  local key="$1"
  for s in $SKIP_KEYS; do
    [[ "$key" == "$s" ]] && return 0
  done
  return 1
}

count=0
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line#"${line%%[![:space:]]*}"}"
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" != *=* ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  key="${key%"${key##*[![:space:]]}"}"
  key="${key#"${key%%[![:space:]]*}"}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
    value="${value:1:-1}"
  elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
    value="${value:1:-1}"
  fi
  is_skipped "$key" && continue

  vercel env rm "$key" "$TARGET" --yes --token "$VERCEL_TOKEN" >/dev/null 2>&1 || true
  printf '%s' "$value" | vercel env add "$key" "$TARGET" --token "$VERCEL_TOKEN" >/dev/null
  echo "OK  $key"
  count=$((count + 1))
done < "$ENV_FILE"

echo "Synced $count keys to Vercel target=$TARGET"
