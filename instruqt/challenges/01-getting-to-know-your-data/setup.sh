#!/bin/bash
#
# Setup script for Challenge 1: Getting to Know Your Data
#
# Creates Elasticsearch indices from mapping definitions,
# bulk loads the Philadelphia dataset, and verifies everything is ready.
#
# Prerequisites:
#   - Elasticsearch running and accessible via ELASTICSEARCH_URL
#   - Data files in data/processed/ (businesses.ndjson, users.ndjson, reviews.ndjson)
#   - Mapping files in mappings/ directory
#
# Environment variables used:
#   ELASTICSEARCH_URL, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD
#   KIBANA_URL
#

set -e

# ==============================================================================
# Configuration
# ==============================================================================

WORKSHOP_DIR="${WORKSHOP_DIR:-/workspace/workshop/elastic-workflow-workshop}"
DATA_DIR="${WORKSHOP_DIR}/data/processed"
MAPPINGS_DIR="${WORKSHOP_DIR}/mappings"

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

# Auth - use basic auth if credentials are available
CURL_AUTH=""
if [ -n "${ELASTICSEARCH_USER}" ] && [ -n "${ELASTICSEARCH_PASSWORD}" ]; then
    CURL_AUTH="-u ${ELASTICSEARCH_USER}:${ELASTICSEARCH_PASSWORD}"
fi

# Bulk loading settings
BATCH_SIZE=5000

echo "=============================================="
echo "Setting up Challenge 1: Getting to Know Your Data"
echo "=============================================="
echo ""
echo "Workshop directory: ${WORKSHOP_DIR}"
echo "Data directory:     ${DATA_DIR}"
echo "Elasticsearch URL:  ${ELASTICSEARCH_URL}"
echo ""

# ==============================================================================
# Helper functions
# ==============================================================================

