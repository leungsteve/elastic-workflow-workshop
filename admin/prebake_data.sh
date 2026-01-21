#!/bin/bash
#
# Pre-bake Workshop Data Files
#
# Run this script ONCE when building the workshop image to generate
# the sample data files. These files will be included in the image
# so the workshop setup is faster.
#
# Usage:
#   ./admin/prebake_data.sh
#
# After running, the following files will be created:
#   - data/sample/businesses.ndjson (300 businesses)
#   - data/sample/users.ndjson (1500 users)
#   - data/sample/reviews.ndjson (8000 reviews)
#   - data/sample/attacker_users.ndjson (10 pre-generated attackers)
#   - data/sample/attack_reviews.ndjson (50 pre-generated attack reviews)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "  Pre-baking Workshop Data Files"
echo "=============================================="
echo ""

# Check Python dependencies
python3 -c "import faker, yaml, tqdm" 2>/dev/null || {
    echo "Installing required Python packages..."
    pip3 install faker pyyaml tqdm python-dotenv elasticsearch
}

# Generate sample data
echo "Generating sample data..."
echo "  - 300 businesses"
echo "  - 1500 users"
echo "  - 8000 reviews"
echo "  - 10 attacker users"
echo "  - 50 attack reviews"
echo ""

PYTHONPATH="$PROJECT_ROOT" python3 -m admin.generate_sample_data \
    --businesses 300 \
    --users 1500 \
    --reviews 8000 \
    --output data/sample

echo ""
echo "=============================================="
echo "  Data files generated successfully!"
echo "=============================================="
echo ""
echo "Files created:"
ls -lh data/sample/*.ndjson
echo ""
echo "Total size:"
du -sh data/sample/
echo ""
echo "These files are ready to be included in the workshop image."
echo "The setup_workshop_data.sh script will load them at workshop start."
