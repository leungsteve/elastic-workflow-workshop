#!/bin/bash
#
# Test script to verify Elasticsearch and Kibana API connectivity
# Run after switching clusters or updating credentials
#
# Usage: ./admin/test_kibana_api.sh
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Find and source .env file
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/../.env" ]; then
    set -a
    source "$SCRIPT_DIR/../.env"
    set +a
elif [ -f ".env" ]; then
    set -a
    source ".env"
    set +a
else
    echo -e "${RED}ERROR: .env file not found${NC}"
    exit 1
fi

# Derive Kibana URL if not set
if [ -z "$KIBANA_URL" ]; then
    KIBANA_URL=$(echo "$ELASTICSEARCH_URL" | sed 's/\.es\./\.kb\./')
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Elastic API Connectivity Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Elasticsearch: $ELASTICSEARCH_URL"
echo "Kibana:        $KIBANA_URL"
echo ""

PASS=0
FAIL=0
WORKFLOWS_AVAILABLE=false

# Helper function
test_endpoint() {
    local name="$1"
    local url="$2"
    local check="$3"

    response=$(curl -s -m 30 -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" -H "kbn-xsrf: true" "$url" 2>/dev/null)

    if echo "$response" | grep -q "$check"; then
        echo -e "${GREEN}✓ PASS${NC} - $name"
        ((PASS++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} - $name"
        echo "  Response: $(echo "$response" | head -c 150)"
        ((FAIL++))
        return 1
    fi
}

echo -e "${BLUE}--- Elasticsearch Tests ---${NC}"

# ES Connection
response=$(curl -s -m 30 -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" "$ELASTICSEARCH_URL" 2>/dev/null)
if echo "$response" | grep -q '"cluster_name"'; then
    # Use jq if available, otherwise use grep
    if command -v jq &>/dev/null; then
        version=$(echo "$response" | jq -r '.version.number // empty')
        build=$(echo "$response" | jq -r '.version.build_flavor // empty')
    else
        version=$(echo "$response" | grep -o '"number":"[^"]*"' | head -1 | cut -d'"' -f4)
        build=$(echo "$response" | grep -o '"build_flavor":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi
    if [ -n "$version" ]; then
        echo -e "${GREEN}✓ PASS${NC} - ES Connection (v$version, $build)"
        [ "$build" == "serverless" ] && echo -e "${YELLOW}  ⚠ Serverless - some APIs may be restricted${NC}"
    else
        echo -e "${GREEN}✓ PASS${NC} - ES Connection"
    fi
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC} - ES Connection"
    ((FAIL++))
fi

# ES Indices
response=$(curl -s -m 30 -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" "$ELASTICSEARCH_URL/_aliases" 2>/dev/null)
if echo "$response" | grep -q 'aliases'; then
    count=$(echo "$response" | grep -o '"aliases"' | wc -l)
    echo -e "${GREEN}✓ PASS${NC} - ES Indices ($count found)"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC} - ES Indices"
    ((FAIL++))
fi

echo ""
echo -e "${BLUE}--- Kibana Tests ---${NC}"

# Kibana Status
response=$(curl -s -m 30 -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" -H "kbn-xsrf: true" "$KIBANA_URL/api/status" 2>/dev/null)
if echo "$response" | grep -q '"version"'; then
    version=$(echo "$response" | grep -o '"number":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo -e "${GREEN}✓ PASS${NC} - Kibana Status (v$version)"
    ((PASS++))
else
    echo -e "${RED}✗ FAIL${NC} - Kibana Status"
    ((FAIL++))
fi

test_endpoint "Kibana Features" "$KIBANA_URL/api/features" '"id"'

echo ""
echo -e "${BLUE}--- Agent Builder API ---${NC}"

test_endpoint "List Tools" "$KIBANA_URL/api/agent_builder/tools" '"results"'
test_endpoint "List Agents" "$KIBANA_URL/api/agent_builder/agents" '"results"'
test_endpoint "List Conversations" "$KIBANA_URL/api/agent_builder/conversations" '"results"'

echo ""
echo -e "${BLUE}--- Workflows API ---${NC}"

response=$(curl -s -m 30 -w "\n%{http_code}" -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" -H "kbn-xsrf: true" "$KIBANA_URL/api/workflows" 2>/dev/null)
http_code=$(echo "$response" | tail -n1)

if [ "$http_code" == "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Workflows API (HTTP 200)"
    echo -e "${GREEN}  ✓ Workflows API is AVAILABLE!${NC}"
    ((PASS++))
    WORKFLOWS_AVAILABLE=true
elif [ "$http_code" == "404" ]; then
    echo -e "${YELLOW}⚠ SKIP${NC} - Workflows API (HTTP 404 - Not available)"
    echo "  Expected on Serverless. Use Kibana UI for workflows."
else
    echo -e "${RED}✗ FAIL${NC} - Workflows API (HTTP $http_code)"
    ((FAIL++))
fi

echo ""
echo -e "${BLUE}--- Alerting API ---${NC}"

test_endpoint "Alerting Health" "$KIBANA_URL/api/alerting/_health" '"is'
test_endpoint "Rule Types" "$KIBANA_URL/api/alerting/rule_types" '"id"'
test_endpoint "Find Rules" "$KIBANA_URL/api/alerting/rules/_find" '"data"'

echo ""
echo -e "${BLUE}--- Connectors API ---${NC}"

test_endpoint "List Connectors" "$KIBANA_URL/api/actions/connectors" '"id"'

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "  ${GREEN}Passed: $PASS${NC}"
echo -e "  ${RED}Failed: $FAIL${NC}"
echo ""

if [ "$WORKFLOWS_AVAILABLE" == "true" ]; then
    echo -e "${GREEN}✓ Workflows API is AVAILABLE - full API access!${NC}"
else
    echo -e "${YELLOW}⚠ Workflows API not available - use Kibana UI${NC}"
fi

echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All tests passed! Cluster is ready.${NC}"
    exit 0
else
    echo -e "${YELLOW}Some tests failed. Check output above.${NC}"
    exit 1
fi
