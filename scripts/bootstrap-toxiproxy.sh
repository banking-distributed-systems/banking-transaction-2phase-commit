#!/bin/sh
set -eu

TOXIPROXY_API="${TOXIPROXY_API:-http://toxiproxy:8474}"
PROXY_NAME="${PROXY_NAME:-vbank_api}"
PROXY_LISTEN="${PROXY_LISTEN:-0.0.0.0:8666}"
PROXY_UPSTREAM="${PROXY_UPSTREAM:-host.docker.internal:5000}"

printf '%s\n' "[toxiproxy-bootstrap] Waiting for ${TOXIPROXY_API} ..."

attempt=0
until curl -fsS "${TOXIPROXY_API}/proxies" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    printf '%s\n' "[toxiproxy-bootstrap] Timeout waiting for toxiproxy API"
    exit 1
  fi
  sleep 1
done

printf '%s\n' "[toxiproxy-bootstrap] Toxiproxy API is ready"

curl -fsS -X DELETE "${TOXIPROXY_API}/proxies/${PROXY_NAME}" >/dev/null 2>&1 || true

payload=$(printf '{"name":"%s","listen":"%s","upstream":"%s"}' "${PROXY_NAME}" "${PROXY_LISTEN}" "${PROXY_UPSTREAM}")

create_resp=$(curl -fsS -X POST "${TOXIPROXY_API}/proxies" \
  -H "Content-Type: application/json" \
  -d "${payload}")

printf '%s\n' "[toxiproxy-bootstrap] Proxy created: ${create_resp}"
