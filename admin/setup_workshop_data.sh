#!/bin/bash
#
# Setup Workshop Data for Instruqt
#
# This script initializes the Elasticsearch indices and loads pre-generated
# sample data for the Review Fraud Detection workshop.
#
# Usage:
#   ./admin/setup_workshop_data.sh
#
# Prerequisites:
#   - .env file with ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY
#   - Pre-generated data files in data/sample/
#
# This script is designed to run during Instruqt challenge setup.
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Load environment variables
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    log_info "Loaded environment from .env"
else
    log_error ".env file not found"
    exit 1
fi

# Validate required environment variables
if [ -z "$ELASTICSEARCH_URL" ]; then
    log_error "ELASTICSEARCH_URL not set"
    exit 1
fi

if [ -z "$ELASTICSEARCH_API_KEY" ]; then
    log_error "ELASTICSEARCH_API_KEY not set"
    exit 1
fi

# Check for required data files
DATA_DIR="data/sample"
REQUIRED_FILES=("businesses.ndjson" "users.ndjson" "reviews.ndjson")

log_info "Checking for required data files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$DATA_DIR/$file" ]; then
        log_warn "$DATA_DIR/$file not found - will generate sample data"
        GENERATE_DATA=true
        break
    fi
done

# Wait for Elasticsearch to be available
log_info "Waiting for Elasticsearch to be available..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s --max-time 5 -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" \
        "$ELASTICSEARCH_URL" > /dev/null 2>&1; then
        log_success "Elasticsearch is available"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        log_error "Elasticsearch not available after $MAX_RETRIES attempts"
        exit 1
    fi
    echo -n "."
    sleep 2
done

# Get ES version for logging
ES_VERSION=$(curl -s -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" \
    "$ELASTICSEARCH_URL" | python3 -c "import sys,json; print(json.load(sys.stdin)['version']['number'])" 2>/dev/null || echo "unknown")
log_info "Elasticsearch version: $ES_VERSION"

# Generate sample data if needed
if [ "$GENERATE_DATA" = true ]; then
    log_info "Generating sample data..."
    PYTHONPATH="$PROJECT_ROOT" python3 -m admin.generate_sample_data \
        --businesses 300 \
        --users 1500 \
        --reviews 8000 \
        --output "$DATA_DIR"

    if [ $? -eq 0 ]; then
        log_success "Sample data generated"
    else
        log_error "Failed to generate sample data"
        exit 1
    fi
fi

# Create indices
log_info "Creating Elasticsearch indices..."
PYTHONPATH="$PROJECT_ROOT" python3 -m admin.create_indices --delete-existing --force

if [ $? -eq 0 ]; then
    log_success "Indices created"
else
    log_error "Failed to create indices"
    exit 1
fi

# Load data
log_info "Loading data into Elasticsearch..."
PYTHONPATH="$PROJECT_ROOT" python3 -m admin.load_data \
    --businesses-file "$DATA_DIR/businesses.ndjson" \
    --users-file "$DATA_DIR/users.ndjson" \
    --reviews-file "$DATA_DIR/reviews.ndjson"

if [ $? -eq 0 ]; then
    log_success "Data loaded successfully"
else
    log_error "Failed to load data"
    exit 1
fi

# Load attacker users if they exist (optional)
if [ -f "$DATA_DIR/attacker_users.ndjson" ]; then
    log_info "Loading pre-generated attacker users..."
    PYTHONPATH="$PROJECT_ROOT" python3 -m admin.load_data \
        --users-file "$DATA_DIR/attacker_users.ndjson" \
        -t users
    log_success "Attacker users loaded"
fi

# Verify data was loaded
log_info "Verifying data load..."
echo ""

# Count documents in each index
for index in businesses users reviews; do
    COUNT=$(curl -s -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" \
        "$ELASTICSEARCH_URL/$index/_count" 2>/dev/null | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
    echo "  $index: $COUNT documents"
done

echo ""
log_success "Workshop data setup complete!"
echo ""
echo "=============================================="
echo "  Workshop is ready!"
echo "=============================================="
echo "  Businesses: $(curl -s -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" "$ELASTICSEARCH_URL/businesses/_count" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null)"
echo "  Users:      $(curl -s -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" "$ELASTICSEARCH_URL/users/_count" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null)"
echo "  Reviews:    $(curl -s -H "Authorization: ApiKey $ELASTICSEARCH_API_KEY" "$ELASTICSEARCH_URL/reviews/_count" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null)"
echo "=============================================="
