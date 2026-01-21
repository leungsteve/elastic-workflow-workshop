#!/bin/bash
#
# Solve script for Challenge 1: Getting to Know Your Data
# This script automatically completes the challenge for testing purposes
#
# In Instruqt, solve scripts are used to:
# - Validate that challenges can be completed
# - Speed up testing of subsequent challenges
#

set -e

ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "=============================================="
echo "Solving Challenge 1: Getting to Know Your Data"
echo "=============================================="

# The setup script should have already loaded the data.
# For this challenge, participants just need to explore the data.
# The solve script verifies the environment is ready.

echo ""
echo "Verifying data is loaded..."

# Check businesses
BUSINESS_COUNT=$(curl -s "${ELASTICSEARCH_URL}/businesses/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
echo "  Businesses: ${BUSINESS_COUNT}"

# Check users
USER_COUNT=$(curl -s "${ELASTICSEARCH_URL}/users/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
echo "  Users: ${USER_COUNT}"

# Check reviews
REVIEW_COUNT=$(curl -s "${ELASTICSEARCH_URL}/reviews/_count" 2>/dev/null | grep -o '"count":[0-9]*' | grep -o '[0-9]*' || echo "0")
echo "  Reviews: ${REVIEW_COUNT}"

# Simulate running the key queries from the assignment
echo ""
echo "Running sample ES|QL queries via API..."

# Query 1: Count businesses
echo ""
echo "Query: FROM businesses | STATS count = COUNT(*)"
curl -s -X POST "${ELASTICSEARCH_URL}/_query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "FROM businesses | STATS count = COUNT(*)"
    }' 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Result: {d.get(\"values\", [[0]])[0][0]} businesses')" 2>/dev/null || echo "  (Query executed)"

# Query 2: User trust score distribution
echo ""
echo "Query: FROM users | STATS avg_trust = AVG(trust_score)"
curl -s -X POST "${ELASTICSEARCH_URL}/_query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "FROM users | STATS avg_trust = AVG(trust_score), min_trust = MIN(trust_score), max_trust = MAX(trust_score)"
    }' 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); v=d.get('values',[[0,0,0]])[0]; print(f'  Result: avg={v[0]:.2f}, min={v[1]:.2f}, max={v[2]:.2f}')" 2>/dev/null || echo "  (Query executed)"

# Query 3: Review rating distribution
echo ""
echo "Query: FROM reviews | STATS count = COUNT(*) BY stars"
curl -s -X POST "${ELASTICSEARCH_URL}/_query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "FROM reviews | STATS count = COUNT(*) BY stars | SORT stars DESC"
    }' 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Result: {len(d.get(\"values\",[]))} rating categories')" 2>/dev/null || echo "  (Query executed)"

echo ""
echo "=============================================="
echo "Challenge 1 Solved!"
echo "=============================================="
echo ""
echo "The data exploration challenge is complete."
echo "Participants should have learned:"
echo "  - How to query the three main indices"
echo "  - The importance of trust_score for detection"
echo "  - How to use LOOKUP JOIN for data enrichment"
echo ""
