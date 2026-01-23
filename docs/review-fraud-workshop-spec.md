# Review Bomb Detection Workshop Specification

## Project Overview

This document provides specifications for building a workshop that demonstrates Elastic's Workflows feature (headline for 9.3) using a review bomb detection scenario. The workshop extends the existing "What's New in Elastic Search" series.

### Workshop Story Arc

| Step | Feature | User Action |
|------|---------|-------------|
| **Search** | Semantic + Keyword + ES|QL | Explore data, find patterns, detect anomalies |
| **Automate** | Workflows | Build automated detection and response |
| **Investigate** | Agent Builder | Create tools to analyze incidents |
| **Observe** | End-to-End | Participate in attack, watch the complete lifecycle |

### Key Message

"Search finds the insight. Workflows acts on it. Agent Builder explains it."

---

## Workshop Structure

### Total Duration: 90 Minutes

| Section | Duration | Content |
|---------|----------|---------|
| Presentation | 30 min | Problem statement, 9.3 highlights, live demo |
| Hands-on Labs | 60 min | Four challenges |

### Presentation Breakdown (30 minutes)

| Segment | Time | Content |
|---------|------|---------|
| Opening Hook | 5 min | The review bomb problem, real-world impact |
| 9.3 Highlights | 5 min | Workflows introduction, Keep acquisition context |
| Live Demo | 15 min | Walk through detection, workflow execution, investigation |
| Workshop Preview | 5 min | Challenge overview, environment access |

### Challenge Breakdown (60 minutes)

| Challenge | Title | Time | Focus |
|-----------|-------|------|-------|
| 1 | Getting to Know Your Data | 15 min | Explore environment, ES|QL queries, detection logic with LOOKUP JOIN |
| 2 | Workflows | 20 min | Build detection and response workflow (headline feature) |
| 3 | Agent Builder | 10 min | Create investigation tools |
| 4 | End-to-End Scenario | 15 min | Use UI to attack, watch workflow respond, investigate, resolve |

---

## Environment Configuration

### Multi-Environment Support

The workshop supports multiple Elasticsearch environments:

| Environment | Auth Method | Use Case |
|-------------|-------------|----------|
| Cloud Serverless | API Key | Primary development, Cloud workshops |
| Local VM (Instruqt) | Username/Password | Instruqt workshops with local Elastic |
| Kubernetes (Instruqt) | Username/Password or API Key | Container-based Instruqt |

### Configuration Files

```
.env.example          # Template (committed to repo)
.env.local            # Local/VM configuration (gitignored)
.env.cloud            # Cloud Serverless configuration (gitignored)
.env                  # Active configuration (gitignored, copy from .env.local or .env.cloud)
config/config.yaml    # Non-sensitive configuration (committed)
```

### Environment Variables

```bash
# .env.example

# Elasticsearch Connection
ELASTICSEARCH_URL=https://your-cluster.es.cloud.elastic.co:443

# Authentication (use ONE of the following)
# For Cloud Serverless:
ELASTICSEARCH_API_KEY=your-api-key

# For Local/VM:
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=changeme

# Application Settings
APP_ENV=development    # development | production
APP_PORT=8000
LOG_LEVEL=INFO

# ELSER Inference (verify availability in your environment)
ELSER_INFERENCE_ID=elser
```

### Config YAML

> **Note:** Environment variables override config.yaml settings for sensitive values (e.g., `ELASTICSEARCH_URL`, `ELASTICSEARCH_API_KEY`). This allows the same config.yaml to be used across environments while keeping credentials secure.

```yaml
# config/config.yaml

app:
  name: "Review Bomb Workshop"
  port: 8000

elasticsearch:
  indices:
    businesses: "businesses"
    users: "users"
    reviews: "reviews"
    incidents: "incidents"
    notifications: "notifications"

streaming:
  replay:
    reviews_per_second: 3
    source: "data/streaming/reviews.ndjson"

data:
  cities: ["Las Vegas", "Phoenix", "Toronto"]
  categories: ["Restaurants", "Food", "Bars", "Cafes"]
  historical_ratio: 0.8

attack:
  default_stars: 1
  reviewer_trust_range: [0.05, 0.20]
  reviewer_account_age_range: [1, 30]
```

---

## Data Strategy

### Hybrid Approach

The workshop uses a combination of real Yelp data and synthetic attack data.

| Data Type | Source | Purpose |
|-----------|--------|---------|
| Businesses | Real Yelp data | Authentic business names, categories, locations |
| Users | Real Yelp data | Genuine user profiles with calculated trust scores |
| Historical Reviews | Real Yelp data | Baseline review activity, status = "published" |
| Streaming Reviews | Real Yelp data (held back) | Normal platform activity during demo |
| Attack Reviews | Participant-generated via UI | Interactive review bomb with custom content |
| Attacker Accounts | Auto-generated per submission | Low trust scores, new accounts |

### Why Hybrid with Interactive Attack?

**Real data for the baseline** gives authenticity. Participants see actual business names, real review text, and genuine user patterns.

**Interactive attack via UI** gives engagement. Participants:
- Choose which business to attack
- Generate and customize review text
- See their own reviews appear in the system
- Watch the workflow detect and respond to their attack
- Creates a "this is real" feeling

### Data Volumes

| Index | Pre-loaded Volume | Notes |
|-------|-------------------|-------|
| `businesses` | 10-20K | Filter to restaurants in 2-3 cities |
| `users` | 50-100K | Include calculated trust scores |
| `reviews` (historical) | 200-500K | Status = "published" |
| `reviews` (streaming) | 10-20K | Held back for real-time replay |

### Review Partitioning

Split the Yelp reviews:
- **Historical (80%):** Pre-loaded before workshop, status = "published"
- **Streaming (20%):** Held back for real-time replay during demo

### Sample Data for Development

A small sample dataset is included for development/testing without the full Yelp download:

```
data/sample/
├── businesses.ndjson    # 100 businesses
├── users.ndjson         # 500 users
└── reviews.ndjson       # 1,000 reviews
```

---

## Part 1: Data Model

### Source Dataset

**Yelp Academic Dataset:** https://www.yelp.com/dataset

Files used:
- `yelp_academic_dataset_business.json` (150K+ businesses)
- `yelp_academic_dataset_user.json` (2M+ users)
- `yelp_academic_dataset_review.json` (7M+ reviews)

### Elasticsearch Index Mappings

#### Index: `businesses`

```json
{
  "mappings": {
    "properties": {
      "business_id": { "type": "keyword" },
      "name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
      "address": { "type": "text" },
      "city": { "type": "keyword" },
      "state": { "type": "keyword" },
      "postal_code": { "type": "keyword" },
      "latitude": { "type": "float" },
      "longitude": { "type": "float" },
      "stars": { "type": "float" },
      "review_count": { "type": "integer" },
      "is_open": { "type": "boolean" },
      "categories": { "type": "keyword" },
      "hours": { "type": "object", "enabled": false },
      "attributes": { "type": "flattened" },
      "current_rating": { "type": "float" },
      "rating_protected": { "type": "boolean" },
      "protection_reason": { "type": "keyword" },
      "protected_since": { "type": "date" }
    }
  }
}
```

#### Index: `users`

```json
{
  "mappings": {
    "properties": {
      "user_id": { "type": "keyword" },
      "name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
      "review_count": { "type": "integer" },
      "yelping_since": { "type": "date" },
      "friends": { "type": "keyword" },
      "useful": { "type": "integer" },
      "funny": { "type": "integer" },
      "cool": { "type": "integer" },
      "fans": { "type": "integer" },
      "elite": { "type": "keyword" },
      "average_stars": { "type": "float" },
      "compliment_hot": { "type": "integer" },
      "compliment_more": { "type": "integer" },
      "compliment_profile": { "type": "integer" },
      "compliment_cute": { "type": "integer" },
      "compliment_list": { "type": "integer" },
      "compliment_note": { "type": "integer" },
      "compliment_plain": { "type": "integer" },
      "compliment_cool": { "type": "integer" },
      "compliment_funny": { "type": "integer" },
      "compliment_writer": { "type": "integer" },
      "compliment_photos": { "type": "integer" },
      "trust_score": { "type": "float" },
      "account_age_days": { "type": "integer" },
      "flagged": { "type": "boolean" },
      "flag_reason": { "type": "keyword" },
      "synthetic": { "type": "boolean" }
    }
  }
}
```

