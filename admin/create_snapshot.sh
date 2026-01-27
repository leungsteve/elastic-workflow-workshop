#!/bin/bash
#
# Create Snapshot for Workshop Fast Setup
#
# One-time script run against an Elastic Cloud cluster with ELSER.
# Ingests the full 200-business dataset, waits for ELSER inference,
# then snapshots all indices to a GCS repository.
#
# Usage:
#   export ELASTICSEARCH_URL="https://my-cloud-cluster:9243"
#   export ELASTICSEARCH_API_KEY="base64-encoded-api-key"
#   export GCS_BUCKET="my-workshop-bucket"
#   ./admin/create_snapshot.sh
#
# Prerequisites:
#   - Elastic Cloud cluster with ELSER deployed
#   - GCS bucket created and accessible from the cluster
#   - GCS credentials configured in the cluster keystore
#   - Data files generated: python -m admin.generate_philly_dataset --count 200
#
# Environment variables:
#   ELASTICSEARCH_URL       Elasticsearch endpoint (required)
#   ELASTICSEARCH_API_KEY   API key for auth (use this OR user/password)
#   ELASTICSEARCH_USER      Basic auth username
#   ELASTICSEARCH_PASSWORD  Basic auth password
#   GCS_BUCKET              GCS bucket name (required)
#   GCS_BASE_PATH           Path prefix in bucket (default: elastic-workshop)
#   SNAPSHOT_REPO           Repository name (default: workshop-snapshots)
#   SNAPSHOT_NAME           Snapshot name (default: snapshot-v1)
#

set -e

# ==============================================================================
# Configuration
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DATA_DIR="${PROJECT_ROOT}/data/processed"
MAPPINGS_DIR="${PROJECT_ROOT}/mappings"

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:?ELASTICSEARCH_URL must be set}"
GCS_BUCKET="${GCS_BUCKET:?GCS_BUCKET must be set}"
GCS_BASE_PATH="${GCS_BASE_PATH:-elastic-whats-new-9.3.0/data/snapshot}"
SNAPSHOT_REPO="${SNAPSHOT_REPO:-workshop-snapshots}"
SNAPSHOT_NAME="${SNAPSHOT_NAME:-snapshot-v1}"

INDICES="businesses users reviews incidents notifications"

echo "=============================================="
echo "  Create Workshop Snapshot"
echo "=============================================="
echo ""
echo "Elasticsearch URL: ${ELASTICSEARCH_URL}"
echo "GCS bucket:        ${GCS_BUCKET}/${GCS_BASE_PATH}"
echo "Snapshot repo:     ${SNAPSHOT_REPO}"
echo "Snapshot name:     ${SNAPSHOT_NAME}"
echo "Data directory:    ${DATA_DIR}"
echo ""

# ==============================================================================
# Helper functions
# ==============================================================================

es_curl() {
    # Wrapper around curl with auth and common options
    # Supports both API key and basic auth
    if [ -n "${ELASTICSEARCH_API_KEY}" ]; then
        curl -s -H "Authorization: ApiKey ${ELASTICSEARCH_API_KEY}" "$@"
    elif [ -n "${ELASTICSEARCH_USER}" ] && [ -n "${ELASTICSEARCH_PASSWORD}" ]; then
        curl -s -u "${ELASTICSEARCH_USER}:${ELASTICSEARCH_PASSWORD}" "$@"
    else
        echo "ERROR: Set ELASTICSEARCH_API_KEY or ELASTICSEARCH_USER/ELASTICSEARCH_PASSWORD" >&2
        exit 1
    fi
}

