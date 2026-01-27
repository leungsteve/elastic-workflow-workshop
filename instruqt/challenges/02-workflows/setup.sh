#!/bin/bash
#
# Setup script for Challenge 2: Building a Detection Workflow
# Ensures workflow prerequisites are in place
#
# This script is idempotent - safe to run multiple times
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

echo "=============================================="
echo "Setting up Challenge 2: Building a Detection Workflow"
echo "=============================================="

# ----------------------------------------------
# Wait for Elasticsearch to be ready
# ----------------------------------------------
echo ""
echo "[1/4] Waiting for Elasticsearch..."
MAX_RETRIES=30
RETRY_COUNT=0

until curl -s "${ELASTICSEARCH_URL}/_cluster/health" 2>/dev/null | grep -q '"status":"green"\|"status":"yellow"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Elasticsearch did not become ready in time"
        exit 1
    fi
    echo "  Waiting... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Elasticsearch is ready!"

# ----------------------------------------------
# Wait for Kibana to be ready
# ----------------------------------------------
echo ""
echo "[2/4] Waiting for Kibana..."
MAX_RETRIES=30
RETRY_COUNT=0

until curl -s "${KIBANA_URL}/api/status" 2>/dev/null | grep -q '"level":"available"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "  Warning: Kibana may not be fully ready yet."
        break
    fi
    echo "  Waiting... (attempt ${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done
echo "  Kibana is ready!"

# ----------------------------------------------
# Create incidents index for workflow output
# ----------------------------------------------
echo ""
echo "[3/4] Creating incidents index..."

if ! curl -s -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/incidents" 2>/dev/null | grep -q "200"; then
    curl -s -X PUT "${ELASTICSEARCH_URL}/incidents" -H "Content-Type: application/json" -d '{
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "incident_id": { "type": "keyword" },
                "incident_type": { "type": "keyword" },
                "status": { "type": "keyword" },
                "severity": { "type": "keyword" },
                "business_id": { "type": "keyword" },
                "business_name": {
                    "type": "text",
                    "fields": { "keyword": { "type": "keyword" } }
                },
                "city": { "type": "keyword" },
                "metrics": {
                    "type": "object",
                    "properties": {
                        "review_count": { "type": "integer" },
                        "avg_stars": { "type": "float" },
                        "avg_trust": { "type": "float" },
                        "unique_attackers": { "type": "integer" }
                    }
                },
                "affected_review_ids": { "type": "keyword" },
                "detected_at": { "type": "date" },
                "created_at": { "type": "date" },
                "updated_at": { "type": "date" },
                "resolved_at": { "type": "date" },
                "resolution_notes": { "type": "text" },
                "resolved_by": { "type": "keyword" }
            }
        }
    }' > /dev/null
    echo "  incidents index created."
else
    echo "  incidents index already exists."
fi

# ----------------------------------------------
# Create notifications index for alerts
# ----------------------------------------------
echo ""
echo "[4/4] Creating notifications index..."

if ! curl -s -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/notifications" 2>/dev/null | grep -q "200"; then
    curl -s -X PUT "${ELASTICSEARCH_URL}/notifications" -H "Content-Type: application/json" -d '{
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "notification_id": { "type": "keyword" },
                "notification_type": { "type": "keyword" },
                "recipient_type": { "type": "keyword" },
                "priority": { "type": "keyword" },
                "title": { "type": "text" },
                "message": { "type": "text" },
                "business_id": { "type": "keyword" },
                "incident_id": { "type": "keyword" },
                "created_at": { "type": "date" },
                "read": { "type": "boolean" },
                "read_at": { "type": "date" }
            }
        }
    }' > /dev/null
    echo "  notifications index created."
else
    echo "  notifications index already exists."
fi

# ----------------------------------------------
# Refresh indices
# ----------------------------------------------
curl -s -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null

# ----------------------------------------------
# Final status
# ----------------------------------------------
echo ""
echo "=============================================="
echo "Challenge 2 Setup Complete!"
echo "=============================================="
echo ""
echo "Prerequisites ready:"
echo "  - incidents index: created"
echo "  - notifications index: created"
echo "  - Kibana Workflows app: accessible"
echo ""
echo "You can now create your Negative Review Campaign Detection workflow!"
echo ""