#### Index: `reviews`

```json
{
  "mappings": {
    "properties": {
      "review_id": { "type": "keyword" },
      "user_id": { "type": "keyword" },
      "business_id": { "type": "keyword" },
      "stars": { "type": "float" },
      "date": { "type": "date" },
      "text": {
        "type": "text",
        "fields": {
          "semantic": { "type": "semantic_text", "inference_id": "elser" }
        }
      },
      "useful": { "type": "integer" },
      "funny": { "type": "integer" },
      "cool": { "type": "integer" },
      "sentiment_score": { "type": "float" },
      "status": { "type": "keyword" },
      "held_reason": { "type": "keyword" },
      "held_at": { "type": "date" },
      "reviewed_by": { "type": "keyword" },
      "reviewed_at": { "type": "date" },
      "incident_id": { "type": "keyword" },
      "partition": { "type": "keyword" },
      "synthetic": { "type": "boolean" },
      "submitted_by": { "type": "keyword" }
    }
  }
}
```

**Status field values:**
- `pending` - Newly submitted, awaiting processing
- `published` - Approved and visible
- `held` - Held for investigation
- `deleted` - Removed (confirmed attack)

**Partition field values:**
- `historical` - Pre-loaded reviews
- `streaming` - Real-time replay
- `attack` - Participant-submitted attack reviews

#### Index: `incidents`

```json
{
  "mappings": {
    "properties": {
      "incident_id": { "type": "keyword" },
      "business_id": { "type": "keyword" },
      "business_name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
      "detected_at": { "type": "date" },
      "incident_type": { "type": "keyword" },
      "severity": { "type": "keyword" },
      "status": { "type": "keyword" },
      "review_count": { "type": "integer" },
      "unique_reviewers": { "type": "integer" },
      "avg_rating": { "type": "float" },
      "avg_trust_score": { "type": "float" },
      "time_window_minutes": { "type": "integer" },
      "held_review_ids": { "type": "keyword" },
      "flagged_user_ids": { "type": "keyword" },
      "summary": { "type": "text" },
      "assigned_to": { "type": "keyword" },
      "resolved_at": { "type": "date" },
      "resolution": { "type": "keyword" },
      "notes": { "type": "text" }
    }
  }
}
```

#### Index: `notifications`

**Note on Slack Integration:** The workflow definitions support Slack notifications and could be configured with a Slack webhook URL in production environments. However, Slack is not available in the Instruqt workshop environment, so we use an Elasticsearch-based notification log instead. The UI displays these notifications, providing the same visibility without external dependencies.

Elasticsearch-based notification log:

```json
{
  "mappings": {
    "properties": {
      "notification_id": { "type": "keyword" },
      "type": { "type": "keyword" },
      "severity": { "type": "keyword" },
      "title": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
      "message": { "type": "text" },
      "incident_id": { "type": "keyword" },
      "business_id": { "type": "keyword" },
      "business_name": { "type": "keyword" },
      "workflow_id": { "type": "keyword" },
      "created_at": { "type": "date" },
      "read": { "type": "boolean" },
      "read_at": { "type": "date" }
    }
  }
}
```

**Notification types:**
- `review_bomb_detected` - Workflow detected an attack
- `reviews_held` - Reviews placed on hold
- `business_protected` - Rating protection enabled
- `incident_created` - New incident record
- `incident_resolved` - Incident closed
- `user_flagged` - Suspicious user flagged

### Trust Score Calculation

Calculate during user ingestion:

```python
trust_score = (
  (min(review_count, 100) / 100 * 0.25) +
  (min(useful, 100) / 100 * 0.15) +
  (min(fans, 50) / 50 * 0.10) +
  (len(elite) * 0.05) +
  (min(account_age_days, 1825) / 1825 * 0.25) +
  (1 - abs(average_stars - 3.5) / 3.5 * 0.20)
)
```

Normalize to 0.0 - 1.0 range. Higher scores indicate more trustworthy reviewers.

---

## Part 2: Pre-Workshop Admin Setup

This section documents what happens before participants join the workshop environment.

### Data Preparation Pipeline

All scripts support:
- `--dry-run` flag for validation without changes
- Progress logging for long-running operations
- Idempotent execution (safe to run multiple times)

#### Step 1: Filter Businesses

Filter to specific cities and categories for focused demo.

**Recommended cities** (well-represented in Yelp data):
- Las Vegas, NV
- Phoenix, AZ
- Toronto, ON

**Recommended categories:**
- Restaurants
- Food
- Bars
- Cafes

**Script:** `admin/filter_businesses.py`
```bash
python admin/filter_businesses.py \
  --input data/raw/yelp_academic_dataset_business.json \
  --output data/processed/businesses.ndjson \
  --cities "Las Vegas,Phoenix,Toronto" \
  --categories "Restaurants,Food,Bars,Cafes" \
  --limit 20000 \
  --dry-run
```

#### Step 2: Filter Users

Extract users who have reviewed the filtered businesses.

**Script:** `admin/filter_users.py`
```bash
python admin/filter_users.py \
  --users data/raw/yelp_academic_dataset_user.json \
  --businesses data/processed/businesses.ndjson \
  --output data/processed/users-raw.ndjson
```

#### Step 3: Calculate Trust Scores

Add trust_score field to all users.

**Script:** `admin/calculate_trust_scores.py`
```bash
python admin/calculate_trust_scores.py \
  --input data/processed/users-raw.ndjson \
  --output data/processed/users.ndjson
```

#### Step 4: Partition Reviews

Split reviews into historical and streaming sets.

**Script:** `admin/partition_reviews.py`
```bash
python admin/partition_reviews.py \
  --reviews data/raw/yelp_academic_dataset_review.json \
  --businesses data/processed/businesses.ndjson \
  --historical-output data/historical/reviews.ndjson \
  --streaming-output data/streaming/reviews.ndjson \
  --historical-ratio 0.8
```

#### Step 5: Create Indices

**Script:** `admin/create_indices.py`
```bash
python admin/create_indices.py \
  --mappings-dir mappings/ \
  --dry-run
```

#### Step 6: Load Historical Data

**Script:** `admin/load_data.py`
```bash
python admin/load_data.py \
  --businesses data/processed/businesses.ndjson \
  --users data/processed/users.ndjson \
  --reviews data/historical/reviews.ndjson \
  --batch-size 5000
```

#### Step 7: Verify Environment

**Script:** `admin/verify_environment.py`
```bash
python admin/verify_environment.py
```

### Master Setup Script

**Script:** `admin/prepare_data.sh`
```bash
#!/bin/bash
set -e

echo "=== Review Bomb Workshop Data Preparation ==="

# Run all steps
python admin/filter_businesses.py --input data/raw/yelp_academic_dataset_business.json --output data/processed/businesses.ndjson
python admin/filter_users.py --users data/raw/yelp_academic_dataset_user.json --businesses data/processed/businesses.ndjson --output data/processed/users-raw.ndjson
python admin/calculate_trust_scores.py --input data/processed/users-raw.ndjson --output data/processed/users.ndjson
python admin/partition_reviews.py --reviews data/raw/yelp_academic_dataset_review.json --businesses data/processed/businesses.ndjson --historical-output data/historical/reviews.ndjson --streaming-output data/streaming/reviews.ndjson
python admin/create_indices.py --mappings-dir mappings/
python admin/load_data.py --businesses data/processed/businesses.ndjson --users data/processed/users.ndjson --reviews data/historical/reviews.ndjson
python admin/verify_environment.py

echo "=== Setup Complete ==="
```

### Verification Checklist

Before workshop begins, confirm:

