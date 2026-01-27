#!/bin/bash
#
# Kubernetes VM Startup Script
#
# Runs on the kubernetes-vm to restore the workshop snapshot from GCS.
# This replaces bulk data loading — all indices come pre-built with ELSER embeddings.
#
# Prerequisites:
#   - ECK-managed Elasticsearch running in the default namespace
#   - GCS credentials available via the "education" client in the ES keystore
#   - Snapshot created via admin/create_snapshot.sh
#
# Usage:
#   ./startup.sh
#

set -e

# ==============================================================================
# Configuration
# ==============================================================================

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

# Snapshot settings
GCS_BUCKET="${GCS_BUCKET:-instruqt-workshop-snapshot-public}"
GCS_BASE_PATH="${GCS_BASE_PATH:-elastic-whats-new-9.3.0/data/snapshot}"
GCS_CLIENT="${GCS_CLIENT:-education}"
SNAPSHOT_REPO="${SNAPSHOT_REPO:-workshop-snapshots}"
SNAPSHOT_NAME="${SNAPSHOT_NAME:-snapshot-v1}"

INDICES="businesses,users,reviews,incidents,notifications"

echo "=============================================="
echo "  Workshop Snapshot Restore"
echo "=============================================="
echo ""

# ==============================================================================
# Step 1: Wait for Elasticsearch pod to be ready
# ==============================================================================
echo "[1/7] Waiting for Elasticsearch pod..."

MAX_RETRIES=60
RETRY_COUNT=0

until kubectl get pod elasticsearch-es-default-0 -n default -o jsonpath='{.status.phase}' 2>/dev/null | grep -q "Running"; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "  ERROR: Elasticsearch pod did not become ready"
        exit 1
    fi
    echo "  Waiting for pod... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Pod is running."

# ==============================================================================
# Step 2: Get elastic user password
# ==============================================================================
echo ""
echo "[2/7] Retrieving elastic user credentials..."

ES_PASSWORD=$(kubectl get secret elasticsearch-es-elastic-user -n default -o jsonpath='{.data.elastic}' | base64 -d)
if [ -z "$ES_PASSWORD" ]; then
    echo "  ERROR: Could not retrieve elastic user password"
    exit 1
fi
CURL_AUTH="-u elastic:${ES_PASSWORD}"
echo "  Credentials retrieved."

# Helper function
es_curl() {
    curl -s ${CURL_AUTH} "$@"
}

# ==============================================================================
# Step 3: Wait for Elasticsearch cluster health
# ==============================================================================
echo ""
echo "[3/7] Waiting for Elasticsearch cluster..."

MAX_RETRIES=60
RETRY_COUNT=0

until es_curl "${ELASTICSEARCH_URL}/_cluster/health" 2>/dev/null | grep -q '"status":"green"\|"status":"yellow"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "  ERROR: Elasticsearch cluster did not become ready"
        exit 1
    fi
    echo "  Waiting for cluster health... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Cluster is ready."

# ==============================================================================
# Step 4: Delete existing indices
# ==============================================================================
echo ""
echo "[4/7] Deleting existing indices..."

DELETE_RESPONSE=$(es_curl -o /dev/null -w "%{http_code}" \
    -X DELETE "${ELASTICSEARCH_URL}/${INDICES}" 2>/dev/null)

if [ "$DELETE_RESPONSE" = "200" ]; then
    echo "  Deleted existing indices."
elif [ "$DELETE_RESPONSE" = "404" ]; then
    echo "  No existing indices to delete."
else
    echo "  Warning: Delete returned HTTP ${DELETE_RESPONSE} (continuing anyway)"
fi

# ==============================================================================
# Step 5: Register GCS snapshot repository (read-only)
# ==============================================================================
echo ""
echo "[5/7] Registering GCS snapshot repository..."

REPO_RESPONSE=$(es_curl -w "\n%{http_code}" \
    -X PUT "${ELASTICSEARCH_URL}/_snapshot/${SNAPSHOT_REPO}?verify=false" \
    -H "Content-Type: application/json" \
    -d "{
        \"type\": \"gcs\",
        \"settings\": {
            \"bucket\": \"${GCS_BUCKET}\",
            \"base_path\": \"${GCS_BASE_PATH}\",
            \"client\": \"${GCS_CLIENT}\",
            \"readonly\": true
        }
    }" 2>/dev/null)

REPO_HTTP=$(echo "$REPO_RESPONSE" | tail -1)
if [ "$REPO_HTTP" = "200" ]; then
    echo "  Repository '${SNAPSHOT_REPO}' registered (readonly, client=${GCS_CLIENT})."
else
    echo "  FAILED to register repository (HTTP ${REPO_HTTP})"
    echo "$REPO_RESPONSE" | head -1
    exit 1
fi

# ==============================================================================
# Step 6: Restore snapshot
# ==============================================================================
echo ""
echo "[6/7] Restoring snapshot '${SNAPSHOT_NAME}'..."

RESTORE_RESPONSE=$(es_curl -w "\n%{http_code}" \
    -X POST "${ELASTICSEARCH_URL}/_snapshot/${SNAPSHOT_REPO}/${SNAPSHOT_NAME}/_restore?wait_for_completion=false" \
    -H "Content-Type: application/json" \
    -d "{
        \"indices\": \"${INDICES}\",
        \"ignore_unavailable\": true,
        \"include_global_state\": false
    }" 2>/dev/null)

RESTORE_HTTP=$(echo "$RESTORE_RESPONSE" | tail -1)
if [ "$RESTORE_HTTP" = "200" ]; then
    echo "  Restore initiated."
else
    echo "  FAILED to initiate restore (HTTP ${RESTORE_HTTP})"
    echo "$RESTORE_RESPONSE" | head -1
    exit 1
fi

# ==============================================================================
# Step 7: Wait for restore completion
# ==============================================================================
echo ""
echo "[7/7] Waiting for restore to complete..."

MAX_WAIT=300
WAIT_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    RECOVERY=$(es_curl "${ELASTICSEARCH_URL}/_cat/recovery?active_only=true&h=index,stage" 2>/dev/null)

    if [ -z "$RECOVERY" ] || [ "$RECOVERY" = "" ]; then
        echo "  All indices restored."
        break
    fi

    RECOVERING_COUNT=$(echo "$RECOVERY" | grep -c "." 2>/dev/null || true)
    echo "  Recovering: ${RECOVERING_COUNT} shard(s) in progress (${ELAPSED}s elapsed)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "  WARNING: Timed out waiting for restore."
fi

# Refresh
es_curl -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "=============================================="
echo "  Snapshot Restore Complete"
echo "=============================================="
echo ""
echo "Indices:"
for index in businesses users reviews incidents notifications; do
    count=$(es_curl "${ELASTICSEARCH_URL}/${index}/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
    echo "  - ${index}: ${count} documents"
done
echo ""
echo "Semantic search: ENABLED (restored from ELSER-processed snapshot)"
echo ""
