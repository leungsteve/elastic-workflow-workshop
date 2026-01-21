#!/bin/bash
#
# Solve script for Challenge 3: Creating Investigation Tools
# Sets up sample data for testing Agent Builder tools
#
# Note: Actual Agent Builder tool creation requires UI interaction.
# This script ensures the data prerequisites are met.
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "=============================================="
echo "Solving Challenge 3: Creating Investigation Tools"
echo "=============================================="

# Create sample business
echo ""
echo "Creating sample business..."
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
echo "  Done: Mario's Italian Kitchen created"

# Create sample incident
echo ""
echo "Creating sample incident..."
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -s -X POST "${ELASTICSEARCH_URL}/incidents/_doc" \
    -H "Content-Type: application/json" \
    -d '{
        "incident_id": "INC-biz_sample_001-solve",
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
        "affected_review_ids": ["rev_001", "rev_002", "rev_003", "rev_004", "rev_005", "rev_006", "rev_007", "rev_008"],
        "detected_at": "'$TIMESTAMP'",
        "created_at": "'$TIMESTAMP'"
    }' > /dev/null 2>&1
echo "  Done: Incident created"

# Create sample attackers
echo ""
echo "Creating sample attacker accounts..."
for i in 1 2 3 4 5; do
    curl -s -X PUT "${ELASTICSEARCH_URL}/users/_doc/attacker_solve_00${i}" \
        -H "Content-Type: application/json" \
        -d '{
            "user_id": "attacker_solve_00'${i}'",
            "name": "SuspiciousUser'${i}'",
            "review_count": 2,
            "trust_score": 0.1'${i}',
            "account_age_days": '${i}',
            "flagged": true,
            "synthetic": true
        }' > /dev/null 2>&1
done
echo "  Done: 5 attacker accounts created"

# Create sample attack reviews
echo ""
echo "Creating sample attack reviews..."
for i in 1 2 3 4 5 6 7 8; do
    ATTACKER_ID="attacker_solve_00$(( (i % 5) + 1 ))"
    curl -s -X PUT "${ELASTICSEARCH_URL}/reviews/_doc/rev_solve_00${i}" \
        -H "Content-Type: application/json" \
        -d '{
            "review_id": "rev_solve_00'${i}'",
            "user_id": "'${ATTACKER_ID}'",
            "business_id": "biz_sample_001",
            "stars": 1,
            "date": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
            "text": "Terrible experience. Would not recommend.",
            "status": "held",
            "held_reason": "review_bomb_detection",
            "synthetic": true
        }' > /dev/null 2>&1
done
echo "  Done: 8 attack reviews created"

# Refresh indices
curl -s -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null

echo ""
echo "=============================================="
echo "Challenge 3 Solved!"
echo "=============================================="
echo ""
echo "Sample data created:"
echo "  - Business: Mario's Italian Kitchen (biz_sample_001)"
echo "  - Incident: INC-biz_sample_001-solve"
echo "  - Attackers: 5 accounts"
echo "  - Reviews: 8 held reviews"
echo ""
echo "Note: Agent Builder tools must be created manually in the Kibana UI."
echo "The check script will pass as long as the data exists."
echo ""