- [ ] `businesses` index has 10,000+ documents
- [ ] `users` index has 50,000+ documents
- [ ] `reviews` index has 200,000+ documents (all historical, status="published")
- [ ] Streaming reviews file exists and is not loaded
- [ ] ELSER inference endpoint is available (verify in environment)
- [ ] Web application starts successfully

---

## Part 3: Web Application

### Purpose

Provides an interactive UI for participants to:
1. Browse and select target businesses
2. Generate and customize attack reviews
3. Submit reviews and watch them appear
4. Monitor attack statistics and workflow responses
5. View notifications from automated workflows

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Web UI (FastAPI + Jinja2)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   Business   │  │    Review    │  │   Dashboard / Stats   │  │
│  │   Selector   │  │   Generator  │  │   & Notifications     │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend Services                            │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   Review     │  │  Background  │  │   Attacker Profile    │  │
│  │  Submitter   │  │   Streamer   │  │     Generator         │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
                       Elasticsearch
                    (Cloud or Local)
```

### UI Components

#### 1. Business Selector
- Search box with autocomplete
- Filter by city, category, star rating
- Display: name, city, current rating, review count
- Click to select as attack target

#### 2. Review Generator
- "Generate Random Review" button
- Editable text area with generated content
- Star rating selector (1-5, defaults to 1)
- Auto-generated attacker profile display (name, account age, trust score)
- "Submit Review" button
- Success/error feedback

#### 3. Recent Reviews Feed
- Shows last 10 reviews for selected business
- Real-time updates (polling or WebSocket)
- Highlights participant's own reviews
- Shows review status (pending, published, held)

#### 4. Attack Statistics Panel
- Current rating vs. baseline rating
- Review count in last 30 minutes
- Average trust score of recent reviewers
- Protection status indicator
- Link to any active incidents

#### 5. Notifications Panel
- Bell icon with unread count
- Dropdown showing recent notifications
- Types: attack detected, reviews held, incident created
- Click to view details

### API Endpoints

```
GET  /                           # Main UI page
GET  /api/businesses             # Search businesses
GET  /api/businesses/{id}        # Get business details
GET  /api/businesses/{id}/stats  # Get attack statistics
GET  /api/businesses/{id}/reviews # Get recent reviews
POST /api/reviews                # Submit a review
GET  /api/reviews/generate       # Generate random review text
POST /api/attackers/generate     # Generate attacker profile
GET  /api/notifications          # Get notifications
POST /api/notifications/{id}/read # Mark notification as read
GET  /api/incidents              # List incidents
GET  /api/incidents/{id}         # Get incident details
POST /api/streaming/start        # Start background streaming
POST /api/streaming/stop         # Stop background streaming
GET  /api/streaming/status       # Get streaming status
GET  /health                     # Health check
```

### Review Templates

Random review generator uses templates:

```python
NEGATIVE_REVIEW_TEMPLATES = [
    "Terrible experience. {food_complaint} {service_complaint} Never coming back.",
    "Worst restaurant in town. {health_complaint} Avoid at all costs.",
    "Zero stars if I could. {service_complaint} {cleanliness_complaint}",
    "How is this place still open? {health_complaint}",
    "Used to be good but went downhill fast. {general_complaint}",
    "Completely overrated. {wait_complaint} {food_complaint}",
    "{health_complaint} {legal_threat}",
    "Scam restaurant. {billing_complaint}",
    "{cleanliness_complaint} I wish I was joking. Do not eat here.",
    "{health_complaint} {legal_threat}",
]

FOOD_COMPLAINTS = ["Food was cold and tasteless.", "Got the worst meal of my life.", ...]
SERVICE_COMPLAINTS = ["Service was awful.", "Rude staff ignored us.", ...]
HEALTH_COMPLAINTS = ["Got sick after eating here.", "Food poisoning.", ...]
# ... etc
```

### Attacker Profile Generator

Creates realistic-looking fake accounts:

```python
def generate_attacker_profile():
    return {
        "user_id": f"attack_{uuid4().hex[:12]}",
        "name": fake.name(),
        "review_count": random.randint(0, 3),
        "yelping_since": datetime.now() - timedelta(days=random.randint(1, 30)),
        "account_age_days": random.randint(1, 30),
        "trust_score": random.uniform(0.05, 0.20),
        "useful": 0,
        "funny": 0,
        "cool": 0,
        "fans": 0,
        "elite": [],
        "average_stars": random.uniform(1.0, 2.0),
        "synthetic": True
    }
```

### Background Streaming

The application can run background streaming of normal reviews:

```python
class BackgroundStreamer:
    """Streams held-back real reviews to simulate normal platform activity."""

    def __init__(self, config, es_client):
        self.config = config
        self.es = es_client
        self.running = False
        self.task = None

    async def start(self):
        """Start streaming reviews in background."""
        self.running = True
        self.task = asyncio.create_task(self._stream_loop())

    async def stop(self):
        """Stop streaming."""
        self.running = False
        if self.task:
            await self.task

    async def _stream_loop(self):
        """Main streaming loop."""
        reviews = self._load_streaming_reviews()
        for review in reviews:
            if not self.running:
                break
            await self._submit_review(review)
            await asyncio.sleep(1 / self.config.reviews_per_second)
```

---

## Part 4: Detection Logic

### ES|QL Queries for Review Bomb Detection

#### Query 1: Velocity Detection

Detect abnormal review velocity for a business in the last 30 minutes.

```sql
FROM reviews
| WHERE date > NOW() - 30 minutes
| STATS
    review_count = COUNT(*),
    unique_reviewers = COUNT_DISTINCT(user_id),
    avg_stars = AVG(stars),
    min_stars = MIN(stars),
    max_stars = MAX(stars)
  BY business_id
| WHERE review_count > 10 AND avg_stars < 2.0
| SORT review_count DESC
| LIMIT 20
```

#### Query 2: Reviewer Trust Analysis

Cross-reference reviews with user trust scores using LOOKUP JOIN.

```sql
FROM reviews
| WHERE date > NOW() - 30 minutes AND stars <= 2
| LOOKUP JOIN users ON user_id
| STATS
    review_count = COUNT(*),
    avg_trust_score = AVG(trust_score),
    avg_account_age = AVG(account_age_days),
    low_trust_count = COUNT(CASE WHEN trust_score < 0.3 THEN 1 END)
  BY business_id
| WHERE review_count > 5 AND avg_trust_score < 0.4
| SORT low_trust_count DESC
```

#### Query 3: Combined Risk Score

```sql
FROM reviews
| WHERE date > NOW() - 30 minutes
| LOOKUP JOIN users ON user_id
| LOOKUP JOIN businesses ON business_id
| STATS
    review_count = COUNT(*),
    avg_stars = AVG(stars),
    avg_trust = AVG(trust_score),
    new_account_pct = AVG(CASE WHEN account_age_days < 30 THEN 1.0 ELSE 0.0 END),
    low_review_pct = AVG(CASE WHEN users.review_count < 5 THEN 1.0 ELSE 0.0 END)
  BY business_id, businesses.name
| EVAL risk_score = (
    (CASE WHEN review_count > 20 THEN 0.3 WHEN review_count > 10 THEN 0.2 ELSE 0.1 END) +
    (CASE WHEN avg_stars < 1.5 THEN 0.3 WHEN avg_stars < 2.5 THEN 0.2 ELSE 0.0 END) +
    (CASE WHEN avg_trust < 0.3 THEN 0.2 WHEN avg_trust < 0.5 THEN 0.1 ELSE 0.0 END) +
    (new_account_pct * 0.2)
  )
| WHERE risk_score > 0.5
| SORT risk_score DESC
| LIMIT 10
```

---

## Part 5: Workflow Definitions

> **Note on YAML Syntax:** The workflow definitions below follow the Elastic Workflows YAML specification. Key syntax elements:
> - `type:` specifies the step type (e.g., `elasticsearch.search`, `slack`, `if`)
> - `connectorId:` references configured connectors for external services
> - `with:` contains step parameters
> - `{{}}` syntax for variable interpolation (Nunjucks-based templating)

### Notification Strategy

**Production environments** can use Slack notifications by configuring:
```yaml
- name: notify-slack
  type: slack
  connectorId: "slack-trust-safety"
  with:
    channel: "#trust-safety-alerts"
    message: "Review bomb detected..."
