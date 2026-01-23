# Admin Scripts for Review Fraud Detection Workshop

This directory contains scripts for preparing data for the Review Fraud Detection Workshop. These scripts process the Yelp Academic Dataset and prepare it for use with Elasticsearch.

## Prerequisites

### 1. Yelp Academic Dataset

The workshop uses the Yelp Academic Dataset for realistic review data. To obtain the dataset:

1. Visit [Yelp Dataset](https://www.yelp.com/dataset)
2. Sign the license agreement and download the dataset
3. Extract the following JSON files to `data/raw/`:
   - `yelp_academic_dataset_business.json`
   - `yelp_academic_dataset_review.json`
   - `yelp_academic_dataset_user.json`

**Note:** The Yelp dataset is approximately 10GB uncompressed.

### 2. Python Environment

Install required Python packages:

```bash
pip install -r requirements.txt
```

Required packages:
- `click` - CLI framework
- `tqdm` - Progress bars
- `faker` - Synthetic data generation
- `pyyaml` - Configuration parsing
- `elasticsearch` - Elasticsearch client
- `python-dotenv` - Environment variable loading

### 3. Elasticsearch

Ensure Elasticsearch is running and accessible. Configure connection via environment variables:

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your Elasticsearch credentials
export ELASTICSEARCH_URL=http://localhost:9200
export ELASTICSEARCH_API_KEY=your-api-key  # Or use username/password
```

## Quick Start

Run the full data preparation pipeline:

```bash
# Make the script executable
chmod +x admin/prepare_data.sh

# Run full preparation
./admin/prepare_data.sh

# Or with dry-run to preview
./admin/prepare_data.sh --dry-run --verbose
```

---

## Instruqt Workshop Setup

For Instruqt workshops, use these specialized scripts:

### prebake_data.sh

Run **once during image build** to generate sample data files:

```bash
./admin/prebake_data.sh
```

Creates:
- `data/sample/businesses.ndjson` (300 businesses)
- `data/sample/users.ndjson` (1500 users)
- `data/sample/reviews.ndjson` (8000 reviews)
- `data/sample/attacker_users.ndjson` (10 attackers)
- `data/sample/attack_reviews.ndjson` (50 attack reviews)

### setup_workshop_data.sh

Run **at workshop start** (in Instruqt setup script) to load data into Elasticsearch:

```bash
./admin/setup_workshop_data.sh
```

This script:
1. Waits for Elasticsearch to be available
2. Creates indices with proper mappings (including `index.mode: lookup`)
3. Loads pre-generated data files
4. Verifies data was loaded correctly

**Instruqt Integration Example:**

```yaml
# In track.yml or challenge setup script
lifecycle:
  setup:
    script: |
      cd /workspace/elastic-workflow-workshop
      ./admin/setup_workshop_data.sh
```

### Recommended Workflow

1. **Image Build Time:**
   ```bash
   ./admin/prebake_data.sh
   ```

2. **Workshop Start (Instruqt setup):**
   ```bash
   ./admin/setup_workshop_data.sh
   ```

This approach gives you:
- Consistent data across all participants
- Fast startup (~15 seconds to load data)
- Fresh indices each session (no leftover attack data)

---

## Individual Scripts

### filter_businesses.py

Filters Yelp businesses by city and category.

```bash
# Filter with default settings (Las Vegas, Phoenix, Toronto + Restaurants, Food, Bars)
python -m admin.filter_businesses

# Filter specific cities
python -m admin.filter_businesses --city "Las Vegas" --city "Phoenix"

# Limit output for testing
python -m admin.filter_businesses --limit 1000

# Preview without writing
python -m admin.filter_businesses --dry-run
```

**Input:** `data/raw/yelp_academic_dataset_business.json`
**Output:** `data/processed/businesses.ndjson`

### filter_users.py

Extracts users who have reviewed the filtered businesses.

```bash
# Extract users with default settings
python -m admin.filter_users

# Limit number of users
python -m admin.filter_users --limit 50000

# Preview without writing
python -m admin.filter_users --dry-run
```

**Input:**
- `data/processed/businesses.ndjson`
- `data/raw/yelp_academic_dataset_review.json`
- `data/raw/yelp_academic_dataset_user.json`

**Output:** `data/processed/users-raw.ndjson`

### calculate_trust_scores.py

Calculates trust scores for users based on their profile.

Trust score formula considers:
- **Review count** (25%): Users with more reviews are more trusted
- **Useful votes** (15%): Recognition from other users
- **Fans** (10%): Follower count
- **Elite status** (5% per year, max 50%): Yelp Elite members
- **Account age** (25%): Older accounts are more trusted
- **Rating balance** (20%): Users with average ratings near 3.5

```bash
# Calculate trust scores
python -m admin.calculate_trust_scores

# Preview with statistics
python -m admin.calculate_trust_scores --dry-run --verbose
```

**Input:** `data/processed/users-raw.ndjson`
**Output:** `data/processed/users.ndjson`

### partition_reviews.py

Splits reviews into historical and streaming sets.

- **Historical (80%):** Pre-loaded into Elasticsearch before workshop
- **Streaming (20%):** Replayed during workshop demo

```bash
# Partition with default 80/20 split
python -m admin.partition_reviews

# Custom split ratio
python -m admin.partition_reviews --historical-ratio 0.9

# Preview without writing
python -m admin.partition_reviews --dry-run
```

**Input:**
- `data/raw/yelp_academic_dataset_review.json`
- `data/processed/businesses.ndjson`

**Output:**
- `data/historical/reviews.ndjson`
- `data/streaming/reviews.ndjson`

### generate_attackers.py

Creates synthetic attacker accounts and attack reviews.

Attackers have:
- Low trust scores (0.05-0.20)
- New accounts (1-30 days old)
- No friends or fans
- No elite status

```bash
# Generate default attack data (auto-select target)
python -m admin.generate_attackers

# Target a specific business
python -m admin.generate_attackers --target-business-id abc123

# Generate larger attack
python -m admin.generate_attackers --num-attackers 25 --num-reviews 100

# Preview without writing
python -m admin.generate_attackers --dry-run
```

**Input:** `data/processed/businesses.ndjson`
**Output:**
- `data/attack/users.ndjson`
- `data/attack/reviews.ndjson`
- `data/attack/target_business.json`

### generate_sample_data.py

Generates synthetic sample data for development/testing without Yelp dataset.

```bash
# Generate default sample data
python -m admin.generate_sample_data

# Generate larger dataset
python -m admin.generate_sample_data --businesses 500 --users 2000 --reviews 10000
```

**Output:**
- `data/sample/businesses.ndjson`
- `data/sample/users.ndjson`
- `data/sample/reviews.ndjson`
- `data/sample/attacker_users.ndjson`
- `data/sample/attack_reviews.ndjson`

### create_indices.py

Creates Elasticsearch indices with proper mappings.

```bash
# Create indices
python -m admin.create_indices

# Delete existing and recreate
python -m admin.create_indices --delete-existing --force
```

### load_data.py

Loads prepared data into Elasticsearch.

```bash
# Load all data
python -m admin.load_data

# Load specific types
python -m admin.load_data --only businesses
python -m admin.load_data --only users
python -m admin.load_data --only reviews
```

### verify_environment.py

Verifies the workshop environment is correctly configured.

```bash
python -m admin.verify_environment --verbose
```

## prepare_data.sh Options

The master script supports the following options:

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview all steps without making changes |
| `--skip-indices` | Skip index creation (if indices already exist) |
| `--skip-filter` | Skip filtering steps (use existing processed files) |
| `--skip-attack` | Skip attack data generation |
| `--skip-load` | Skip data loading (just prepare files) |
| `--delete-existing` | Delete existing indices before creating new ones |
| `--verbose` | Enable verbose output for all steps |
| `--sample-only` | Use sample data instead of real Yelp data |
| `--help` | Show help message |

## Expected Output Structure

After running the full pipeline:

```
data/
  raw/                          # Original Yelp data (input)
    yelp_academic_dataset_business.json
    yelp_academic_dataset_review.json
    yelp_academic_dataset_user.json
  processed/                    # Filtered and transformed data
    businesses.ndjson           # Filtered businesses
    users-raw.ndjson            # Raw extracted users
    users.ndjson                # Users with trust scores
  historical/                   # Data loaded before workshop
    reviews.ndjson              # 80% of reviews
  streaming/                    # Data for live replay
    reviews.ndjson              # 20% of reviews
  attack/                       # Synthetic attack data
    users.ndjson                # Attacker accounts
    reviews.ndjson              # Attack reviews
    target_business.json        # Target business info
  sample/                       # Generated sample data (optional)
    businesses.ndjson
    users.ndjson
    reviews.ndjson
    attacker_users.ndjson
    attack_reviews.ndjson
```

## Troubleshooting

### Missing Yelp Data Files

```
[ERROR] Missing: yelp_academic_dataset_business.json
```

**Solution:** Download the Yelp Academic Dataset and extract JSON files to `data/raw/`.

### Elasticsearch Connection Failed

```
[WARN] Cannot connect to Elasticsearch at http://localhost:9200
```

**Solution:**
1. Ensure Elasticsearch is running
2. Check the `ELASTICSEARCH_URL` environment variable
3. Verify authentication credentials

### Python Package Not Found

```
ModuleNotFoundError: No module named 'click'
```

**Solution:** Install dependencies with `pip install -r requirements.txt`

### Memory Issues with Large Files

For very large datasets, you may encounter memory issues. Solutions:
1. Use `--limit` options to reduce data size
2. Increase available memory
3. Process in chunks (modify scripts if needed)

### Permission Denied on prepare_data.sh

```
bash: ./admin/prepare_data.sh: Permission denied
```

**Solution:** Make the script executable: `chmod +x admin/prepare_data.sh`

### Processed Files Already Exist

The scripts are idempotent and will overwrite existing files. Use `--dry-run` to preview changes first.

## Configuration

Edit `config/config.yaml` to customize:

- Cities to filter
- Categories to include
- Historical/streaming split ratio
- Maximum document limits
- Attack simulation parameters

## Development

### Running Individual Scripts in Debug Mode

```bash
# With verbose output
python -m admin.filter_businesses --verbose

# With specific config file
python -m admin.filter_businesses --config path/to/config.yaml

# With specific environment file
python -m admin.filter_businesses --env path/to/.env
```

### Testing with Sample Data

For development without the full Yelp dataset:

```bash
# Generate sample data
python -m admin.generate_sample_data

# Use sample data for other operations
python -m admin.generate_attackers \
  --businesses data/sample/businesses.ndjson \
  --users-output data/sample/attack_users.ndjson \
  --reviews-output data/sample/attack_reviews.ndjson
```
