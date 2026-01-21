#!/bin/bash
#
# Check script for Challenge 3: Creating Investigation Tools
# Verifies participant has set up sample data for Agent Builder
#
# Note: Agent Builder tool creation is done through the UI and cannot
# be easily verified via API. This check verifies the data prerequisites.
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

echo "=============================================="
echo "Checking Challenge 3 Completion"
echo "=============================================="

ERRORS=0

# ----------------------------------------------
# Check 1: Verify Kibana is accessible
# ----------------------------------------------
echo ""
echo "[1/4] Verifying Kibana accessibility..."

if curl -s "${KIBANA_URL}/api/status" 2>/dev/null | grep -q '"level":"available"'; then
    echo "  OK: Kibana is accessible."
else
    echo "  FAIL: Cannot connect to Kibana."
    echo "        Agent Builder requires Kibana to be running."
    ERRORS=$((ERRORS + 1))
fi

# ----------------------------------------------
# Check 2: Verify incidents index has data
# ----------------------------------------------
echo ""
echo "[2/4] Checking for incident data..."

INCIDENT_COUNT=$(curl -s "${ELASTICSEARCH_URL}/incidents/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "${INCIDENT_COUNT:-0}" -gt "0" ] 2>/dev/null; then
    echo "  OK: Found ${INCIDENT_COUNT} incident(s) in the incidents index."
else
    echo "  WARN: No incidents found."
    echo "        Sample data may need to be created for testing."
fi

# ----------------------------------------------
# Check 3: Verify sample business exists
# ----------------------------------------------
echo ""
echo "[3/4] Checking for sample business..."

BUSINESS_CHECK=$(curl -s "${ELASTICSEARCH_URL}/businesses/_doc/biz_sample_001" 2>/dev/null | grep -c '"found":true' || echo "0")

if [ "${BUSINESS_CHECK:-0}" -gt "0" ] 2>/dev/null; then
    echo "  OK: Sample business (Mario's Italian Kitchen) exists."
else
    echo "  WARN: Sample business not found."
    echo "        The setup script should have created this."
fi

# ----------------------------------------------
# Check 4: Verify sample attack data exists
# ----------------------------------------------
echo ""
echo "[4/4] Checking for sample attack data..."

ATTACK_REVIEW_COUNT=$(curl -s "${ELASTICSEARCH_URL}/reviews/_search" \
    -H "Content-Type: application/json" \
    -d '{
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    { "term": { "business_id": "biz_sample_001" } },
                    { "term": { "status": "held" } }
                ]
            }
        }
    }' 2>/dev/null | grep -o '"total":[^}]*"value":[0-9]*' | grep -o 'value":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "${ATTACK_REVIEW_COUNT:-0}" -gt "0" ] 2>/dev/null; then
    echo "  OK: Found ${ATTACK_REVIEW_COUNT} held review(s) for sample business."
else
    echo "  WARN: No held reviews found for sample business."
fi

# ----------------------------------------------
# Final Result
# ----------------------------------------------
echo ""
echo "=============================================="

if [ $ERRORS -gt 0 ]; then
    echo "Challenge 3 Check: FAILED"
    echo "=============================================="
    echo ""
    echo "Please ensure Kibana is running and accessible."
    fail-message "Kibana verification failed. Please ensure Kibana is running."
    exit 1
fi

echo "Challenge 3 Check: PASSED"
echo "=============================================="
echo ""
echo "Infrastructure is ready for Agent Builder tools."
echo ""
echo "Please verify manually that you have:"
echo "  1. Created the 'incident_summary' tool"
echo "  2. Created the 'reviewer_analysis' tool"
echo "  3. Tested the tools with natural language queries"
echo ""
echo "Sample test queries:"
echo '  - "Summarize the incident for Mario'\''s Italian Kitchen"'
echo '  - "Analyze the attackers for business biz_sample_001"'
echo ""
echo "You're ready to move on to Challenge 4: End-to-End Scenario!"
echo ""

exit 0