```

**Workshop environments (Instruqt)** use Elasticsearch notifications instead, since Slack webhooks are not available. The web UI displays these notifications with the same information.

### Workflow 1: Review Bomb Detection and Response

```yaml
version: 1
name: "Review Bomb Detection"
description: "Detect and respond to review bombing attacks"
enabled: true
tags: ["trust-safety", "detection", "automation"]

triggers:
  - type: schedule
    interval: "5m"

steps:
  - name: detect-anomaly
    type: elasticsearch.search
    with:
      index: "reviews"
      query:
        bool:
          filter:
            - range:
                date:
                  gte: "now-30m"
      aggs:
        by_business:
          terms:
            field: "business_id"
            size: 20
          aggs:
            review_count:
              value_count:
                field: "review_id"
            avg_stars:
              avg:
                field: "stars"

  - name: enrich-with-trust-scores
    type: foreach
    foreach: "{{ steps.detect-anomaly.output.aggregations.by_business.buckets }}"
    steps:
      - name: get-reviewer-trust
        type: elasticsearch.search
        with:
          index: "reviews,users"
          query:
            bool:
              must:
                - term:
                    business_id: "{{ foreach.item.key }}"
                - range:
                    date:
                      gte: "now-30m"

  - name: check-threshold
    type: if
    condition: "steps.detect-anomaly.output.aggregations.by_business.buckets.length > 0"
    steps:
      - name: process-each-anomaly
        type: foreach
        foreach: "{{ steps.detect-anomaly.output.aggregations.by_business.buckets | selectattr('review_count.value', '>', 10) }}"
        steps:
          - name: get-business-info
            type: elasticsearch.search
            with:
              index: "businesses"
              query:
                term:
                  business_id: "{{ foreach.item.key }}"

          - name: create-incident
            type: elasticsearch.index
            with:
              index: "incidents"
              document:
                incident_id: "INC-{{ execution.id | truncate(12, '') }}"
                business_id: "{{ foreach.item.key }}"
                business_name: "{{ steps.get-business-info.output.hits.hits[0]._source.name }}"
                detected_at: "{{ execution.startedAt }}"
                incident_type: "review_bomb"
                severity: "{{ 'critical' if foreach.item.review_count.value > 20 else 'high' }}"
                status: "open"
                review_count: "{{ foreach.item.review_count.value }}"
                avg_rating: "{{ foreach.item.avg_stars.value }}"

          - name: hold-reviews
            type: elasticsearch.request
            with:
              method: POST
              path: "/reviews/_update_by_query"
              body:
                query:
                  bool:
                    must:
                      - term:
                          business_id: "{{ foreach.item.key }}"
                      - range:
                          date:
                            gte: "now-30m"
                      - terms:
                          status: ["pending", "published"]
                script:
                  source: "ctx._source.status = 'held'; ctx._source.held_reason = 'review_bomb_suspected'; ctx._source.held_at = params.now"
                  params:
                    now: "{{ execution.startedAt }}"

          - name: protect-business
            type: elasticsearch.update
            with:
              index: "businesses"
              id: "{{ foreach.item.key }}"
              doc:
                rating_protected: true
                protection_reason: "review_bomb_investigation"
                protected_since: "{{ execution.startedAt }}"

          - name: create-notification
            type: elasticsearch.index
            with:
              index: "notifications"
              document:
                notification_id: "{{ execution.id }}-notify"
                type: "review_bomb_detected"
                severity: "{{ 'critical' if foreach.item.review_count.value > 20 else 'high' }}"
                title: "Review Bomb Detected"
                message: "Detected {{ foreach.item.review_count.value }} suspicious reviews for {{ steps.get-business-info.output.hits.hits[0]._source.name }} in the last 30 minutes."
                business_id: "{{ foreach.item.key }}"
                business_name: "{{ steps.get-business-info.output.hits.hits[0]._source.name }}"
                workflow_id: "review-bomb-detection"
                created_at: "{{ execution.startedAt }}"
                read: false
```

### Workflow 2: Reviewer Flagging

```yaml
version: 1
name: "Flag Suspicious Reviewers"
description: "Flag users involved in coordinated attacks"
enabled: true
tags: ["trust-safety", "user-management"]

triggers:
  - type: document
    index: incidents
    filters:
      - field: incident_type
        value: "review_bomb"
      - field: status
        value: "open"

steps:
  - name: get-incident-reviews
    type: elasticsearch.search
    with:
      index: "reviews"
      query:
        term:
          incident_id: "{{ trigger.document.incident_id }}"

  - name: get-reviewer-details
    type: foreach
    foreach: "{{ steps.get-incident-reviews.output.hits.hits }}"
    steps:
      - name: lookup-user
        type: elasticsearch.search
        with:
          index: "users"
          query:
            term:
              user_id: "{{ foreach.item._source.user_id }}"

      - name: check-if-suspicious
        type: if
        condition: "steps.lookup-user.output.hits.hits[0]._source.trust_score < 0.3 or steps.lookup-user.output.hits.hits[0]._source.account_age_days < 30"
        steps:
          - name: flag-user
            type: elasticsearch.update
            with:
              index: "users"
              id: "{{ foreach.item._source.user_id }}"
              doc:
                flagged: true
                flag_reason: "coordinated_attack_participant"
                flagged_at: "{{ execution.startedAt }}"
                related_incident: "{{ trigger.document.incident_id }}"

  - name: update-incident-with-flagged-users
    type: elasticsearch.update
    with:
      index: "incidents"
      id: "{{ trigger.document._id }}"
      doc:
        flagged_user_count: "{{ steps.get-incident-reviews.output.hits.total.value }}"
        last_updated: "{{ execution.startedAt }}"

  - name: create-notification
    type: elasticsearch.index
    with:
      index: "notifications"
      document:
        notification_id: "{{ execution.id }}-flag-notify"
        type: "users_flagged"
        severity: "info"
        title: "Suspicious Users Flagged"
        message: "Users have been flagged for participating in coordinated attack (Incident: {{ trigger.document.incident_id }})"
        incident_id: "{{ trigger.document.incident_id }}"
        workflow_id: "flag-suspicious-reviewers"
        created_at: "{{ execution.startedAt }}"
        read: false
```

### Workflow 3: Incident Resolution

```yaml
version: 1
name: "Resolve Incident"
description: "Handle incident resolution and restore business rating"
enabled: true
tags: ["trust-safety", "incident-response"]

triggers:
  - type: document
    index: incidents
    filters:
      - field: status
        value: "resolved"

steps:
  - name: get-incident-details
    type: elasticsearch.search
    with:
      index: "incidents"
      query:
        term:
          incident_id: "{{ trigger.document.incident_id }}"

  - name: check-resolution-type
    type: if
    condition: "steps.get-incident-details.output.hits.hits[0]._source.resolution == 'confirmed_attack'"
    steps:
      # If confirmed attack, delete the held reviews
      - name: delete-attack-reviews
        type: elasticsearch.request
        with:
          method: POST
          path: "/reviews/_update_by_query"
          body:
            query:
              bool:
                must:
                  - term:
                      incident_id: "{{ trigger.document.incident_id }}"
                  - term:
                      status: "held"
            script:
              source: "ctx._source.status = 'deleted'; ctx._source.reviewed_at = params.now"
              params:
                now: "{{ execution.startedAt }}"
    else:
      # If false positive, release the held reviews
      - name: release-held-reviews
        type: elasticsearch.request
        with:
          method: POST
          path: "/reviews/_update_by_query"
          body:
            query:
              bool:
                must:
                  - term:
                      incident_id: "{{ trigger.document.incident_id }}"
                  - term:
                      status: "held"
            script:
              source: "ctx._source.status = 'published'; ctx._source.reviewed_at = params.now"
              params:
                now: "{{ execution.startedAt }}"

  - name: restore-business-rating
    type: elasticsearch.update
    with:
      index: "businesses"
      id: "{{ steps.get-incident-details.output.hits.hits[0]._source.business_id }}"
      doc:
        rating_protected: false
        protection_reason: null
        protected_since: null

  - name: create-resolution-notification
    type: elasticsearch.index
    with:
      index: "notifications"
      document:
        notification_id: "{{ execution.id }}-resolve-notify"
        type: "incident_resolved"
        severity: "info"
        title: "Incident Resolved"
        message: "Incident {{ trigger.document.incident_id }} has been resolved ({{ steps.get-incident-details.output.hits.hits[0]._source.resolution }}). Reviews processed and business rating protection removed."
        incident_id: "{{ trigger.document.incident_id }}"
        business_id: "{{ steps.get-incident-details.output.hits.hits[0]._source.business_id }}"
        workflow_id: "resolve-incident"
        created_at: "{{ execution.startedAt }}"
        read: false
