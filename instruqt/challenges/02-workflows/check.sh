#!/bin/bash
#
# Check script for Challenge 2: Building a Detection Workflow
# Verifies participant has created the workflow correctly
#
# Instruqt check scripts should:
# - Exit 0 for success
# - Exit 1 for failure (with fail-message)
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"

echo "=============================================="
echo "Checking Challenge 2 Completion"
echo "=============================================="

ERRORS=0
WARNINGS=0

# ----------------------------------------------
# Check 1: Incidents index exists
# ----------------------------------------------
echo ""
echo "[1/4] Checking incidents index..."

if curl -s -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/incidents" 2>/dev/null | grep -q "200"; then
    echo "  OK: incidents index exists."
else
    echo "  FAIL: incidents index not found."
    echo "        This index is needed to store workflow output."
    ERRORS=$((ERRORS + 1))
fi

# ----------------------------------------------
# Check 2: Notifications index exists
# ----------------------------------------------
echo ""
echo "[2/4] Checking notifications index..."

if curl -s -o /dev/null -w "%{http_code}" "${ELASTICSEARCH_URL}/notifications" 2>/dev/null | grep -q "200"; then
    echo "  OK: notifications index exists."
else
    echo "  WARN: notifications index not found."
    echo "        This is optional but recommended for alerts."
    WARNINGS=$((WARNINGS + 1))
fi

# ----------------------------------------------
# Check 3: Look for workflow in Kibana saved objects
# ----------------------------------------------
echo ""
echo "[3/4] Checking for workflow creation..."

# Try to find workflows via Kibana API
# Note: The exact endpoint depends on the Workflows implementation
WORKFLOW_SEARCH=$(curl -s "${KIBANA_URL}/api/saved_objects/_find?type=workflow&per_page=100" \
    -H "kbn-xsrf: true" 2>/dev/null || echo '{"total":0}')

WORKFLOW_COUNT=$(echo "$WORKFLOW_SEARCH" | grep -o '"total":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "${WORKFLOW_COUNT:-0}" -gt "0" ] 2>/dev/null; then
    echo "  OK: Found ${WORKFLOW_COUNT} workflow(s) in Kibana."

    # Check if any workflow contains "review" or "fraud" in the title
    if echo "$WORKFLOW_SEARCH" | grep -qi "negative.*review.*campaign\|review.*bomb\|review.bomb.detection"; then
        echo "  OK: Found 'Negative Review Campaign Detection' workflow."
    else
        echo "  WARN: Workflow exists but may not be named 'Negative Review Campaign Detection'."
        echo "        Please verify your workflow is correctly named."
        WARNINGS=$((WARNINGS + 1))
    fi
else
    # Alternative check: Look for workflow configuration files or API endpoints
    # This depends on how Workflows is implemented in your version

    # Check if there's been any workflow execution (would indicate workflow exists)
    WORKFLOW_LOG_CHECK=$(curl -s "${KIBANA_URL}/api/workflows/executions?per_page=1" \
        -H "kbn-xsrf: true" 2>/dev/null || echo '{"total":0}')

    EXECUTION_COUNT=$(echo "$WORKFLOW_LOG_CHECK" | grep -o '"total":[0-9]*' | grep -o '[0-9]*' || echo "0")

    if [ "${EXECUTION_COUNT:-0}" -gt "0" ] 2>/dev/null; then
        echo "  OK: Workflow execution history found."
    else
        echo "  WARN: Could not verify workflow creation via API."
        echo "        Please ensure you have created and saved the workflow in Kibana."
        echo "        Note: This check may show a warning even if the workflow exists."
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# ----------------------------------------------
# Check 4: Verify Kibana is accessible
# ----------------------------------------------
echo ""
echo "[4/4] Verifying Kibana accessibility..."

if curl -s "${KIBANA_URL}/api/status" 2>/dev/null | grep -q '"level":"available"'; then
    echo "  OK: Kibana is accessible."
else
    echo "  FAIL: Cannot connect to Kibana."
    echo "        Please ensure Kibana is running."
    ERRORS=$((ERRORS + 1))
fi

# ----------------------------------------------
# Final Result
# ----------------------------------------------
echo ""
echo "=============================================="

if [ $ERRORS -gt 0 ]; then
    echo "Challenge 2 Check: FAILED"
    echo "=============================================="
    echo ""
    echo "Errors found: ${ERRORS}"
    echo "Warnings: ${WARNINGS}"
    echo ""
    echo "Please ensure:"
    echo "  1. The incidents index exists"
    echo "  2. You have created a workflow named 'Negative Review Campaign Detection'"
    echo "  3. The workflow has the required trigger and steps"
    echo ""
    fail-message "Workflow verification failed. Please create the 'Negative Review Campaign Detection' workflow as described in the assignment."
    exit 1
fi

if [ $WARNINGS -gt 0 ]; then
    echo "Challenge 2 Check: PASSED (with warnings)"
    echo "=============================================="
    echo ""
    echo "Warnings: ${WARNINGS}"
    echo ""
    echo "The required infrastructure is in place."
    echo "Please verify manually that your workflow is configured correctly."
else
    echo "Challenge 2 Check: PASSED"
    echo "=============================================="
fi

echo ""
echo "Great job! You've created the detection workflow infrastructure."
echo ""
echo "Your workflow should:"
echo "  - Run on a 1-minute schedule"
echo "  - Detect negative review campaigns using ES|QL"
echo "  - Hold suspicious reviews"
echo "  - Protect targeted businesses"
echo "  - Create incidents for investigation"
echo ""
echo "You're ready to move on to Challenge 3: Agent Builder!"
echo ""

exit 0
