#!/bin/bash
#
# Setup script for Challenge 4: End-to-End Attack Simulation
# Prepares the target business and attacker pool for the simulation
#
# This script is idempotent - safe to run multiple times
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
APP_URL="${APP_URL:-http://localhost:8080}"

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
# Create/Reset target business
# ----------------------------------------------
echo ""
echo "[2/5] Setting up target business..."

# Create fresh target business (reset any previous state)
curl -s -X PUT "${ELASTICSEARCH_URL}/businesses/_doc/target_biz_001" \
    -H "Content-Type: application/json" \
    -d '{
        "business_id": "target_biz_001",
        "name": "The Golden Spoon",
        "address": "456 Oak Avenue",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78701",
        "latitude": 30.2672,
        "longitude": -97.7431,
        "stars": 4.7,
        "review_count": 523,
        "is_open": true,
        "categories": ["Restaurant", "American", "Brunch"],
        "rating_protected": false,
        "protection_reason": null,
        "protected_since": null
    }' > /dev/null 2>&1
echo "  Target business created: The Golden Spoon (4.7 stars)"

# ----------------------------------------------
# Clear any existing incidents for this business
# ----------------------------------------------
echo ""
echo "[3/5] Clearing previous incidents..."

curl -s -X POST "${ELASTICSEARCH_URL}/incidents/_delete_by_query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": {
            "term": { "business_id": "target_biz_001" }
        }
    }' > /dev/null 2>&1 || true
echo "  Previous incidents cleared."

# Clear any held reviews from previous simulations
curl -s -X POST "${ELASTICSEARCH_URL}/reviews/_delete_by_query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": {
            "bool": {
                "must": [
                    { "term": { "business_id": "target_biz_001" } },
                    { "term": { "synthetic": true } }
                ]
            }
        }
    }' > /dev/null 2>&1 || true
echo "  Previous synthetic reviews cleared."

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
# Start attack simulator (if available)
# ----------------------------------------------
echo ""
echo "[5/5] Checking attack simulator..."

# Check if simulator is available
if curl -s "${APP_URL}/health" 2>/dev/null | grep -q "ok"; then
    echo "  Attack simulator is already running at ${APP_URL}"
else
    # Try to start it
    if [ -f "/workshop/app/start.sh" ]; then
        echo "  Starting attack simulator..."
        /workshop/app/start.sh &
        sleep 5
    elif command -v docker-compose &> /dev/null && [ -f "/workshop/docker-compose.yml" ]; then
        echo "  Starting attack simulator via Docker..."
        cd /workshop && docker-compose up -d simulator 2>/dev/null || true
        sleep 5
    fi

    # Verify it started
    if curl -s "${APP_URL}/health" 2>/dev/null | grep -q "ok"; then
        echo "  Attack simulator started successfully."
    else
        echo "  Note: Attack simulator may need to be started manually."
        echo "        Or use the Terminal to simulate attacks directly."
    fi
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
echo "Simulation Environment Ready:"
echo ""
echo "  Target Business:"
echo "    - Name: The Golden Spoon"
echo "    - ID: target_biz_001"
echo "    - Rating: 4.7 stars"
echo "    - Status: Normal (not protected)"
echo ""
echo "  Attacker Pool:"
echo "    - 20 low-trust accounts ready"
echo "    - Trust scores: 0.05 - 0.35"
echo "    - Account ages: 1-21 days"
echo ""
echo "  Attack Simulator: ${APP_URL}"
echo ""
echo "You are ready to begin the end-to-end attack simulation!"
echo ""