```

---

## Part 6: Agent Builder Tools

### Tool 1: Incident Summary

```json
{
  "name": "incident_summary",
  "description": "Summarize a review bomb incident including affected business, review patterns, and current status",
  "parameters": {
    "incident_id": {
      "type": "string",
      "description": "The incident ID to summarize (e.g., INC-abc123)"
    }
  },
  "esql": "FROM incidents | WHERE incident_id == \"{{ incident_id }}\" | LOOKUP JOIN businesses ON business_id | KEEP incident_id, business_name, detected_at, severity, status, review_count, avg_rating, avg_trust_score, resolution"
}
```

### Tool 2: Reviewer Pattern Analysis

```json
{
  "name": "reviewer_pattern_analysis",
  "description": "Analyze patterns among reviewers involved in an incident to identify coordination signals",
  "parameters": {
    "incident_id": {
      "type": "string",
      "description": "The incident ID to analyze"
    }
  },
  "esql": "FROM reviews | WHERE incident_id == \"{{ incident_id }}\" | LOOKUP JOIN users ON user_id | STATS reviewer_count = COUNT_DISTINCT(user_id), avg_account_age = AVG(account_age_days), avg_trust_score = AVG(trust_score), avg_review_count = AVG(users.review_count), accounts_under_30_days = COUNT(CASE WHEN account_age_days < 30 THEN 1 END), accounts_under_5_reviews = COUNT(CASE WHEN users.review_count < 5 THEN 1 END)"
}
```

### Tool 3: Business Risk Assessment

```json
{
  "name": "business_risk_assessment",
  "description": "Assess a business's current risk profile for review manipulation based on recent activity",
  "parameters": {
    "business_id": {
      "type": "string",
      "description": "Business ID to assess"
    }
  },
  "esql": "FROM reviews | WHERE business_id == \"{{ business_id }}\" AND date > NOW() - 7 days | LOOKUP JOIN users ON user_id | STATS total_reviews = COUNT(*), avg_rating = AVG(stars), low_trust_reviews = COUNT(CASE WHEN trust_score < 0.3 THEN 1 END), new_account_reviews = COUNT(CASE WHEN account_age_days < 30 THEN 1 END), negative_reviews = COUNT(CASE WHEN stars <= 2 THEN 1 END) | EVAL low_trust_pct = low_trust_reviews * 100.0 / total_reviews, new_account_pct = new_account_reviews * 100.0 / total_reviews, negative_pct = negative_reviews * 100.0 / total_reviews"
}
```

### Tool 4: Recent Incidents

```json
{
  "name": "recent_incidents",
  "description": "List recent review bomb incidents, optionally filtered by status",
  "parameters": {
    "status": {
      "type": "string",
      "description": "Filter by status: open, resolved, or all",
      "default": "all"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of incidents to return",
      "default": 10
    }
  },
  "esql": "FROM incidents | WHERE status == \"{{ status }}\" OR \"{{ status }}\" == \"all\" | SORT detected_at DESC | LIMIT {{ limit }} | KEEP incident_id, business_name, detected_at, severity, status, review_count"
}
```

---

## Part 7: Instruqt Workshop Challenges

### Challenge 1: Getting to Know Your Data

**Time:** 15 minutes

**Objective:** Explore the pre-loaded review platform data, understand the schema, and write detection queries using ES|QL and LOOKUP JOIN.

**Tabs:**
- Kibana (Dev Tools, Discover)
- Instructions

**Instructions:**

Welcome to the Trust & Safety team at a review platform! Your environment is pre-loaded with real business and review data. Your job is to understand the data and build detection logic for review bombing attacks.

**Task 1: Explore the Data**

Navigate to Kibana Discover and explore each index:

```sql
-- How many businesses?
FROM businesses | STATS count = COUNT(*)

-- What cities are represented?
FROM businesses | STATS count = COUNT(*) BY city | SORT count DESC

-- Average trust score across users?
FROM users | STATS avg_trust = AVG(trust_score), min_trust = MIN(trust_score), max_trust = MAX(trust_score)

-- Reviews in last 24 hours?
FROM reviews | WHERE date > NOW() - 24 hours | STATS count = COUNT(*)
```

**Task 2: Understand Trust Scores**

Explore how trust scores correlate with user behavior:

```sql
FROM users
| STATS
    user_count = COUNT(*),
    avg_reviews = AVG(review_count),
    avg_account_age = AVG(account_age_days)
  BY trust_bucket = CASE
    WHEN trust_score < 0.3 THEN "low"
    WHEN trust_score < 0.7 THEN "medium"
    ELSE "high"
  END
| SORT trust_bucket
```

**Task 3: Build a Detection Query**

Write an ES|QL query that detects potential review bombs. Complete this query:

```sql
FROM reviews
| WHERE date > NOW() - 30 minutes
| LOOKUP JOIN users ON user_id
| STATS
    review_count = COUNT(*),
    avg_stars = AVG(stars),
    avg_trust = AVG(trust_score)
  BY business_id
| WHERE review_count > ___ AND avg_trust < ___
| SORT review_count DESC
```

**Task 4: Test with Real Data**

Find a well-rated business that could be a target:

```sql
FROM businesses
| WHERE categories LIKE "*Restaurant*" AND stars >= 4.0
| SORT review_count DESC
| LIMIT 10
| KEEP business_id, name, city, stars, review_count
```

**Verification:**
- [ ] Can query document counts for each index
- [ ] Understands trust score distribution
- [ ] Completed the detection query with appropriate thresholds
- [ ] Identified potential target businesses

---

### Challenge 2: Workflows

**Time:** 20 minutes

**Objective:** Build a workflow that automatically detects review bombs and protects affected businesses.

**Tabs:**
- Kibana (Workflows UI)
- Instructions

**Instructions:**

Now that you can detect review bombs with ES|QL, let's automate the response. When an attack is detected, the workflow should:
1. Hold suspicious reviews
2. Protect the business rating
3. Create an incident record
4. Log a notification

**Task 1: Create a New Workflow**

1. Navigate to the Workflows app in Kibana
2. Click "Create workflow" to open the YAML editor
3. Copy the provided workflow YAML (see Challenge 2 assignment for full YAML)

**Task 2: Understand the Workflow Structure**

The workflow YAML contains:
- **Trigger:** Schedule (every 5 minutes)
- **Detection Query:** ES|QL with LOOKUP JOIN from Challenge 1
- **For Each Loop:** Process each detected attack
- **Response Actions:** Hold reviews, protect business, create incident, notify

Example detection query within the workflow:
```sql
FROM reviews
| WHERE date > NOW() - 30 minutes
| LOOKUP JOIN users ON user_id
| STATS
    review_count = COUNT(*),
    avg_stars = AVG(stars),
    avg_trust = AVG(trust_score)
  BY business_id
