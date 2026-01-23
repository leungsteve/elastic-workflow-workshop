#!/bin/bash
#
# Check script for Challenge 4: End-to-End Attack Simulation
# Verifies that an attack was simulated and detected
#
# Instruqt check scripts should:
# - Exit 0 for success
# - Exit 1 for failure (with fail-message)
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "=============================================="
echo "Checking Challenge 4 Completion"
echo "=============================================="

ERRORS=0
WARNINGS=0

# ----------------------------------------------
# Check 1: Incident was created
# ----------------------------------------------
echo ""
echo "[1/4] Checking for incident creation..."

INCIDENT_CHECK=$(curl -s "${ELASTICSEARCH_URL}/incidents/_search" \
    -H "Content-Type: application/json" \
    -d '{
        "size": 1,
        "query": {
            "bool": {
                "must": [
                    { "term": { "incident_type": "review_fraud" } }
                ],
                "filter": [
                    { "range": { "created_at": { "gte": "now-2h" } } }
                ]
            }
        },
        "sort": [{ "created_at": "desc" }]
    }' 2>/dev/null || echo '{"hits":{"total":{"value":0}}}')

INCIDENT_COUNT=$(echo "$INCIDENT_CHECK" | grep -o '"value":[0-9]*' | head -1 | grep -o '[0-9]*' || echo "0")

if [ "${INCIDENT_COUNT:-0}" -gt "0" ] 2>/dev/null; then
    echo "  OK: Found ${INCIDENT_COUNT} incident(s) created in the last 2 hours."

    # Extract incident details for display
    INCIDENT_BIZ=$(echo "$INCIDENT_CHECK" | grep -o '"business_name":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "Unknown")
    INCIDENT_SEV=$(echo "$INCIDENT_CHECK" | grep -o '"severity":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "Unknown")
    echo "  Details: ${INCIDENT_BIZ} (${INCIDENT_SEV} severity)"
else
    echo "  FAIL: No review fraud incidents found in the last 2 hours."
    echo "        Please launch an attack and ensure your workflow detects it."
    ERRORS=$((ERRORS + 1))
fi

# ----------------------------------------------
# Check 2: Reviews were held
# ----------------------------------------------
echo ""
echo "[2/4] Checking for held reviews..."

HELD_REVIEWS=$(curl -s "${ELASTICSEARCH_URL}/reviews/_count" \
    -H "Content-Type: application/json" \
    -d '{
        "query": {
            "bool": {
                "must": [
                    { "term": { "status": "held" } }
                ],
                "filter": [
                    { "range": { "date": { "gte": "now-2h" } } }
                ]
            }
        }
    }' 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "${HELD_REVIEWS:-0}" -ge "5" ] 2>/dev/null; then
    echo "  OK: ${HELD_REVIEWS} reviews have been held."
elif [ "${HELD_REVIEWS:-0}" -gt "0" ] 2>/dev/null; then
    echo "  WARN: Only ${HELD_REVIEWS} reviews held. Expected at least 5."
    WARNINGS=$((WARNINGS + 1))
else
    echo "  FAIL: No reviews have been held."
    echo "        Your workflow should hold suspicious reviews automatically."
    ERRORS=$((ERRORS + 1))
fi

# ----------------------------------------------
# Check 3: Business was protected
# ----------------------------------------------
echo ""
echo "[3/4] Checking for business protection..."

PROTECTED_CHECK=$(curl -s "${ELASTICSEARCH_URL}/businesses/_search" \
    -H "Content-Type: application/json" \
    -d '{
        "size": 5,
        "query": {
            "term": { "rating_protected": true }
        },
        "_source": ["business_id", "name", "rating_protected", "protection_reason"]
    }' 2>/dev/null || echo '{"hits":{"total":{"value":0}}}')

PROTECTED_COUNT=$(echo "$PROTECTED_CHECK" | grep -o '"value":[0-9]*' | head -1 | grep -o '[0-9]*' || echo "0")

if [ "${PROTECTED_COUNT:-0}" -gt "0" ] 2>/dev/null; then
    echo "  OK: ${PROTECTED_COUNT} business(es) are under protection."
else
    echo "  WARN: No businesses found with rating protection enabled."
    echo "        Your workflow should protect businesses under attack."
    WARNINGS=$((WARNINGS + 1))
fi

# ----------------------------------------------
# Check 4: Target business state
# ----------------------------------------------
echo ""
echo "[4/4] Checking target business state..."

TARGET_CHECK=$(curl -s "${ELASTICSEARCH_URL}/businesses/_doc/ytynqOUb3hjKeJfRj5Tshw" 2>/dev/null || echo '{"found":false}')

if echo "$TARGET_CHECK" | grep -q '"found":true'; then
    TARGET_NAME=$(echo "$TARGET_CHECK" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || echo "Unknown")
    TARGET_PROTECTED=$(echo "$TARGET_CHECK" | grep -o '"rating_protected":[^,}]*' | cut -d':' -f2 || echo "unknown")

    echo "  Target business: ${TARGET_NAME}"
    echo "  Protected: ${TARGET_PROTECTED}"

    if [ "$TARGET_PROTECTED" == "true" ]; then
        echo "  OK: Target business is protected."
    else
        echo "  INFO: Target business is not protected (may have been resolved)."
    fi
else
    echo "  WARN: Target business (Reading Terminal Market) not found."
    WARNINGS=$((WARNINGS + 1))
fi

# ----------------------------------------------
# Final Result
# ----------------------------------------------
echo ""
echo "=============================================="

if [ $ERRORS -gt 0 ]; then
    echo "Challenge 4 Check: FAILED"
    echo "=============================================="
    echo ""
    echo "Errors: ${ERRORS}"
    echo "Warnings: ${WARNINGS}"
    echo ""
    echo "Please ensure you have:"
    echo "  1. Launched an attack via the simulator"
    echo "  2. Waited for or triggered the detection workflow"
    echo "  3. Verified that incidents were created"
    echo ""
    fail-message "End-to-end simulation verification failed. Please launch an attack and ensure your workflow detects it."
    exit 1
fi

echo "Challenge 4 Check: PASSED"
echo "=============================================="
echo ""
echo "Summary:"
echo "  - Incidents detected: ${INCIDENT_COUNT}"
echo "  - Reviews held: ${HELD_REVIEWS}"
echo "  - Businesses protected: ${PROTECTED_COUNT}"

if [ $WARNINGS -gt 0 ]; then
    echo ""
    echo "Warnings: ${WARNINGS} (some checks were not fully verified)"
fi

echo ""
echo "=============================================="
echo "CONGRATULATIONS!"
echo "=============================================="
echo ""
echo "You have completed the Review Fraud Detection Workshop!"
echo ""
echo "What you accomplished:"
echo "  - Explored data with ES|QL and LOOKUP JOIN"
echo "  - Built automated detection workflows"
echo "  - Created AI-powered investigation tools"
echo "  - Ran a complete attack simulation"
echo ""
echo "Key message: Search finds the insight."
echo "             Semantic search reveals the meaning."
echo "             Workflows acts on it."
echo "             Agent Builder explains it."
echo ""
echo "Thank you for participating!"
echo ""

exit 0
