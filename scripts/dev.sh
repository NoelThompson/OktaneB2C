#!/usr/bin/env bash
# Bring up all three services with prefixed, interleaved logs. Ctrl-C stops all.
set -euo pipefail

cd "$(dirname "$0")/.."

pids=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

run() {
  local label=$1
  shift
  "$@" 2>&1 | sed -u "s/^/[$label] /" &
  pids+=("$!")
}

# Enforce scope on the MCP server by default. In mock mode the agent mints the
# tokens and serves the matching JWKS, so this is a real verification against a
# local issuer — not a bypass. Override any of these from the environment.
AGENT_BASE=${AGENT_PUBLIC_BASE:-http://localhost:8788}
export MCP_REQUIRE_AUTH=${MCP_REQUIRE_AUTH:-true}
export OKTA_CATALOG_ISSUER=${OKTA_CATALOG_ISSUER:-$AGENT_BASE/mock-as/catalog}
export OKTA_ORDERS_ISSUER=${OKTA_ORDERS_ISSUER:-$AGENT_BASE/mock-as/orders}

# MCP first: the agent's startup probe expects it, and the web app reads the
# catalog through the agent.
run mcp   npm run dev --workspace=packages/mcp-server
sleep 2
run agent ./scripts/dev-agent.sh
sleep 2
run web   npm run dev --workspace=apps/web

echo
echo "  storefront  http://localhost:3000"
echo "  agent       http://localhost:8788/healthz"
echo "  mcp         http://localhost:8787/healthz"
echo

wait
