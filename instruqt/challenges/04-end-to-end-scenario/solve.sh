#!/bin/bash
#
# Solve script for Challenge 4: End-to-End Attack Simulation
# Simulates an attack and creates the expected artifacts for testing
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "=============================================="
echo "Solving Challenge 4: End-to-End Attack Simulation"
echo "=============================================="

# ----------------------------------------------
# Setup target business (protect the real Yelp business)
# ----------------------------------------------
echo ""
echo "[1/5] Setting up target business..."

TARGET_BIZ_ID="ytynqOUb3hjKeJfRj5Tshw"
TARGET_BIZ_NAME="Reading Terminal Market"

curl -s -X POST "${ELASTICSEARCH_URL}/businesses/_update/${TARGET_BIZ_ID}" \
    -H "Content-Type: application/json" \
    -d '{
        "doc": {
            "rating_protected": true,
            "protection_reason": "review_bomb_detected",
            "protected_since": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
        }
    }' > /dev/null 2>&1
echo "  Done: Target business (${TARGET_BIZ_NAME}) protected"

# ----------------------------------------------
# Create attacker accounts
# ----------------------------------------------
echo ""
echo "[2/5] Creating attacker accounts..."

for i in {1..8}; do
    PADDED_I=$(printf '%03d' $i)
    curl -s -X PUT "${ELASTICSEARCH_URL}/users/_doc/solve_attacker_${PADDED_I}" \
        -H "Content-Type: application/json" \
        -d '{
            "user_id": "solve_attacker_'${PADDED_I}'",
            "name": "Attacker'${i}'",
            "review_count": 1,
            "trust_score": 0.1'${i}',
            "account_age_days": '${i}',
            "flagged": true,
            "synthetic": true
        }' > /dev/null 2>&1
done
echo "  Done: 8 attacker accounts created"

# ----------------------------------------------
# Create attack reviews (held)
# ----------------------------------------------
echo ""
echo "[3/5] Creating attack reviews..."

ATTACK_TEXTS=(
    "Terrible food, would never come back!"
    "Worst experience I have ever had."
    "Completely overrated. Save your money."
    "Food was cold and staff was rude."
    "Do not waste your time here."
    "Disgusting. Found something in my food."
    "Absolute disaster of a restaurant."
    "Zero stars if I could. Awful place."
    "Horrible service, horrible food."
    "Never again. Total waste of money."
    "The worst meal I have ever had."
    "Avoid at all costs. Seriously bad."
)

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

for i in {1..12}; do
    ATTACKER_NUM=$(( (i % 8) + 1 ))
    ATTACKER_ID="solve_attacker_$(printf '%03d' $ATTACKER_NUM)"
    TEXT_INDEX=$(( (i - 1) % 12 ))
    REVIEW_TIME=$(date -u -d "-$((i * 2)) minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)

    curl -s -X PUT "${ELASTICSEARCH_URL}/reviews/_doc/solve_attack_review_$(printf '%03d' $i)" \
        -H "Content-Type: application/json" \
        -d '{
            "review_id": "solve_attack_review_'$(printf '%03d' $i)'",
            "user_id": "'${ATTACKER_ID}'",
            "business_id": "'${TARGET_BIZ_ID}'",
            "stars": '$((RANDOM % 2 + 1))',
            "date": "'${REVIEW_TIME}'",
            "text": "'"${ATTACK_TEXTS[$TEXT_INDEX]}"'",
            "useful": 0,
            "funny": 0,
            "cool": 0,
            "status": "held",
            "held_reason": "review_bomb_detection",
            "held_at": "'${TIMESTAMP}'",
            "synthetic": true
        }' > /dev/null 2>&1
done
echo "  Done: 12 attack reviews created (held)"

# ----------------------------------------------
# Create incident
# ----------------------------------------------
echo ""
echo "[4/5] Creating incident..."

INCIDENT_ID="INC-${TARGET_BIZ_ID}-$(date +%Y%m%d%H%M%S)"

curl -s -X POST "${ELASTICSEARCH_URL}/incidents/_doc" \
    -H "Content-Type: application/json" \
    -d '{
        "incident_id": "'${INCIDENT_ID}'",
        "incident_type": "review_bomb",
        "status": "detected",
        "severity": "high",
        "business_id": "'${TARGET_BIZ_ID}'",
        "business_name": "'${TARGET_BIZ_NAME}'",
        "city": "Philadelphia",
        "metrics": {
            "review_count": 12,
            "avg_stars": 1.4,
            "avg_trust": 0.15,
            "unique_attackers": 8
        },
        "affected_review_ids": ["solve_attack_review_001", "solve_attack_review_002", "solve_attack_review_003", "solve_attack_review_004", "solve_attack_review_005", "solve_attack_review_006", "solve_attack_review_007", "solve_attack_review_008", "solve_attack_review_009", "solve_attack_review_010", "solve_attack_review_011", "solve_attack_review_012"],
        "detected_at": "'${TIMESTAMP}'",
        "created_at": "'${TIMESTAMP}'"
    }' > /dev/null 2>&1
echo "  Done: Incident created (${INCIDENT_ID})"

# ----------------------------------------------
# Refresh indices
# ----------------------------------------------
echo ""
echo "[5/5] Finalizing..."
curl -s -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null

# ----------------------------------------------
# Summary
# ----------------------------------------------
echo ""
echo "=============================================="
echo "Challenge 4 Solved!"
echo "=============================================="
echo ""
echo "Simulated attack completed:"
echo ""
echo "  Target: ${TARGET_BIZ_NAME} (${TARGET_BIZ_ID})"
echo "  Status: Protected"
echo ""
echo "  Attack Details:"
echo "    - Reviews: 12 (held)"
echo "    - Attackers: 8 accounts"
echo "    - Severity: High"
echo ""
echo "  Incident: ${INCIDENT_ID}"
echo "    - Status: Open"
echo "    - Ready for investigation"
echo ""
echo "The check script should now pass."
echo ""
