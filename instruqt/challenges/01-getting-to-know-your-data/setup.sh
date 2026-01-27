#!/bin/bash
#
# Setup script for Challenge 1: Getting to Know Your Data
#
# Runs on host-1. Assumes the kubernetes-vm startup.sh has already
# restored the snapshot (indices + ELSER embeddings).
#
# This script:
#   1. Waits for Elasticsearch to be reachable
#   2. Verifies the snapshot restore completed (indices exist with data)
#   3. Waits for Kibana
#   4. Enables Workflows UI
#   5. Starts the FastAPI application
#
# Environment variables used:
#   ELASTICSEARCH_URL, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD
#   KIBANA_URL, WORKSHOP_DIR
#

set -e

# ==============================================================================
# Configuration
# ==============================================================================

WORKSHOP_DIR="${WORKSHOP_DIR:-/workspace/workshop/elastic-workflow-workshop}"

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

# Auth - use basic auth if credentials are available, or get from k8s secret
CURL_AUTH=""
if [ -n "${ELASTICSEARCH_USER}" ] && [ -n "${ELASTICSEARCH_PASSWORD}" ]; then
    CURL_AUTH="-u ${ELASTICSEARCH_USER}:${ELASTICSEARCH_PASSWORD}"
elif command -v kubectl &>/dev/null; then
    ES_PASSWORD=$(kubectl get secret elasticsearch-es-elastic-user -n default -o jsonpath='{.data.elastic}' 2>/dev/null | base64 -d 2>/dev/null)
    if [ -n "$ES_PASSWORD" ]; then
        CURL_AUTH="-u elastic:${ES_PASSWORD}"
    fi
fi

echo "=============================================="
echo "Setting up Challenge 1: Getting to Know Your Data"
echo "=============================================="
echo ""
echo "Workshop directory: ${WORKSHOP_DIR}"
echo "Elasticsearch URL:  ${ELASTICSEARCH_URL}"
echo ""

# ==============================================================================
# Helper functions
# ==============================================================================

es_curl() {
    curl -s ${CURL_AUTH} "$@"
}

get_doc_count() {
    local index="$1"
    es_curl "${ELASTICSEARCH_URL}/${index}/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0"
}

# ==============================================================================
# Step 1: Wait for Elasticsearch
# ==============================================================================
echo "[1/5] Waiting for Elasticsearch..."
MAX_RETRIES=60
RETRY_COUNT=0

until es_curl "${ELASTICSEARCH_URL}/_cluster/health" 2>/dev/null | grep -q '"status":"green"\|"status":"yellow"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Elasticsearch did not become ready in time"
        exit 1
    fi
    echo "  Waiting for Elasticsearch... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Elasticsearch is ready!"

# ==============================================================================
# Step 2: Verify snapshot restore completed
# ==============================================================================
echo ""
echo "[2/5] Verifying snapshot restore..."

MAX_RETRIES=60
RETRY_COUNT=0
ALL_PRESENT=false

until [ "$ALL_PRESENT" = true ]; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "  ERROR: Indices not available after waiting. Check kubernetes-vm startup.sh."
        exit 1
    fi

    ALL_PRESENT=true
    for index in businesses users reviews; do
        count=$(get_doc_count "$index")
        if [ "$count" = "0" ] || [ -z "$count" ]; then
            ALL_PRESENT=false
            break
        fi
    done

    if [ "$ALL_PRESENT" = false ]; then
        echo "  Waiting for restored indices to be available... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
        sleep 5
    fi
done

echo "  Snapshot restore verified:"
for index in businesses users reviews incidents notifications; do
    count=$(get_doc_count "$index")
    echo "    ${index}: ${count} documents"
done

# ==============================================================================
# Step 3: Wait for Kibana
# ==============================================================================
echo ""
echo "[3/5] Waiting for Kibana..."
MAX_RETRIES=30
RETRY_COUNT=0

until es_curl "${KIBANA_URL}/api/status" 2>/dev/null | grep -q '"level":"available"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "  Warning: Kibana may not be fully ready yet, but setup can continue."
        break
    fi
    echo "  Waiting for Kibana... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Kibana is ready!"

# ==============================================================================
# Step 4: Enable Elastic Workflows
# ==============================================================================
echo ""
echo "[4/5] Enabling Elastic Workflows..."

WORKFLOWS_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "${KIBANA_URL}/internal/kibana/settings" \
    -H "Content-Type: application/json" \
    -H "kbn-xsrf: true" \
    ${CURL_AUTH} \
    -d '{"changes": {"workflows:ui:enabled": true}}' 2>/dev/null)

WORKFLOWS_HTTP=$(echo "$WORKFLOWS_RESPONSE" | tail -1)
if [ "$WORKFLOWS_HTTP" = "200" ]; then
    echo "  Workflows UI enabled successfully"
else
    echo "  Warning: Could not enable Workflows UI (HTTP ${WORKFLOWS_HTTP})"
    echo "  You can enable it manually in Kibana Dev Tools:"
    echo "    POST kbn://internal/kibana/settings"
    echo '    {"changes": {"workflows:ui:enabled": true}}'
fi

# ==============================================================================
# Step 5: Start the FastAPI application
# ==============================================================================
echo ""
echo "[5/5] Starting the FastAPI application..."

cd ${WORKSHOP_DIR}
pip install -r requirements.txt > /tmp/pip_install.log 2>&1
echo "  Dependencies installed."

nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/app.log 2>&1 &

# Wait for app to be ready
APP_RETRIES=0
APP_MAX_RETRIES=30
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    APP_RETRIES=$((APP_RETRIES + 1))
    if [ $APP_RETRIES -ge $APP_MAX_RETRIES ]; then
        echo "  Warning: App did not become ready in time. Check /tmp/app.log for details."
        break
    fi
    sleep 2
done

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "  FastAPI application is running at http://localhost:8000"
else
    echo "  Warning: App may still be starting. Check /tmp/app.log"
fi

# ==============================================================================
# Final status
# ==============================================================================
echo ""
echo "=============================================="
echo "Challenge 1 Setup Complete!"
echo "=============================================="
echo ""
echo "Indices (restored from snapshot):"
for index in businesses users reviews incidents notifications; do
    count=$(get_doc_count "$index")
    echo "  - ${index}: ${count} documents"
done

echo ""
echo "Semantic search: ENABLED (restored from ELSER-processed snapshot)"

if [ "$WORKFLOWS_HTTP" = "200" ]; then
    echo "Workflows UI:    ENABLED"
else
    echo "Workflows UI:    NOT ENABLED (enable manually via Dev Tools)"
fi

echo ""
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "FastAPI App:     RUNNING (http://localhost:8000)"
    echo "ElasticEats UI:  http://localhost:8000/elasticeats"
else
    echo "FastAPI App:     NOT RUNNING (check /tmp/app.log)"
fi
echo ""
echo "You can now begin exploring the data in Kibana!"
echo ""
