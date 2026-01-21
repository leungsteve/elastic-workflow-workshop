#!/bin/bash
#
# Setup script for Challenge 1: Getting to Know Your Data
# Ensures indices are created and sample data is loaded
#
# This script is idempotent - safe to run multiple times
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
WORKSHOP_DIR="${WORKSHOP_DIR:-/workshop}"

echo "=============================================="
echo "Setting up Challenge 1: Getting to Know Your Data"
echo "=============================================="

# ----------------------------------------------
# Wait for Elasticsearch to be ready
# ----------------------------------------------
echo ""
echo "[1/5] Waiting for Elasticsearch..."
MAX_RETRIES=60
RETRY_COUNT=0

until curl -s "${ELASTICSEARCH_URL}/_cluster/health" 2>/dev/null | grep -q '"status":"green"\|"status":"yellow"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Elasticsearch did not become ready in time"
        exit 1
    fi
    echo "  Waiting for Elasticsearch... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Elasticsearch is ready!"

# ----------------------------------------------
# Create indices with proper mappings
# ----------------------------------------------
echo ""
echo "[2/5] Creating indices..."

# Create businesses index
if ! curl -s -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/businesses" 2>/dev/null | grep -q "200"; then
    echo "  Creating businesses index..."
    curl -s -X PUT "${ELASTICSEARCH_URL}/businesses" -H "Content-Type: application/json" -d '{
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "business_id": { "type": "keyword" },
                "name": {
                    "type": "text",
                    "fields": { "keyword": { "type": "keyword" } }
                },
                "address": { "type": "text" },
                "city": { "type": "keyword" },
                "state": { "type": "keyword" },
                "postal_code": { "type": "keyword" },
                "latitude": { "type": "float" },
                "longitude": { "type": "float" },
                "stars": { "type": "float" },
                "review_count": { "type": "integer" },
                "is_open": { "type": "boolean" },
                "categories": { "type": "keyword" },
                "rating_protected": { "type": "boolean" },
                "protection_reason": { "type": "keyword" },
                "protected_since": { "type": "date" }
            }
        }
    }' > /dev/null
    echo "  businesses index created."
else
    echo "  businesses index already exists."
fi

# Create users index
if ! curl -s -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/users" 2>/dev/null | grep -q "200"; then
    echo "  Creating users index..."
    curl -s -X PUT "${ELASTICSEARCH_URL}/users" -H "Content-Type: application/json" -d '{
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "user_id": { "type": "keyword" },
                "name": {
                    "type": "text",
                    "fields": { "keyword": { "type": "keyword" } }
                },
                "review_count": { "type": "integer" },
                "yelping_since": { "type": "date" },
                "useful": { "type": "integer" },
                "funny": { "type": "integer" },
                "cool": { "type": "integer" },
                "fans": { "type": "integer" },
                "average_stars": { "type": "float" },
                "trust_score": { "type": "float" },
                "account_age_days": { "type": "integer" },
                "flagged": { "type": "boolean" },
                "flag_reason": { "type": "keyword" },
                "synthetic": { "type": "boolean" }
            }
        }
    }' > /dev/null
    echo "  users index created."
else
    echo "  users index already exists."
fi

# Create reviews index
if ! curl -s -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/reviews" 2>/dev/null | grep -q "200"; then
    echo "  Creating reviews index..."
    curl -s -X PUT "${ELASTICSEARCH_URL}/reviews" -H "Content-Type: application/json" -d '{
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "review_id": { "type": "keyword" },
                "user_id": { "type": "keyword" },
                "business_id": { "type": "keyword" },
                "stars": { "type": "float" },
                "date": { "type": "date" },
                "text": { "type": "text" },
                "useful": { "type": "integer" },
                "funny": { "type": "integer" },
                "cool": { "type": "integer" },
                "sentiment_score": { "type": "float" },
                "status": { "type": "keyword" },
                "held_reason": { "type": "keyword" },
                "held_at": { "type": "date" },
                "incident_id": { "type": "keyword" },
                "synthetic": { "type": "boolean" }
            }
        }
    }' > /dev/null
    echo "  reviews index created."
