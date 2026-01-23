#!/bin/bash
#
# Master script to prepare all data for the Review Fraud Workshop.
#
# This script runs all data preparation steps in the correct order:
# 1. Create Elasticsearch indices
# 2. Filter businesses from Yelp data
# 3. Extract users who reviewed those businesses
# 4. Calculate trust scores for users
# 5. Partition reviews into historical/streaming sets
# 6. Generate synthetic attack data
# 7. Load data into Elasticsearch
# 8. Verify the environment
#
# Usage:
#   ./admin/prepare_data.sh [options]
#
# Options:
#   --dry-run        Preview all steps without making changes
#   --skip-indices   Skip index creation (if indices already exist)
#   --skip-filter    Skip filtering steps (use existing processed files)
#   --skip-attack    Skip attack data generation
#   --skip-load      Skip data loading (just prepare files)
#   --delete-existing Delete existing indices before creating new ones
#   --verbose        Enable verbose output for all steps
#   --sample-only    Use sample data instead of real Yelp data
#   --help           Show this help message
#
# Environment Variables:
#   ELASTICSEARCH_URL       Elasticsearch URL (default: http://localhost:9200)
#   ELASTICSEARCH_API_KEY   API key for authentication
#   ELASTICSEARCH_USERNAME  Username for basic auth
#   ELASTICSEARCH_PASSWORD  Password for basic auth
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default options
DRY_RUN=""
SKIP_INDICES=false
SKIP_FILTER=false
SKIP_ATTACK=false
SKIP_LOAD=false
VERBOSE=""
DELETE_EXISTING=""
SAMPLE_ONLY=false

# Counters for summary
STEPS_COMPLETED=0
STEPS_SKIPPED=0
STEPS_FAILED=0
START_TIME=$(date +%s)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --skip-indices)
            SKIP_INDICES=true
            shift
            ;;
        --skip-filter)
            SKIP_FILTER=true
            shift
            ;;
        --skip-attack)
            SKIP_ATTACK=true
            shift
            ;;
        --skip-load)
            SKIP_LOAD=true
            shift
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --delete-existing)
            DELETE_EXISTING="--delete-existing --force"
            shift
            ;;
        --sample-only)
            SAMPLE_ONLY=true
            shift
            ;;
        --help|-h)
            # Print lines 2-34 (the comment block)
            sed -n '2,34p' "$0" | sed 's/^# *//'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help to see available options."
            exit 1
            ;;
    esac
done

# Helper functions
log_step() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

log_substep() {
    echo -e "${CYAN}>>> $1${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

# Format duration
format_duration() {
    local seconds=$1
    local minutes=$((seconds / 60))
    local remaining_seconds=$((seconds % 60))
    if [[ $minutes -gt 0 ]]; then
        echo "${minutes}m ${remaining_seconds}s"
    else
        echo "${remaining_seconds}s"
    fi
}

# Find Python executable (prefer python3)
find_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo ""
    fi
}

PYTHON_CMD=$(find_python)

# Check Python is available
check_python() {
    log_substep "Checking Python installation..."

    if [[ -z "$PYTHON_CMD" ]]; then
        log_error "Python not found. Please install Python 3.8+."
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 8 ]]; then
        log_error "Python 3.8+ required, found Python $PYTHON_VERSION"
        exit 1
    fi

    log_success "Using Python $PYTHON_VERSION"
}

# Check required Python packages
check_python_packages() {
    log_substep "Checking Python dependencies..."

    local MISSING=0
    for pkg in click tqdm faker yaml elasticsearch dotenv; do
        if ! $PYTHON_CMD -c "import $pkg" 2>/dev/null; then
            log_warn "Missing Python package: $pkg"
            MISSING=$((MISSING + 1))
        fi
    done

    if [[ $MISSING -gt 0 ]]; then
        log_warn "Some packages are missing. Install with: pip install -r requirements.txt"
    else
        log_success "All Python dependencies available"
    fi
}