check_index_exists() {
    local index="$1"
    local http_code
    http_code=$(es_curl -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/${index}" 2>/dev/null)
    [ "$http_code" = "200" ]
}

get_doc_count() {
    local index="$1"
    es_curl "${ELASTICSEARCH_URL}/${index}/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0"
}

bulk_load() {
    local index="$1"
    local file="$2"
    local batch_size=5000

    if [ ! -f "$file" ]; then
        echo "  ERROR: File not found: ${file}"
        return 1
    fi

    local total
    total=$(wc -l < "$file")
    echo "  Loading ${total} documents into '${index}'..."

    local tmp_dir
    tmp_dir=$(mktemp -d)
    trap "rm -rf ${tmp_dir}" RETURN

    split -l "$batch_size" "$file" "${tmp_dir}/batch_"

    local loaded=0

    for batch_file in "${tmp_dir}"/batch_*; do
        [ -f "$batch_file" ] || continue

        local batch_count
        batch_count=$(wc -l < "$batch_file")

        awk '{print "{\"index\":{}}"; print}' "$batch_file" > "${batch_file}.bulk"
        echo "" >> "${batch_file}.bulk"

        local response
        response=$(es_curl -w "\n%{http_code}" \
            -X POST "${ELASTICSEARCH_URL}/${index}/_bulk" \
            -H "Content-Type: application/x-ndjson" \
            --data-binary "@${batch_file}.bulk" 2>/dev/null)

        local http_code
        http_code=$(echo "$response" | tail -1)

        loaded=$((loaded + batch_count))
        echo "  [${loaded}/${total}] (HTTP ${http_code})"

        rm -f "$batch_file" "${batch_file}.bulk"
    done

    echo "  Done: ${loaded} documents loaded into '${index}'"
}

# ==============================================================================
# Step 1: Validate prerequisites
# ==============================================================================
echo "[1/7] Validating prerequisites..."

# Check Elasticsearch is reachable
CLUSTER_INFO=$(es_curl "${ELASTICSEARCH_URL}" 2>/dev/null)
if ! echo "$CLUSTER_INFO" | grep -q '"cluster_name"'; then
    echo "  ERROR: Cannot reach Elasticsearch at ${ELASTICSEARCH_URL}"
    echo "  Response: ${CLUSTER_INFO}"
    exit 1
fi
CLUSTER_NAME=$(echo "$CLUSTER_INFO" | grep -o '"cluster_name":"[^"]*"' | cut -d'"' -f4)
echo "  Cluster: ${CLUSTER_NAME}"

# Check ELSER availability
ELSER_RESPONSE=$(es_curl "${ELASTICSEARCH_URL}/_inference/.elser-2-elasticsearch" 2>/dev/null)
if echo "$ELSER_RESPONSE" | grep -q '"inference_id"'; then
    echo "  ELSER: available"
else
    echo "  ERROR: ELSER inference endpoint not found."
    echo "  Deploy ELSER on this cluster before creating the snapshot."
    echo "  Response: ${ELSER_RESPONSE}"
    exit 1
fi

# Check data files exist
MISSING_FILES=0
for file in businesses.ndjson users.ndjson reviews.ndjson; do
    if [ ! -f "${DATA_DIR}/${file}" ]; then
        echo "  ERROR: Missing data file: ${DATA_DIR}/${file}"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
done
if [ "$MISSING_FILES" -gt 0 ]; then
    echo ""
    echo "  Generate data first:"
    echo "    python -m admin.generate_philly_dataset --count 200"
    exit 1
fi
echo "  Data files: present"

# ==============================================================================
# Step 2: Delete and recreate indices
# ==============================================================================
echo ""
echo "[2/7] Creating indices..."

for index in $INDICES; do
    if check_index_exists "$index"; then
        es_curl -o /dev/null -X DELETE "${ELASTICSEARCH_URL}/${index}" 2>/dev/null
        echo "  Deleted existing index: ${index}"
    fi
done

for index in $INDICES; do
    mapping_file="${MAPPINGS_DIR}/${index}.json"
    if [ -f "$mapping_file" ]; then
        local_http_code=$(es_curl -o /tmp/es_response.json -w "%{http_code}" \
            -X PUT "${ELASTICSEARCH_URL}/${index}" \
            -H "Content-Type: application/json" \
            --data-binary "@${mapping_file}" 2>/dev/null)
        if [ "$local_http_code" = "200" ]; then
            echo "  Created index: ${index}"
        else
            echo "  FAILED to create index '${index}' (HTTP ${local_http_code})"
            cat /tmp/es_response.json 2>/dev/null
            echo ""
            exit 1
        fi
    else
        echo "  WARNING: Mapping file not found: ${mapping_file}"
    fi
done

# ==============================================================================
# Step 3: Bulk load data
# ==============================================================================
echo ""
echo "[3/7] Loading data..."

bulk_load "businesses" "${DATA_DIR}/businesses.ndjson"
bulk_load "users" "${DATA_DIR}/users.ndjson"
bulk_load "reviews" "${DATA_DIR}/reviews.ndjson"

es_curl -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null
echo "  Indices refreshed."

# ==============================================================================
# Step 4: Wait for ELSER inference to complete
# ==============================================================================
echo ""
echo "[4/7] Waiting for ELSER inference to complete..."

# ELSER processes documents asynchronously via the ingest pipeline.
# Poll until the number of documents with a populated semantic field
# matches the total review count, or until inference tasks are done.
MAX_WAIT=600  # 10 minutes max
WAIT_INTERVAL=10
ELAPSED=0
TOTAL_REVIEWS=$(get_doc_count "reviews")

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check if there are any active inference tasks
    TASKS=$(es_curl "${ELASTICSEARCH_URL}/_cat/tasks?v&actions=*inference*" 2>/dev/null)
    BULK_TASKS=$(es_curl "${ELASTICSEARCH_URL}/_cat/tasks?v&actions=*bulk*" 2>/dev/null)

    ACTIVE_INFERENCE=$(echo "$TASKS" | grep -c "inference" 2>/dev/null || true)
    ACTIVE_BULK=$(echo "$BULK_TASKS" | grep -c "bulk" 2>/dev/null || true)

    if [ "$ACTIVE_INFERENCE" -eq 0 ] && [ "$ACTIVE_BULK" -eq 0 ]; then
        # Double-check: refresh and verify doc count is stable
        es_curl -X POST "${ELASTICSEARCH_URL}/reviews/_refresh" > /dev/null
        CURRENT_COUNT=$(get_doc_count "reviews")
        echo "  No active inference/bulk tasks. Review count: ${CURRENT_COUNT}"
        break
    fi

    echo "  Active tasks: ${ACTIVE_INFERENCE} inference, ${ACTIVE_BULK} bulk (${ELAPSED}s elapsed)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "  WARNING: Timed out waiting for inference. Snapshot may contain incomplete embeddings."
fi

# Final refresh
es_curl -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null

echo ""
echo "  Document counts:"
for index in $INDICES; do
    count=$(get_doc_count "$index")
    echo "    ${index}: ${count}"
done

# ==============================================================================
# Step 5: Register GCS snapshot repository
# ==============================================================================
echo ""
echo "[5/7] Registering GCS snapshot repository..."

REPO_RESPONSE=$(es_curl -w "\n%{http_code}" \
    -X PUT "${ELASTICSEARCH_URL}/_snapshot/${SNAPSHOT_REPO}" \
    -H "Content-Type: application/json" \
    -d "{
        \"type\": \"gcs\",
        \"settings\": {
            \"bucket\": \"${GCS_BUCKET}\",
            \"base_path\": \"${GCS_BASE_PATH}\"
        }
    }" 2>/dev/null)