es_curl() {
    # Wrapper around curl with auth and common options
    curl -s ${CURL_AUTH} "$@"
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

create_index_from_mapping() {
    # Create an index using a mapping JSON file
    local index="$1"
    local mapping_file="$2"

    if check_index_exists "$index"; then
        echo "  Index '${index}' already exists, skipping."
        return 0
    fi

    local http_code
    http_code=$(es_curl -o /tmp/es_response.json -w "%{http_code}" \
        -X PUT "${ELASTICSEARCH_URL}/${index}" \
        -H "Content-Type: application/json" \
        --data-binary "@${mapping_file}" 2>/dev/null)

    if [ "$http_code" = "200" ]; then
        echo "  Created index: ${index}"
        return 0
    else
        echo "  FAILED to create index '${index}' (HTTP ${http_code})"
        cat /tmp/es_response.json 2>/dev/null
        echo ""
        return 1
    fi
}

create_reviews_index_without_elser() {
    # Fallback: create reviews index without semantic_text fields
    local index="reviews"
    local mapping_file="${MAPPINGS_DIR}/reviews.json"

    echo "  Creating reviews index WITHOUT semantic_text (ELSER not available)..."

    # Use Python to strip semantic_text fields from the mapping
    local modified_mapping
    modified_mapping=$(python3 -c "
import json, sys

with open('${mapping_file}') as f:
    mapping = json.load(f)

props = mapping.get('mappings', {}).get('properties', {})

# Remove semantic_text fields
semantic_fields = set()
for name, defn in list(props.items()):
    if defn.get('type') == 'semantic_text':
        semantic_fields.add(name)
        del props[name]

# Remove copy_to references to semantic fields
for name, defn in props.items():
    if 'copy_to' in defn and defn['copy_to'] in semantic_fields:
        del defn['copy_to']

json.dump(mapping, sys.stdout)
")

    local http_code
    http_code=$(echo "${modified_mapping}" | es_curl -o /tmp/es_response.json -w "%{http_code}" \
        -X PUT "${ELASTICSEARCH_URL}/${index}" \
        -H "Content-Type: application/json" \
        --data-binary @- 2>/dev/null)

    if [ "$http_code" = "200" ]; then
        echo "  Created index: ${index} (without semantic search)"
        return 0
    else
        echo "  FAILED to create index '${index}' (HTTP ${http_code})"
        cat /tmp/es_response.json 2>/dev/null
        echo ""
        return 1
    fi
}

bulk_load() {
    # Bulk load a plain NDJSON file into an Elasticsearch index
    # Converts each line to bulk format: {"index":{}} \n {doc}
    # Processes in batches to avoid overwhelming Elasticsearch
    local index="$1"
    local file="$2"
    local batch_size="${3:-${BATCH_SIZE}}"

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

    # Split the file into batches
    split -l "$batch_size" "$file" "${tmp_dir}/batch_"

    local loaded=0
    local errors=0

    for batch_file in "${tmp_dir}"/batch_*; do
        [ -f "$batch_file" ] || continue

        local batch_count
        batch_count=$(wc -l < "$batch_file")

        # Convert plain NDJSON to bulk format:
        # For each line, prepend {"index":{}}
        awk '{print "{\"index\":{}}"; print}' "$batch_file" > "${batch_file}.bulk"

        # Ensure file ends with newline (required by _bulk API)
        echo "" >> "${batch_file}.bulk"

        # Send to Elasticsearch
        local response
        response=$(es_curl -w "\n%{http_code}" \
            -X POST "${ELASTICSEARCH_URL}/${index}/_bulk" \
            -H "Content-Type: application/x-ndjson" \
            --data-binary "@${batch_file}.bulk" 2>/dev/null)

        local http_code
        http_code=$(echo "$response" | tail -1)

        # Check for errors in response
        local has_errors="false"
        if echo "$response" | head -1 | grep -q '"errors":true'; then
            has_errors="true"
            errors=$((errors + 1))
        fi

        loaded=$((loaded + batch_count))

        if [ "$has_errors" = "true" ]; then
            echo "  [${loaded}/${total}] Batch loaded with some errors (HTTP ${http_code})"
        else
            echo "  [${loaded}/${total}] OK (HTTP ${http_code})"
        fi

        # Clean up batch files
        rm -f "$batch_file" "${batch_file}.bulk"
    done

    echo "  Done: ${loaded} documents loaded into '${index}'"
    if [ "$errors" -gt 0 ]; then
        echo "  Warning: ${errors} batch(es) had errors (documents may still have been indexed)"
    fi
}


# ==============================================================================
# Step 1: Wait for Elasticsearch
# ==============================================================================
echo "[1/7] Waiting for Elasticsearch..."
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
# Step 2: Check ELSER availability
# ==============================================================================
echo ""
echo "[2/7] Checking ELSER inference endpoint..."

ELSER_AVAILABLE=false
ELSER_RESPONSE=$(es_curl "${ELASTICSEARCH_URL}/_inference/.elser-2-elasticsearch" 2>/dev/null)
if echo "$ELSER_RESPONSE" | grep -q '"inference_id"'; then
    ELSER_AVAILABLE=true
    echo "  ELSER (.elser-2-elasticsearch) is available - semantic search will be enabled"
else
    echo "  ELSER not available - reviews index will be created without semantic search"
    echo "  (Semantic search can be added later by reindexing after deploying ELSER)"
fi

# ==============================================================================
# Step 3: Create indices from mapping files
# ==============================================================================
echo ""
echo "[3/7] Creating indices..."

# Create lookup indices (businesses, users) and operational indices (incidents, notifications)
for index in businesses users incidents notifications; do
    mapping_file="${MAPPINGS_DIR}/${index}.json"
    if [ -f "$mapping_file" ]; then
        create_index_from_mapping "$index" "$mapping_file"
    else
        echo "  WARNING: Mapping file not found: ${mapping_file}"
    fi
done

# Create reviews index (with or without ELSER)
if ! check_index_exists "reviews"; then
    if [ "$ELSER_AVAILABLE" = true ]; then
        create_index_from_mapping "reviews" "${MAPPINGS_DIR}/reviews.json"
    else
        create_reviews_index_without_elser
    fi
else
    echo "  Index 'reviews' already exists, skipping."
fi

# ==============================================================================
# Step 4: Load data from NDJSON files
# ==============================================================================
echo ""
echo "[4/7] Loading data..."

# Check that data files exist
MISSING_FILES=0
for file in businesses.ndjson users.ndjson reviews.ndjson; do
    if [ ! -f "${DATA_DIR}/${file}" ]; then
        echo "  ERROR: Missing data file: ${DATA_DIR}/${file}"
        MISSING_FILES=$((MISSING_FILES + 1))
    fi
done

if [ "$MISSING_FILES" -gt 0 ]; then
    echo ""
    echo "  Data files must be placed in ${DATA_DIR}/"
    echo "  Expected files:"
    echo "    - businesses.ndjson"
    echo "    - users.ndjson"
    echo "    - reviews.ndjson"
    echo ""
    echo "  Generate them with: python admin/generate_philly_dataset.py --count 100"
    exit 1
fi

# Load each dataset (skip if already loaded)
BUSINESS_COUNT=$(get_doc_count "businesses")
if [ "${BUSINESS_COUNT:-0}" -lt 50 ]; then
    bulk_load "businesses" "${DATA_DIR}/businesses.ndjson"
else
    echo "  Businesses already loaded (${BUSINESS_COUNT} documents)"
fi

USER_COUNT=$(get_doc_count "users")
if [ "${USER_COUNT:-0}" -lt 100 ]; then
    bulk_load "users" "${DATA_DIR}/users.ndjson"
else
    echo "  Users already loaded (${USER_COUNT} documents)"
fi

REVIEW_COUNT=$(get_doc_count "reviews")
if [ "${REVIEW_COUNT:-0}" -lt 100 ]; then
    bulk_load "reviews" "${DATA_DIR}/reviews.ndjson"
else
    echo "  Reviews already loaded (${REVIEW_COUNT} documents)"
fi

# ==============================================================================
# Step 5: Refresh indices
# ==============================================================================
echo ""
echo "[5/7] Refreshing indices..."
es_curl -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null
echo "  Indices refreshed."

# ==============================================================================
# Step 6: Wait for Kibana
# ==============================================================================
echo ""
echo "[6/7] Waiting for Kibana..."
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
# Step 7: Enable Elastic Workflows
# ==============================================================================
echo ""
echo "[7/7] Enabling Elastic Workflows..."

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
# Final status
# ==============================================================================
echo ""
echo "=============================================="
echo "Challenge 1 Setup Complete!"
echo "=============================================="
echo ""
echo "Indices:"
for index in businesses users reviews incidents notifications; do
    count=$(get_doc_count "$index")
    echo "  - ${index}: ${count} documents"
done

echo ""
if [ "$ELSER_AVAILABLE" = true ]; then
    echo "Semantic search: ENABLED (ELSER)"
else
    echo "Semantic search: DISABLED (ELSER not available)"
fi

if [ "$WORKFLOWS_HTTP" = "200" ]; then
    echo "Workflows UI:    ENABLED"
else
    echo "Workflows UI:    NOT ENABLED (enable manually via Dev Tools)"
fi

echo ""
echo "You can now begin exploring the data in Kibana!"
echo ""