# Check Elasticsearch connection
check_elasticsearch() {
    log_substep "Checking Elasticsearch connection..."

    local ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

    # Try to connect to Elasticsearch
    if command -v curl &> /dev/null; then
        local CURL_OPTS="-s --connect-timeout 5"

        # Add auth if provided
        if [[ -n "$ELASTICSEARCH_API_KEY" ]]; then
            CURL_OPTS="$CURL_OPTS -H \"Authorization: ApiKey $ELASTICSEARCH_API_KEY\""
        elif [[ -n "$ELASTICSEARCH_USERNAME" && -n "$ELASTICSEARCH_PASSWORD" ]]; then
            CURL_OPTS="$CURL_OPTS -u $ELASTICSEARCH_USERNAME:$ELASTICSEARCH_PASSWORD"
        fi

        if eval "curl $CURL_OPTS \"$ES_URL\"" > /dev/null 2>&1; then
            log_success "Elasticsearch reachable at $ES_URL"
        else
            log_warn "Cannot connect to Elasticsearch at $ES_URL"
            log_warn "Make sure Elasticsearch is running and accessible"
            if [[ "$SKIP_LOAD" == "false" ]]; then
                log_warn "Data loading will fail without Elasticsearch"
            fi
        fi
    else
        log_warn "curl not found, skipping Elasticsearch check"
    fi
}

# Check required Yelp data files exist
check_raw_data() {
    log_step "Step 0: Checking prerequisites..."

    check_python
    check_python_packages
    check_elasticsearch

    if [[ "$SAMPLE_ONLY" == "true" ]]; then
        log_info "Sample-only mode: skipping Yelp data check"
        return 0
    fi

    log_substep "Checking Yelp data files..."

    local RAW_DIR="$PROJECT_ROOT/data/raw"
    local MISSING=0
    local TOTAL_SIZE=0

    for file in yelp_academic_dataset_business.json yelp_academic_dataset_review.json yelp_academic_dataset_user.json; do
        if [[ -f "$RAW_DIR/$file" ]]; then
            local SIZE=$(du -h "$RAW_DIR/$file" | cut -f1)
            log_success "Found: $file ($SIZE)"
            TOTAL_SIZE=$((TOTAL_SIZE + $(stat -f%z "$RAW_DIR/$file" 2>/dev/null || stat -c%s "$RAW_DIR/$file" 2>/dev/null || echo 0)))
        else
            log_error "Missing: $file"
            MISSING=$((MISSING + 1))
        fi
    done

    if [[ $MISSING -gt 0 ]]; then
        echo ""
        log_error "Missing $MISSING required data files in $RAW_DIR"
        echo ""
        log_info "To obtain the Yelp Academic Dataset:"
        log_info "  1. Visit https://www.yelp.com/dataset"
        log_info "  2. Sign the license agreement and download"
        log_info "  3. Extract the JSON files to: $RAW_DIR"
        echo ""
        log_info "Alternatively, use --sample-only to work with generated sample data"
        exit 1
    fi

    log_success "All Yelp data files present"
}

# Run a Python module with error handling
run_module() {
    local MODULE=$1
    shift
    local ARGS="$@"
    local STEP_START=$(date +%s)

    log_info "Running: $PYTHON_CMD -m $MODULE $ARGS"

    cd "$PROJECT_ROOT"

    if $PYTHON_CMD -m "$MODULE" $ARGS; then
        local STEP_END=$(date +%s)
        local STEP_DURATION=$((STEP_END - STEP_START))
        log_success "Completed in $(format_duration $STEP_DURATION)"
        STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
        return 0
    else
        log_error "Module $MODULE failed!"
        STEPS_FAILED=$((STEPS_FAILED + 1))
        return 1
    fi
}

# Check if processed files exist
check_processed_files() {
    local PROCESSED_DIR="$PROJECT_ROOT/data/processed"

    if [[ -f "$PROCESSED_DIR/businesses.ndjson" ]] && \
       [[ -f "$PROCESSED_DIR/users.ndjson" ]]; then
        return 0
    else
        return 1
    fi
}

# Generate sample data if needed
generate_sample_if_needed() {
    if [[ "$SAMPLE_ONLY" == "true" ]]; then
        log_step "Generating sample data..."
        run_module admin.generate_sample_data $DRY_RUN $VERBOSE --output "$PROJECT_ROOT/data/sample"
    fi
}

