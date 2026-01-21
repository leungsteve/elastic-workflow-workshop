#!/bin/bash
#
# Check script for Challenge 1: Getting to Know Your Data
# Verifies participant has explored the data and understands the indices
#
# Instruqt check scripts should:
# - Exit 0 for success
# - Exit 1 for failure (with fail-message)
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "=============================================="
echo "Checking Challenge 1 Completion"
echo "=============================================="

ERRORS=0

# ----------------------------------------------
# Check 1: Businesses index has data
# ----------------------------------------------
echo ""
echo "[1/4] Checking businesses index..."
BUSINESS_COUNT=$(curl -s "${ELASTICSEARCH_URL}/businesses/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "${BUSINESS_COUNT:-0}" -eq "0" ] 2>/dev/null; then
    echo "  FAIL: The businesses index is empty."
    echo "        Please run the setup script or verify data was loaded."
    ERRORS=$((ERRORS + 1))
else
    echo "  OK: businesses index has ${BUSINESS_COUNT} documents."
fi

# ----------------------------------------------
# Check 2: Users index has data
# ----------------------------------------------
echo ""
echo "[2/4] Checking users index..."
USER_COUNT=$(curl -s "${ELASTICSEARCH_URL}/users/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "${USER_COUNT:-0}" -eq "0" ] 2>/dev/null; then
    echo "  FAIL: The users index is empty."
    echo "        Please run the setup script or verify data was loaded."
    ERRORS=$((ERRORS + 1))
else
    echo "  OK: users index has ${USER_COUNT} documents."
fi

# ----------------------------------------------
# Check 3: Reviews index has data
# ----------------------------------------------
echo ""
echo "[3/4] Checking reviews index..."
REVIEW_COUNT=$(curl -s "${ELASTICSEARCH_URL}/reviews/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "${REVIEW_COUNT:-0}" -eq "0" ] 2>/dev/null; then
    echo "  FAIL: The reviews index is empty."
    echo "        Please run the setup script or verify data was loaded."
    ERRORS=$((ERRORS + 1))
else
    echo "  OK: reviews index has ${REVIEW_COUNT} documents."
fi

# ----------------------------------------------
# Check 4: Users have trust_score field populated
# ----------------------------------------------
echo ""
echo "[4/4] Checking trust_score data..."
TRUST_SCORE_CHECK=$(curl -s "${ELASTICSEARCH_URL}/users/_search" \
    -H "Content-Type: application/json" \
    -d '{
        "size": 0,
        "aggs": {
            "has_trust_score": {
                "filter": {
                    "exists": { "field": "trust_score" }
                }
            }
        }
    }' 2>/dev/null | grep -o '"doc_count":[0-9]*' | head -1 | grep -o '[0-9]*' || echo "0")

if [ "${TRUST_SCORE_CHECK:-0}" -lt "10" ] 2>/dev/null; then
    echo "  FAIL: Users don't have trust_score data."
    echo "        This field is essential for detecting suspicious activity."
    ERRORS=$((ERRORS + 1))
else
    echo "  OK: Users have trust_score data (${TRUST_SCORE_CHECK} users with scores)."
fi

# ----------------------------------------------
# Final Result
# ----------------------------------------------
echo ""
echo "=============================================="

if [ $ERRORS -gt 0 ]; then
    echo "Challenge 1 Check: FAILED"
    echo "=============================================="
    echo ""
    echo "Please ensure:"
    echo "  1. All three indices (businesses, users, reviews) have data"
    echo "  2. Users have trust_score values populated"
    echo "  3. You have explored the data using the ES|QL queries in the assignment"
    echo ""
    fail-message "Data verification failed. Please ensure the data is properly loaded and try the ES|QL queries from the assignment."
    exit 1
fi

echo "Challenge 1 Check: PASSED"
echo "=============================================="
echo ""
echo "Great job! You've successfully explored the data model."
echo ""
echo "Summary:"
echo "  - Businesses: ${BUSINESS_COUNT}"
echo "  - Users: ${USER_COUNT}"
echo "  - Reviews: ${REVIEW_COUNT}"
echo ""
echo "You're ready to move on to Challenge 2: Building a Detection Workflow!"
echo ""

exit 0