| WHERE review_count > 10 AND avg_stars < 2.0 AND avg_trust < 0.4
| SORT review_count DESC
| LIMIT 5
```

**Task 3: Understand Response Steps**

The workflow includes these response actions for each detected business:

1. **Hold Reviews** - Update suspicious reviews: `status = "held"`
2. **Protect Business** - Update business: `rating_protected = true`
3. **Create Incident** - Index a document to the `incidents` index
4. **Create Notification** - Index to `notifications` index

**Task 4: Review Conditional Logic**

The workflow includes severity classification:
- `critical`: review_count > 20
- `high`: review_count > 10
- `medium`: review_count >= 5

**Task 5: Save and Enable**

1. Enable the workflow using the toggle
2. Click Save
3. Use the Play/Run button to test immediately

**Verification:**
- [ ] Workflow YAML pasted into editor
- [ ] Workflow enabled and saved
- [ ] Test run completes without errors
- [ ] You understand trigger, detection, and response sections

---

### Challenge 3: Agent Builder

**Time:** 10 minutes

**Objective:** Create Agent Builder tools that help analysts investigate incidents using natural language.

**Tabs:**
- Kibana (Agent Builder)
- Instructions

**Instructions:**

When a workflow detects an attack, an analyst needs to investigate. Agent Builder lets you create tools that answer natural language questions using your data.

**Task 1: Create Incident Summary Tool**

Create a tool that summarizes an incident:

1. Select **Type:** ES|QL
2. Enter the ES|QL query with `{{incident_id}}` parameter placeholder
3. In **ES|QL Parameters**, add: `incident_id` (type: `text`, required)
4. Set **Tool ID:** `incident_summary`
5. Set **Description:** Summarize a review bomb incident

**ES|QL Query:**
```sql
FROM incidents
| WHERE incident_id == "{{incident_id}}"
| LOOKUP JOIN businesses ON business_id
| KEEP incident_id, business_name, detected_at, severity, status, review_count, avg_rating
```

**Task 2: Create Reviewer Analysis Tool**

Create a tool that analyzes attackers:

1. Select **Type:** ES|QL
2. Enter the ES|QL query with `{{business_id}}` parameter placeholder
3. In **ES|QL Parameters**, add: `business_id` (type: `text`, required)
4. Set **Tool ID:** `reviewer_analysis`
5. Set **Description:** Analyze reviewers involved in an attack

**ES|QL Query:**
```sql
FROM reviews
| WHERE business_id == "{{business_id}}"
| WHERE @timestamp > NOW() - 24 hours
| LOOKUP JOIN users ON user_id
| STATS
    reviewer_count = COUNT_DISTINCT(user_id),
    avg_account_age = AVG(account_age_days),
    avg_trust_score = AVG(trust_score),
    new_accounts = COUNT(CASE WHEN account_age_days < 30 THEN 1 END)
```

**Task 3: Test the Agent**

Open the Agent chat and test:

1. "What incidents were detected recently?"
2. "Summarize incident INC-001"
3. "Analyze the reviewers in that incident. Does this look coordinated?"

**Verification:**
- [ ] incident_summary tool created and working
- [ ] reviewer_analysis tool created and working
- [ ] Agent responds to natural language queries

---

### Challenge 4: End-to-End Scenario

**Time:** 15 minutes

**Objective:** Launch a review bomb attack using the web UI and observe the full detection, response, and investigation lifecycle.

**Tabs:**
- Web Application (Attack UI)
- Kibana (Discover, Workflows, Agent)
- Instructions

**Instructions:**

Time to put it all together. You'll launch an attack and watch your defenses respond.

**Task 1: Check Baseline State**

Open the Web Application and select a target business. Note:
- Current star rating
- Review count
- Rating protection status (should be `false`)

**Task 2: Launch Your Attack**

Using the Attack UI:

1. Select your target business
2. Click "Generate Random Review" to create attack content
3. Optionally edit the review to include something unique (so you can find it later!)
4. Click "Submit Review"
5. Repeat 10-15 times rapidly

Watch the "Recent Reviews" panel - you should see your reviews appear with status "pending".

**Task 3: Observe Workflow Execution**

Within 5 minutes (or trigger manually), your workflow should execute. Watch for:
- Reviews changing status to "held"
- Business `rating_protected` = true
- New incident in `incidents` index
- Notification appearing in the UI

Verify in Kibana:

```sql
FROM reviews
| WHERE business_id == "YOUR_BUSINESS_ID"
| WHERE date > NOW() - 10 minutes
| STATS count = COUNT(*) BY status
```

**Task 4: Investigate with Agent Builder**

Open the Agent and investigate:

1. "What incidents were detected in the last hour?"
2. "Summarize the most recent incident"
3. "Analyze the reviewers. Is this a coordinated attack?"

**Task 5: Resolve the Incident**

Mark the incident as resolved with resolution = "confirmed_attack". Observe:
- Attack reviews marked as "deleted"
- Business rating protection removed
- Resolution notification created

**Discussion Questions:**
- How quickly did the workflow detect your attack?
- What signals were most useful for detection?
- How would you tune thresholds for different scenarios?
- What additional response actions would be valuable?

**Verification:**
- [ ] Successfully submitted attack reviews via UI
- [ ] Workflow triggered automatically
- [ ] Reviews held, business protected, incident created
- [ ] Investigated with Agent Builder
- [ ] Resolved incident successfully

---

## Part 8: File Manifest

### Repository Structure

```
review-bomb-workshop/
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── Makefile
├── .env.example
├── .gitignore
│
├── config/
│   └── config.yaml
│
├── app/                               # FastAPI Web Application
│   ├── __init__.py
│   ├── main.py                        # FastAPI app entry point
│   ├── config.py                      # Configuration loading
│   ├── dependencies.py                # Dependency injection
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── businesses.py              # Business search/details API
│   │   ├── reviews.py                 # Review submission API
│   │   ├── incidents.py               # Incident management API
│   │   ├── notifications.py           # Notifications API
│   │   └── streaming.py               # Background streaming control
│   ├── services/
│   │   ├── __init__.py
│   │   ├── elasticsearch.py           # ES client wrapper
│   │   ├── review_generator.py        # Random review generation
│   │   ├── attacker_generator.py      # Fake profile generation
│   │   └── background_streamer.py     # Background streaming service
│   ├── models/
│   │   ├── __init__.py
│   │   ├── business.py
│   │   ├── review.py
│   │   ├── incident.py
│   │   ├── notification.py
│   │   └── user.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html                 # Main attack UI
│   │   └── components/
│   │       ├── business_selector.html
│   │       ├── review_form.html
│   │       ├── recent_reviews.html
│   │       ├── attack_stats.html
│   │       └── notifications.html
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── app.js
│
├── admin/                             # Pre-workshop setup scripts
│   ├── __init__.py
│   ├── prepare_data.sh                # Master setup script
│   ├── filter_businesses.py
│   ├── filter_users.py
│   ├── calculate_trust_scores.py
│   ├── partition_reviews.py
│   ├── create_indices.py
│   ├── load_data.py
│   ├── verify_environment.py
│   └── utils/
│       ├── __init__.py
│       ├── elasticsearch.py           # Shared ES utilities
│       ├── progress.py                # Progress logging
│       └── cli.py                     # CLI argument helpers
│
├── data/
│   ├── raw/                           # Yelp dataset (gitignored)
│   │   ├── yelp_academic_dataset_business.json
│   │   ├── yelp_academic_dataset_user.json
│   │   └── yelp_academic_dataset_review.json
│   ├── processed/                     # Filtered data (gitignored)
│   ├── historical/                    # Pre-loaded reviews (gitignored)
│   ├── streaming/                     # Held-back reviews (gitignored)
│   └── sample/                        # Small sample for dev (committed)
│       ├── businesses.ndjson
│       ├── users.ndjson
│       └── reviews.ndjson
│
├── mappings/                          # Elasticsearch index mappings
│   ├── businesses.json
│   ├── users.json
│   ├── reviews.json
│   ├── incidents.json
│   └── notifications.json
│
├── queries/                           # ES|QL queries
│   ├── detection/
│   │   ├── velocity_detection.esql
│   │   ├── trust_correlation.esql
│   │   └── combined_risk_score.esql
│   └── investigation/
│       ├── incident_summary.esql
│       └── reviewer_analysis.esql
│
├── workflows/                         # Workflow definitions
│   ├── review_bomb_detection.yaml
│   ├── reviewer_flagging.yaml
│   └── incident_resolution.yaml
│
├── agent-tools/                       # Agent Builder tool definitions
│   ├── incident_summary.json
│   ├── reviewer_pattern_analysis.json
│   ├── business_risk_assessment.json
│   └── recent_incidents.json
│
├── instruqt/                          # Workshop challenges
│   └── challenges/
│       ├── 01-getting-to-know-your-data/
│       │   ├── assignment.md
│       │   ├── setup.sh
│       │   └── check.sh
│       ├── 02-workflows/
│       │   ├── assignment.md
│       │   ├── setup.sh
│       │   └── check.sh
│       ├── 03-agent-builder/
│       │   ├── assignment.md
│       │   ├── setup.sh
│       │   └── check.sh
│       └── 04-end-to-end-scenario/
│           ├── assignment.md
│           ├── setup.sh
│           └── check.sh
│
├── presentation/
│   ├── slides.md
│   └── images/
│
└── docs/
    ├── admin-setup-guide.md
    └── troubleshooting.md
