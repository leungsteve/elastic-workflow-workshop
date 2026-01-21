#!/bin/bash
#
# Setup script for Challenge 3: Creating Investigation Tools
# Ensures sample data exists for testing Agent Builder tools
#
# This script is idempotent - safe to run multiple times
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

echo "=============================================="
echo "Setting up Challenge 3: Creating Investigation Tools"
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
# Create sample incident for testing
# ----------------------------------------------
echo ""
echo "[3/4] Creating sample incident data..."

# Create sample business if it doesn't exist
curl -s -X PUT "${ELASTICSEARCH_URL}/businesses/_doc/biz_sample_001" \
    -H "Content-Type: application/json" \
    -d '{
        "business_id": "biz_sample_001",
        "name": "Mario'\''s Italian Kitchen",
        "address": "123 Main Street",
        "city": "San Francisco",
        "state": "CA",
        "postal_code": "94102",
        "stars": 4.5,
        "review_count": 234,
        "is_open": true,
        "categories": ["Italian", "Restaurant", "Pizza"],
        "rating_protected": true,
        "protection_reason": "review_bomb_detected"
    }' > /dev/null 2>&1
echo "  Sample business created: Mario's Italian Kitchen"

# Create sample incident
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -s -X POST "${ELASTICSEARCH_URL}/incidents/_doc" \
    -H "Content-Type: application/json" \
    -d '{
        "incident_id": "INC-biz_sample_001-'$(date +%Y%m%d%H%M%S)'",
        "incident_type": "review_bomb",
        "status": "open",
        "severity": "high",
        "business_id": "biz_sample_001",
        "business_name": "Mario'\''s Italian Kitchen",
        "city": "San Francisco",
        "metrics": {
            "review_count": 8,
            "avg_stars": 1.3,
            "avg_trust": 0.18,
            "unique_attackers": 5
        },
        "affected_review_ids": ["rev_attack_001", "rev_attack_002", "rev_attack_003", "rev_attack_004", "rev_attack_005", "rev_attack_006", "rev_attack_007", "rev_attack_008"],
        "detected_at": "'$TIMESTAMP'",
        "created_at": "'$TIMESTAMP'"
    }' > /dev/null 2>&1
echo "  Sample incident created: high severity attack"

# ----------------------------------------------
# Create sample attacker accounts and reviews
# ----------------------------------------------
echo ""
echo "[4/4] Creating sample attacker data..."

# Create attacker accounts
for i in 1 2 3 4 5; do
    TRUST_SCORE=$(echo "scale=2; 0.0$((RANDOM % 30 + 5))" | bc 2>/dev/null || echo "0.15")
    ACCOUNT_AGE=$((RANDOM % 14 + 1))

    curl -s -X PUT "${ELASTICSEARCH_URL}/users/_doc/attacker_sample_00${i}" \
        -H "Content-Type: application/json" \
        -d '{
            "user_id": "attacker_sample_00'${i}'",
            "name": "User'$((RANDOM % 9999))'",
            "review_count": '$((RANDOM % 5 + 1))',
            "yelping_since": "2024-01-01T00:00:00Z",
            "useful": 0,
            "funny": 0,
            "cool": 0,
            "fans": 0,
            "average_stars": 1.5,
            "trust_score": 0.'$((RANDOM % 25 + 5))',
            "account_age_days": '$ACCOUNT_AGE',
            "flagged": true,
            "flag_reason": "review_bomb_participant",
            "synthetic": true
        }' > /dev/null 2>&1
done
echo "  Created 5 sample attacker accounts"

# Create attack reviews
REVIEW_TEXTS=(
    "Terrible food, would never go back."
    "Worst experience ever. Avoid this place."
    "Food was cold and service was awful."
    "Complete waste of money. 0 stars if I could."
    "Do not eat here. You will regret it."
    "Disgusting. Found a hair in my food."
    "Rude staff and horrible atmosphere."
    "Overpriced garbage. Save your money."
)

for i in 1 2 3 4 5 6 7 8; do
    ATTACKER_ID="attacker_sample_00$(( (i % 5) + 1 ))"
    TEXT_INDEX=$(( (i - 1) % 8 ))
    REVIEW_TIMESTAMP=$(date -u -d "-$((i * 2)) minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)

    curl -s -X PUT "${ELASTICSEARCH_URL}/reviews/_doc/rev_attack_00${i}" \
        -H "Content-Type: application/json" \
        -d '{
            "review_id": "rev_attack_00'${i}'",
            "user_id": "'${ATTACKER_ID}'",
            "business_id": "biz_sample_001",
            "stars": '$((RANDOM % 2 + 1))',
            "date": "'$REVIEW_TIMESTAMP'",
            "text": "'"${REVIEW_TEXTS[$TEXT_INDEX]}"'",
            "useful": 0,
            "funny": 0,
            "cool": 0,
            "status": "held",
            "held_reason": "review_bomb_detection",
            "incident_id": "INC-biz_sample_001",
            "synthetic": true
        }' > /dev/null 2>&1
done
echo "  Created 8 sample attack reviews"

# Refresh indices
curl -s -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null

# ----------------------------------------------
# Final status
# ----------------------------------------------
echo ""
echo "=============================================="
echo "Challenge 3 Setup Complete!"
echo "=============================================="
echo ""
echo "Sample data created for testing:"
echo "  - Business: Mario's Italian Kitchen (biz_sample_001)"
echo "  - Incident: High severity review bomb attack"
echo "  - Attackers: 5 low-trust accounts"
echo "  - Reviews: 8 suspicious 1-2 star reviews"
echo ""
echo "You can now create Agent Builder tools to investigate this incident!"
echo ""
echo "Test queries to try after creating your tools:"
echo '  - "Summarize the incident for Mario'\''s Italian Kitchen"'
echo '  - "Analyze the attackers for business biz_sample_001"'
echo ""