# Main execution
main() {
    echo -e "${GREEN}"
    echo "=============================================================="
    echo "       Review Fraud Workshop - Data Preparation"
    echo "=============================================================="
    echo -e "${NC}"
    echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    if [[ -n "$DRY_RUN" ]]; then
        log_warn "DRY RUN MODE - No changes will be made"
        echo ""
    fi

    # Pre-flight checks
    check_raw_data

    # Step 1: Create indices
    if [[ "$SKIP_INDICES" == "false" ]]; then
        log_step "Step 1: Creating Elasticsearch indices..."
        if ! run_module admin.create_indices $DRY_RUN $VERBOSE $DELETE_EXISTING; then
            log_error "Index creation failed. Use --skip-indices to skip."
            exit 1
        fi
    else
        log_step "Step 1: Skipping index creation (--skip-indices)"
        STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
    fi

    # Step 2-5: Data filtering and processing
    if [[ "$SKIP_FILTER" == "false" ]]; then
        if [[ "$SAMPLE_ONLY" == "true" ]]; then
            generate_sample_if_needed

            log_step "Step 2-5: Using sample data (--sample-only)"
            log_info "Sample data already includes processed businesses, users, and reviews"
            STEPS_SKIPPED=$((STEPS_SKIPPED + 4))
        else
            log_step "Step 2: Filtering businesses..."
            if ! run_module admin.filter_businesses $DRY_RUN $VERBOSE; then
                log_error "Business filtering failed"
                exit 1
            fi

            log_step "Step 3: Extracting users..."
            if ! run_module admin.filter_users $DRY_RUN $VERBOSE; then
                log_error "User extraction failed"
                exit 1
            fi

            log_step "Step 4: Calculating trust scores..."
            if ! run_module admin.calculate_trust_scores $DRY_RUN $VERBOSE; then
                log_error "Trust score calculation failed"
                exit 1
            fi

            log_step "Step 5: Partitioning reviews..."
            if ! run_module admin.partition_reviews $DRY_RUN $VERBOSE; then
                log_error "Review partitioning failed"
                exit 1
            fi
        fi
    else
        log_step "Steps 2-5: Skipping data filtering (--skip-filter)"

        # Verify processed files exist
        if ! check_processed_files; then
            log_error "Processed data files not found!"
            log_error "Cannot skip filtering without existing processed files."
            log_error "Remove --skip-filter or run filtering first."
            exit 1
        fi
        log_info "Using existing processed files"
        STEPS_SKIPPED=$((STEPS_SKIPPED + 4))
    fi

    # Step 6: Generate attack data
    if [[ "$SKIP_ATTACK" == "false" ]]; then
        log_step "Step 6: Generating attack data..."
        if ! run_module admin.generate_attackers $DRY_RUN $VERBOSE; then
            log_warn "Attack data generation failed (non-fatal)"
            log_warn "You can generate attack data later with: python -m admin.generate_attackers"
        fi
    else
        log_step "Step 6: Skipping attack data generation (--skip-attack)"
        STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
    fi

    # Step 7: Load data
    if [[ "$SKIP_LOAD" == "false" ]]; then
        log_step "Step 7: Loading data into Elasticsearch..."
        if ! run_module admin.load_data $DRY_RUN $VERBOSE; then
            log_error "Data loading failed"
            log_error "Check Elasticsearch connection and try again"
            exit 1
        fi
    else
        log_step "Step 7: Skipping data loading (--skip-load)"
        STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
    fi

    # Step 8: Verify environment
    log_step "Step 8: Verifying environment..."
    if ! run_module admin.verify_environment $VERBOSE; then
        log_warn "Environment verification had warnings"
    fi

    # Calculate duration
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # Print summary
    echo ""
    echo -e "${GREEN}"
    echo "=============================================================="
    echo "               Data Preparation Complete!"
    echo "=============================================================="
    echo -e "${NC}"

    echo "Summary:"
    echo "  - Steps completed: $STEPS_COMPLETED"
    echo "  - Steps skipped:   $STEPS_SKIPPED"
    echo "  - Steps failed:    $STEPS_FAILED"
    echo "  - Total time:      $(format_duration $DURATION)"
    echo ""

    if [[ $STEPS_FAILED -gt 0 ]]; then
        log_error "Some steps failed. Review the output above for details."
        exit 1
    fi

    if [[ -n "$DRY_RUN" ]]; then
        log_warn "This was a dry run. Re-run without --dry-run to make actual changes."
    else
        echo "Generated data files:"
        echo "  - data/processed/businesses.ndjson"
        echo "  - data/processed/users.ndjson"
        echo "  - data/historical/reviews.ndjson"
        echo "  - data/streaming/reviews.ndjson"
        echo "  - data/attack/users.ndjson"
        echo "  - data/attack/reviews.ndjson"
        echo ""
        log_success "The workshop environment is ready!"
        log_info "You can now start the workshop application with: make run"
    fi
}

# Run main
main
