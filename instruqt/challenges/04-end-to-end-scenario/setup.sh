#!/bin/bash
#
# Setup script for Challenge 4: End-to-End Attack Simulation
# Prepares the environment for attacking a real Yelp business
#
# Target: Reading Terminal Market (ytynqOUb3hjKeJfRj5Tshw)
# A famous Philadelphia landmark with 4.6 stars and 1,860+ reviews
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
APP_URL="${APP_URL:-http://localhost:8080}"

TARGET_BIZ_ID="ytynqOUb3hjKeJfRj5Tshw"
TARGET_BIZ_NAME="Reading Terminal Market"

echo "=============================================="
echo "Setting up Challenge 4: End-to-End Attack Simulation"
echo "=============================================="

# ----------------------------------------------
# Wait for Elasticsearch to be ready
# ----------------------------------------------
echo ""
echo "[1/5] Waiting for Elasticsearch..."
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
# Verify target business exists
# ----------------------------------------------
echo ""
echo "[2/5] Verifying target business..."

BIZ_CHECK=$(curl -s "${ELASTICSEARCH_URL}/businesses/_doc/${TARGET_BIZ_ID}" 2>/dev/null || echo '{"found":false}')

if echo "$BIZ_CHECK" | grep -q '"found":true'; then
    BIZ_STARS=$(echo "$BIZ_CHECK" | grep -o '"stars":[0-9.]*' | cut -d':' -f2 || echo "?")
    BIZ_REVIEWS=$(echo "$BIZ_CHECK" | grep -o '"review_count":[0-9]*' | cut -d':' -f2 || echo "?")
    echo "  Found: ${TARGET_BIZ_NAME}"
    echo "  Rating: ${BIZ_STARS} stars, ${BIZ_REVIEWS} reviews"
else
    echo "  WARNING: Target business not found in index."
    echo "  Make sure the Yelp data has been loaded."
fi

# Reset any previous protection state
curl -s -X POST "${ELASTICSEARCH_URL}/businesses/_update/${TARGET_BIZ_ID}" \
    -H "Content-Type: application/json" \
    -d '{
        "doc": {
            "rating_protected": false,
            "protection_reason": null,
            "protected_since": null
        }
    }' > /dev/null 2>&1 || true
echo "  Reset protection state to normal."

# ----------------------------------------------
# Clear any existing incidents for this business
# ----------------------------------------------
echo ""
echo "[3/5] Clearing previous simulation data..."

curl -s -X POST "${ELASTICSEARCH_URL}/incidents/_delete_by_query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": {
            "term": { "business_id": "'"${TARGET_BIZ_ID}"'" }
        }
    }' > /dev/null 2>&1 || true
echo "  Previous incidents cleared."

# Clear any synthetic/attack reviews from previous simulations
curl -s -X POST "${ELASTICSEARCH_URL}/reviews/_delete_by_query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": {
            "bool": {
                "must": [
                    { "term": { "business_id": "'"${TARGET_BIZ_ID}"'" } },
                    { "term": { "is_simulated": true } }
                ]
            }
        }
    }' > /dev/null 2>&1 || true
echo "  Previous attack reviews cleared."

# ----------------------------------------------
# Create attacker account pool
# ----------------------------------------------
echo ""
echo "[4/5] Creating attacker account pool..."

ATTACKER_NAMES=(
    "NewReviewer2024"
    "JustJoined123"
    "FreshAccount99"
    "Review_User_X"
    "Anonymous_Food"
    "CriticX_2024"
    "TruthTeller101"
    "HonestReview77"
    "RealOpinion42"
    "FoodCritic_New"
    "JustMyThoughts"
    "UnbiasedView99"
    "FirstReview_Me"
    "NewToYelp2024"
    "TryingItOut123"
    "NoFakeHere007"
    "ActuallyTried"
    "RealExperience"
    "NotABot_Trust"
    "GenuineReview1"
)

for i in {1..20}; do
    # Generate low trust score (0.05 - 0.35)
    TRUST_SCORE=$(awk "BEGIN {printf \"%.2f\", 0.05 + (0.30 * $RANDOM / 32767)}")
    # Generate new account age (1-21 days)
    ACCOUNT_AGE=$((RANDOM % 21 + 1))
    # Low review count (0-4)
    REVIEW_COUNT=$((RANDOM % 5))

    PADDED_I=$(printf '%03d' $i)
    NAME_INDEX=$((i - 1))

    curl -s -X PUT "${ELASTICSEARCH_URL}/users/_doc/sim_attacker_${PADDED_I}" \
        -H "Content-Type: application/json" \
        -d '{
            "user_id": "sim_attacker_'${PADDED_I}'",
            "name": "'${ATTACKER_NAMES[$NAME_INDEX]}'",
            "review_count": '${REVIEW_COUNT}',
            "yelping_since": "2024-01-01T00:00:00Z",
            "useful": 0,
            "funny": 0,
            "cool": 0,
            "fans": 0,
            "average_stars": 1.5,
            "trust_score": '${TRUST_SCORE}',
            "account_age_days": '${ACCOUNT_AGE}',
            "flagged": false,
            "synthetic": true
        }' > /dev/null 2>&1
done
echo "  Created 20 simulated attacker accounts (low trust, new accounts)"

# ----------------------------------------------
# Check attack simulator
# ----------------------------------------------
echo ""
echo "[5/5] Checking attack simulator..."

if curl -s "${APP_URL}/health" 2>/dev/null | grep -q "healthy"; then
    echo "  Attack simulator is running at ${APP_URL}"
else
    echo "  Note: Attack simulator may need to be started."
    echo "        Run: python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080"
fi

# Refresh indices
curl -s -X POST "${ELASTICSEARCH_URL}/_refresh" > /dev/null

# ----------------------------------------------
# Final status
# ----------------------------------------------
echo ""
echo "=============================================="
echo "Challenge 4 Setup Complete!"
echo "=============================================="
echo ""
echo "Target Business (Real Yelp Data):"
echo ""
echo "  Name: ${TARGET_BIZ_NAME}"
echo "  ID: ${TARGET_BIZ_ID}"
echo "  Location: Philadelphia"
echo "  Status: Normal (not protected)"
echo ""
echo "Attacker Pool:"
echo "  - 20 low-trust accounts ready"
echo "  - Trust scores: 0.05 - 0.35"
echo "  - Account ages: 1-21 days"
echo ""
echo "Attack Simulator: ${APP_URL}"
echo ""
echo "You are ready to begin the end-to-end attack simulation!"
echo ""