else
    echo "  reviews index already exists."
fi

# ----------------------------------------------
# Load sample data if indices are empty
# ----------------------------------------------
echo ""
echo "[3/5] Loading sample data..."

# Check and load businesses
BUSINESS_COUNT=$(curl -s "${ELASTICSEARCH_URL}/businesses/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
if [ "${BUSINESS_COUNT:-0}" -lt "100" ] 2>/dev/null; then
    echo "  Loading business data..."
    if [ -f "${WORKSHOP_DIR}/data/businesses.ndjson" ]; then
        curl -s -X POST "${ELASTICSEARCH_URL}/businesses/_bulk" \
            -H "Content-Type: application/x-ndjson" \
            --data-binary "@${WORKSHOP_DIR}/data/businesses.ndjson" > /dev/null
        echo "  Businesses loaded from file."
    else
        echo "  Note: Sample data file not found. Data may need to be loaded separately."
    fi
else
    echo "  Businesses already loaded (${BUSINESS_COUNT} documents)."
fi

# Check and load users
USER_COUNT=$(curl -s "${ELASTICSEARCH_URL}/users/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
if [ "${USER_COUNT:-0}" -lt "100" ] 2>/dev/null; then
    echo "  Loading user data..."
    if [ -f "${WORKSHOP_DIR}/data/users.ndjson" ]; then
        curl -s -X POST "${ELASTICSEARCH_URL}/users/_bulk" \
            -H "Content-Type: application/x-ndjson" \
            --data-binary "@${WORKSHOP_DIR}/data/users.ndjson" > /dev/null
        echo "  Users loaded from file."
    else
        echo "  Note: Sample data file not found. Data may need to be loaded separately."
    fi
else
    echo "  Users already loaded (${USER_COUNT} documents)."
fi

# Check and load reviews
REVIEW_COUNT=$(curl -s "${ELASTICSEARCH_URL}/reviews/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
if [ "${REVIEW_COUNT:-0}" -lt "100" ] 2>/dev/null; then
    echo "  Loading review data..."
    if [ -f "${WORKSHOP_DIR}/data/reviews.ndjson" ]; then
        curl -s -X POST "${ELASTICSEARCH_URL}/reviews/_bulk" \
            -H "Content-Type: application/x-ndjson" \
            --data-binary "@${WORKSHOP_DIR}/data/reviews.ndjson" > /dev/null
        echo "  Reviews loaded from file."
    else
        echo "  Note: Sample data file not found. Data may need to be loaded separately."
    fi
else
    echo "  Reviews already loaded (${REVIEW_COUNT} documents)."
fi

# ----------------------------------------------
# Refresh indices to make data searchable
# ----------------------------------------------
echo ""
echo "[4/5] Refreshing indices..."
curl -s -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null
echo "  Indices refreshed."

# ----------------------------------------------
# Wait for Kibana to be ready
# ----------------------------------------------
echo ""
echo "[5/5] Waiting for Kibana..."
MAX_RETRIES=30
RETRY_COUNT=0

until curl -s "${KIBANA_URL}/api/status" 2>/dev/null | grep -q '"level":"available"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "  Warning: Kibana may not be fully ready yet, but setup can continue."
        break
    fi
    echo "  Waiting for Kibana... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Kibana is ready!"

# ----------------------------------------------
# Final status
# ----------------------------------------------
echo ""
echo "=============================================="
echo "Challenge 1 Setup Complete!"
echo "=============================================="
echo ""
echo "Data Summary:"
FINAL_BUSINESS_COUNT=$(curl -s "${ELASTICSEARCH_URL}/businesses/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
FINAL_USER_COUNT=$(curl -s "${ELASTICSEARCH_URL}/users/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
FINAL_REVIEW_COUNT=$(curl -s "${ELASTICSEARCH_URL}/reviews/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
echo "  - Businesses: ${FINAL_BUSINESS_COUNT}"
echo "  - Users: ${FINAL_USER_COUNT}"
echo "  - Reviews: ${FINAL_REVIEW_COUNT}"
echo ""
echo "You can now begin exploring the data in Kibana!"
echo ""