REPO_HTTP=$(echo "$REPO_RESPONSE" | tail -1)
if [ "$REPO_HTTP" = "200" ]; then
    echo "  Repository '${SNAPSHOT_REPO}' registered."
else
    echo "  FAILED to register repository (HTTP ${REPO_HTTP})"
    echo "$REPO_RESPONSE" | head -1
    exit 1
fi

# ==============================================================================
# Step 6: Take snapshot
# ==============================================================================
echo ""
echo "[6/7] Taking snapshot '${SNAPSHOT_NAME}'..."

SNAP_RESPONSE=$(es_curl -w "\n%{http_code}" \
    -X PUT "${ELASTICSEARCH_URL}/_snapshot/${SNAPSHOT_REPO}/${SNAPSHOT_NAME}?wait_for_completion=false" \
    -H "Content-Type: application/json" \
    -d "{
        \"indices\": \"$(echo $INDICES | tr ' ' ',')\",
        \"ignore_unavailable\": true,
        \"include_global_state\": false
    }" 2>/dev/null)

SNAP_HTTP=$(echo "$SNAP_RESPONSE" | tail -1)
if [ "$SNAP_HTTP" = "200" ]; then
    echo "  Snapshot initiated."
else
    echo "  FAILED to initiate snapshot (HTTP ${SNAP_HTTP})"
    echo "$SNAP_RESPONSE" | head -1
    exit 1
fi

# ==============================================================================
# Step 7: Wait for snapshot completion
# ==============================================================================
echo ""
echo "[7/7] Waiting for snapshot to complete..."

MAX_WAIT=600
WAIT_INTERVAL=10
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(es_curl "${ELASTICSEARCH_URL}/_snapshot/${SNAPSHOT_REPO}/${SNAPSHOT_NAME}" 2>/dev/null)
    STATE=$(echo "$STATUS_RESPONSE" | grep -o '"state":"[^"]*"' | head -1 | cut -d'"' -f4)

    if [ "$STATE" = "SUCCESS" ]; then
        echo "  Snapshot completed successfully!"
        break
    elif [ "$STATE" = "FAILED" ] || [ "$STATE" = "PARTIAL" ]; then
        echo "  ERROR: Snapshot ended with state: ${STATE}"
        echo "$STATUS_RESPONSE"
        exit 1
    fi

    echo "  State: ${STATE:-UNKNOWN} (${ELAPSED}s elapsed)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "  WARNING: Timed out waiting for snapshot completion."
    echo "  Check status manually:"
    echo "    GET _snapshot/${SNAPSHOT_REPO}/${SNAPSHOT_NAME}"
    exit 1
fi

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "=============================================="
echo "  Snapshot Created Successfully!"
echo "=============================================="
echo ""
echo "Repository:  ${SNAPSHOT_REPO}"
echo "Snapshot:    ${SNAPSHOT_NAME}"
echo "GCS bucket:  gs://${GCS_BUCKET}/${GCS_BASE_PATH}"
echo ""
echo "Indices:"
for index in $INDICES; do
    count=$(get_doc_count "$index")
    echo "  - ${index}: ${count} documents"
done
echo ""
echo "To restore on Instruqt, set these env vars in the setup script:"
echo "  GCS_BUCKET=${GCS_BUCKET}"
echo "  GCS_BASE_PATH=${GCS_BASE_PATH}"
echo "  SNAPSHOT_REPO=${SNAPSHOT_REPO}"
echo "  SNAPSHOT_NAME=${SNAPSHOT_NAME}"
echo ""