```

### Makefile

```makefile
.PHONY: setup install prepare-data load-data run dev clean verify help

help:
	@echo "Review Bomb Workshop - Available Commands"
	@echo "=========================================="
	@echo "setup          - Create venv and install dependencies"
	@echo "install        - Install dependencies only"
	@echo "prepare-data   - Run full data preparation pipeline"
	@echo "load-data      - Load data to Elasticsearch"
	@echo "run            - Run the web application"
	@echo "dev            - Run in development mode with reload"
	@echo "verify         - Verify environment is ready"
	@echo "clean          - Remove generated files"
	@echo "docker-build   - Build Docker image"
	@echo "docker-run     - Run in Docker container"

setup:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

install:
	pip install -r requirements.txt

prepare-data:
	./admin/prepare_data.sh

load-data:
	python admin/load_data.py

run:
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

verify:
	python admin/verify_environment.py

clean:
	rm -rf data/processed/* data/historical/* data/streaming/*
	rm -rf __pycache__ */__pycache__ */*/__pycache__

docker-build:
	docker build -t review-bomb-workshop .

docker-run:
	docker run -p 8000:8000 --env-file .env review-bomb-workshop
```

---

## ELSER Verification

The semantic search feature requires ELSER. Availability varies by environment:

### Cloud Serverless
- ELSER should be available as a built-in inference endpoint
- Verify with: `GET _inference/sparse_embedding/elser`

### Instruqt / Local
- May need to deploy ELSER model
- Or use inference endpoint if pre-configured
- Fallback: disable semantic field if ELSER unavailable

### Verification Script

```python
def verify_elser(es_client):
    """Check if ELSER inference is available."""
    try:
        response = es_client.inference.get(inference_id="elser")
        print("✓ ELSER inference endpoint available")
        return True
    except Exception as e:
        print(f"✗ ELSER not available: {e}")
        print("  Semantic search features will be disabled")
        return False
```

---

## Recommended Enhancements

This section documents recommended improvements to make the workshop more robust, flexible, and demo-friendly.

### ELSER Graceful Degradation

Make ELSER/semantic search fully optional to support environments where it may not be available or desired.

**Configuration:**
- Add `ELSER_ENABLED=false` to `.env.example` as the default
- The reviews index mapping should NOT include the `semantic_text` field by default
- Semantic search becomes an opt-in enhancement rather than a requirement

**Separate enablement script:** `admin/enable_semantic_search.py`

This script can be run after initial setup to add semantic capabilities:

```python
#!/usr/bin/env python3
"""
Enable semantic search by adding the semantic_text field to the reviews index.
Run this only after ELSER is verified available in your environment.
"""

import argparse
from elasticsearch import Elasticsearch
from admin.utils.elasticsearch import get_es_client

def enable_semantic_search(es: Elasticsearch, dry_run: bool = False):
    """Add semantic_text field to reviews index mapping."""

    # First verify ELSER is available
    try:
        es.inference.get(inference_id="elser")
        print("✓ ELSER inference endpoint verified")
    except Exception as e:
        print(f"✗ ELSER not available: {e}")
        print("  Cannot enable semantic search without ELSER")
        return False

    # Update mapping to add semantic field
    mapping_update = {
        "properties": {
            "text": {
                "type": "text",
                "fields": {
                    "semantic": {
                        "type": "semantic_text",
                        "inference_id": "elser"
                    }
                }
            }
        }
    }

    if dry_run:
        print("DRY RUN: Would update reviews index mapping:")
        print(mapping_update)
        return True

    es.indices.put_mapping(index="reviews", body=mapping_update)
    print("✓ Semantic search enabled on reviews index")

    # Trigger reindex to populate semantic field
    print("  Note: Existing documents need reindexing to populate semantic field")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    es = get_es_client()
    enable_semantic_search(es, dry_run=args.dry_run)
```

**Benefits:**
- Workshop works out-of-the-box in any environment
- No failures due to missing ELSER
- Semantic features can be enabled when available
- Cleaner separation of concerns

### Turbo Mode for Attack Simulation

Add a "Turbo Attack" button to make demos more dramatic and save time during live presentations.

**Web UI Enhancement:**
- Add a "Turbo Attack" button next to the regular "Submit Review" button
- Submits 15-20 reviews in a single burst (configurable)
- Shows progress indicator during burst submission
- Makes the demo more visually impactful

**Configuration in `config.yaml`:**

```yaml
attack:
  default_stars: 1
  reviewer_trust_range: [0.05, 0.20]
  reviewer_account_age_range: [1, 30]
  turbo_mode:
    enabled: true
    reviews_per_burst: 15
    delay_between_reviews_ms: 200  # Small delay to show progress
    button_label: "Turbo Attack (15 reviews)"
```

**API Endpoint:**

```
POST /api/reviews/burst
{
  "business_id": "abc123",
  "count": 15,
  "stars": 1
}
```

**Benefits:**
- Faster demo execution
- More dramatic visual impact when workflow triggers
- Reduces repetitive clicking during presentations
- Configurable to adjust intensity

### Async Elasticsearch Client

Use `elasticsearch[async]` for the FastAPI web application to improve performance during concurrent attack simulations.

**Implementation:**

```python
# app/services/elasticsearch.py
from elasticsearch import AsyncElasticsearch

async def get_async_es_client() -> AsyncElasticsearch:
    """Get async Elasticsearch client for FastAPI endpoints."""
    return AsyncElasticsearch(
        hosts=[settings.ELASTICSEARCH_URL],
        api_key=settings.ELASTICSEARCH_API_KEY,
        # ... other settings
    )
```

**Usage in routers:**

```python
# app/routers/reviews.py
from fastapi import APIRouter, Depends
from app.services.elasticsearch import get_async_es_client

router = APIRouter()

@router.post("/api/reviews")
async def submit_review(
    review: ReviewSubmission,
    es: AsyncElasticsearch = Depends(get_async_es_client)
):
    await es.index(index="reviews", document=review.dict())
    return {"status": "submitted"}
```

**Guidance:**
- Use `elasticsearch[async]` for FastAPI web application
- Sync client is fine for admin scripts (simpler, no async overhead)
- Add `elasticsearch[async]` to `requirements.txt`

**Benefits:**
- Better performance during burst attack submissions
- Non-blocking I/O for concurrent requests
- More responsive UI during heavy load

### Integration Tests

Add pytest tests for admin scripts and API endpoints to ensure reliability.

**Test structure:**

```
tests/
├── conftest.py              # Shared fixtures
├── test_admin/
│   ├── test_filter_businesses.py
│   ├── test_calculate_trust_scores.py
│   ├── test_create_indices.py
│   └── test_load_data.py
├── test_api/
│   ├── test_businesses.py
│   ├── test_reviews.py
│   ├── test_incidents.py
│   └── test_notifications.py
└── test_services/
    ├── test_review_generator.py
    └── test_attacker_generator.py
```

**Test index prefix:**

```python
# tests/conftest.py
import pytest
from elasticsearch import Elasticsearch

TEST_INDEX_PREFIX = "test-"

@pytest.fixture
def test_indices():
    """Return test index names to avoid polluting real data."""
    return {
        "businesses": f"{TEST_INDEX_PREFIX}businesses",
        "users": f"{TEST_INDEX_PREFIX}users",
        "reviews": f"{TEST_INDEX_PREFIX}reviews",
        "incidents": f"{TEST_INDEX_PREFIX}incidents",
        "notifications": f"{TEST_INDEX_PREFIX}notifications",
    }

@pytest.fixture(autouse=True)
def cleanup_test_indices(es_client, test_indices):
    """Clean up test indices after each test."""
    yield
    for index in test_indices.values():
        es_client.indices.delete(index=index, ignore=[404])
```

**Makefile targets:**

```makefile
.PHONY: test test-admin test-api test-coverage

test:
	pytest tests/ -v

test-admin:
	pytest tests/test_admin/ -v

test-api:
	pytest tests/test_api/ -v

test-coverage:
	pytest tests/ --cov=app --cov=admin --cov-report=html
```

**Benefits:**
- Catch regressions early
- Safe testing with isolated indices
- CI/CD integration ready

### Sample Data Generator

Create a script to generate sample data for rapid development without requiring the full Yelp dataset download.

**Script:** `admin/generate_sample_data.py`

```python
#!/usr/bin/env python3
"""
Generate sample data for development and testing.
Creates realistic but synthetic data without requiring the Yelp dataset.
"""

import argparse
import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

def generate_businesses(count: int = 100) -> list:
    """Generate sample business records."""
    categories = ["Restaurants", "Food", "Bars", "Cafes", "Pizza", "Mexican", "Italian"]
    cities = ["Las Vegas", "Phoenix", "Toronto"]

    businesses = []
    for i in range(count):
        businesses.append({
            "business_id": f"biz_{fake.uuid4()[:12]}",
            "name": fake.company() + " " + random.choice(["Restaurant", "Cafe", "Grill", "Kitchen"]),
            "address": fake.street_address(),
            "city": random.choice(cities),
            "state": "NV" if "Vegas" in cities else random.choice(["NV", "AZ", "ON"]),
            "postal_code": fake.postcode(),
            "latitude": float(fake.latitude()),
            "longitude": float(fake.longitude()),
            "stars": round(random.uniform(2.5, 5.0), 1),
            "review_count": random.randint(10, 500),
            "is_open": True,
            "categories": random.sample(categories, k=random.randint(1, 3)),
        })
    return businesses

def generate_users(count: int = 500) -> list:
    """Generate sample user records with trust scores."""
    users = []
    for i in range(count):
        account_age = random.randint(30, 2000)
        review_count = random.randint(1, 200)
        useful = random.randint(0, 100)
        fans = random.randint(0, 50)

        # Calculate trust score
        trust_score = (
            (min(review_count, 100) / 100 * 0.25) +
            (min(useful, 100) / 100 * 0.15) +
            (min(fans, 50) / 50 * 0.10) +
            (min(account_age, 1825) / 1825 * 0.25) +
            0.15  # Base score
        )

        users.append({
            "user_id": f"user_{fake.uuid4()[:12]}",
            "name": fake.name(),
            "review_count": review_count,
            "yelping_since": (datetime.now() - timedelta(days=account_age)).isoformat(),
            "account_age_days": account_age,
            "useful": useful,
            "funny": random.randint(0, 50),
            "cool": random.randint(0, 50),
            "fans": fans,
            "elite": [],
            "average_stars": round(random.uniform(2.5, 4.5), 1),
            "trust_score": round(min(trust_score, 1.0), 3),
            "flagged": False,
            "synthetic": False,
        })
    return users

def generate_reviews(businesses: list, users: list, count: int = 2000) -> list:
    """Generate sample review records."""
    reviews = []
    review_texts = [
        "Great food and excellent service! Will definitely come back.",
        "Average experience. Nothing special but not bad either.",
        "The ambiance was nice but the food took too long.",
        "Best restaurant in town! Highly recommend the specials.",
        "Decent meal for the price. Good portion sizes.",
    ]

    for i in range(count):
        business = random.choice(businesses)
        user = random.choice(users)
        stars = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 20, 35, 30])[0]

        reviews.append({
            "review_id": f"rev_{fake.uuid4()[:12]}",
            "user_id": user["user_id"],
            "business_id": business["business_id"],
            "stars": stars,
            "date": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
            "text": random.choice(review_texts),
            "useful": random.randint(0, 10),
            "funny": random.randint(0, 5),
            "cool": random.randint(0, 5),
            "status": "published",
            "partition": "historical",
            "synthetic": False,
        })
    return reviews

def main():
    parser = argparse.ArgumentParser(description="Generate sample data for development")
    parser.add_argument("--businesses", type=int, default=100, help="Number of businesses")
    parser.add_argument("--users", type=int, default=500, help="Number of users")
    parser.add_argument("--reviews", type=int, default=2000, help="Number of reviews")
    parser.add_argument("--output-dir", type=str, default="data/sample", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.businesses} businesses...")
    businesses = generate_businesses(args.businesses)

    print(f"Generating {args.users} users...")
    users = generate_users(args.users)

    print(f"Generating {args.reviews} reviews...")
    reviews = generate_reviews(businesses, users, args.reviews)

    # Write NDJSON files
    for name, data in [("businesses", businesses), ("users", users), ("reviews", reviews)]:
        filepath = output_dir / f"{name}.ndjson"
        with open(filepath, "w") as f:
            for record in data:
                f.write(json.dumps(record) + "\n")
        print(f"  Written {len(data)} records to {filepath}")

    print("Sample data generation complete!")

if __name__ == "__main__":
    main()
```

**Usage:**

```bash
# Generate default sample data
python admin/generate_sample_data.py

# Generate larger dataset
python admin/generate_sample_data.py --businesses 200 --users 1000 --reviews 5000

# Custom output directory
python admin/generate_sample_data.py --output-dir data/dev-sample
```

**Output:**

```
data/sample/
├── businesses.ndjson    # 100 businesses
├── users.ndjson         # 500 users
└── reviews.ndjson       # 2,000 reviews
```

**Benefits:**
- Rapid local development without Yelp dataset
- Consistent test data across environments
- Configurable data volumes
- No download or license requirements

---

## End of Specification

This document provides comprehensive specifications for building:

1. **Web Application** - FastAPI app with interactive attack UI
2. **Admin Setup Scripts** - Data preparation pipeline with progress logging
3. **Detection Queries** - ES|QL queries with LOOKUP JOIN
4. **Workflow Definitions** - YAML workflows with Elasticsearch notifications
5. **Agent Builder Tools** - Investigation tools for incident analysis
6. **Instruqt Challenges** - Four hands-on challenges (60 minutes total)

All components work together to tell the story: **"Search finds the insight. Workflows acts on it. Agent Builder explains it."**

---

## Implementation Status (2026-01-20)

**All major components from this specification have been implemented:**

| Component | Status | Notes |
|-----------|--------|-------|
| Web Application | ✅ Complete | FastAPI + Jinja2, all routes working |
| Attack Simulation | ✅ Complete | Turbo attack, auto-incident creation |
| Streaming Application | ✅ Complete | replay, inject, mixed modes |
| Admin Scripts | ✅ Complete | Full Yelp data pipeline tested |
| Agent Builder Tools | ✅ Complete | 4 tools + README |
| Instruqt Challenges | ✅ Complete | All 4 challenges with setup/check scripts |
| Presentation | ✅ Complete | Slides + talk track |
| Workflow YAML | ✅ Complete | Detection, flagging, resolution |

**End-to-end flow verified:** Attack injection → Detection → Auto-incident creation

See `.claude.md` for current implementation details and run instructions.
