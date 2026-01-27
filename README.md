# Negative Review Campaign Detection Workshop

**What's New in Elastic 9.3: Simplify, Optimize, Innovate with AI**

A hands-on workshop demonstrating how to detect negative review campaigns using Elastic's latest features. Participants learn to detect coordinated fake reviews, automate protective responses, and investigate incidents using AI—applicable to any review system (Yelp, Amazon, App Store, etc.).

> **Key Message:** "Protecting review integrity at scale—detect negative review campaigns, automate response, investigate with AI."

---

## Three Themes

| Theme | What You'll Learn | Business Value |
|-------|-------------------|----------------|
| **SIMPLIFY** | ES\|QL readable queries, Workflows visual builder | Anyone can build detection logic |
| **OPTIMIZE** | LOOKUP JOIN, automated response | Reduce cost, instant protection |
| **INNOVATE WITH AI** | Agent Builder, ELSER semantic search | Natural language investigation |

---

## Overview

Negative review campaigns are a universal problem affecting any platform with user-generated reviews—restaurants on Yelp, products on Amazon, apps in the App Store, hotels on TripAdvisor. Bad actors create fake accounts and submit coordinated fake reviews to manipulate ratings, damaging businesses and eroding consumer trust.

This workshop teaches participants to build a complete negative review campaign detection and response system using Elastic's latest features. **The same patterns work for any review system.**

**Workshop Duration:** 90 minutes

- Presentation & Demo: 30 minutes
- Hands-on Labs: 60 minutes

**Target Audience:**

- Trust & Safety teams
- Data analysts building search applications
- Developers implementing content moderation
- Solutions architects evaluating Elastic capabilities

---

## What You'll Learn

| Challenge | Duration | Theme | Skills |
|-----------|----------|-------|--------|
| Getting to Know Your Data | 15 min | SIMPLIFY | ES\|QL queries, LOOKUP JOIN, detection logic |
| Workflows | 20 min | SIMPLIFY + OPTIMIZE | Automated detection and response pipelines |
| Agent Builder | 10 min | INNOVATE WITH AI | Natural language investigation tools |
| End-to-End Scenario | 15 min | All Three | Full review bombing lifecycle simulation |

---

## Features Highlighted

### Elastic 9.3 Capabilities (Mapped to Themes)

| Feature | Theme | Description |
|---------|-------|-------------|
| **ES\|QL** | SIMPLIFY | Readable query syntax anyone can understand |
| **LOOKUP JOIN** | OPTIMIZE | One query replaces multiple API calls |
| **Workflows** | SIMPLIFY + OPTIMIZE | Visual, no-code automation |
| **Agent Builder** | INNOVATE WITH AI | Natural language investigation |
| **ELSER Semantic Search** | INNOVATE WITH AI | Search by meaning, not keywords |

### Workshop Scenario

1. **Detect** - Identify abnormal review patterns using ES|QL (SIMPLIFY)
2. **Correlate** - Cross-reference with user trust scores via LOOKUP JOIN (OPTIMIZE)
3. **Automate** - Trigger workflows to protect businesses instantly (OPTIMIZE)
4. **Investigate** - Use Agent Builder for natural language analysis (INNOVATE WITH AI)
5. **Resolve** - Process incidents and restore business integrity

### Universal Applicability

The negative review campaign detection patterns in this workshop apply to ANY review system:

- 🍽️ **Restaurants:** Yelp, Google Business, TripAdvisor
- 🛒 **E-commerce:** Amazon, Home Depot, Walmart, Target
- 📱 **Apps:** App Store, Google Play
- 💼 **B2B:** G2, Capterra, Trustpilot
- 🏨 **Travel:** Booking.com, Airbnb, Hotels.com

### Automated Response Actions

When a negative review campaign is detected, the workflow automatically:
- **Protects business ratings** - Sets `rating_protected: true` to freeze displayed rating
- **Holds suspicious reviews** - Marks campaign reviews as `status: "held"` for manual review
- **Creates incidents** - Logs the campaign with severity classification (critical/high/medium/low)
- **Records actions** - Tracks all response actions taken for audit purposes

---

## Repository Structure

```
elastic-workflow-workshop/
├── admin/                    # Pre-workshop setup scripts
│   ├── prepare_data.sh       # Master setup script
│   ├── filter_businesses.py  # Filter Yelp data by city/category
│   ├── calculate_trust_scores.py
│   ├── partition_reviews.py  # Split historical/streaming
│   ├── generate_attackers.py # Create synthetic attack accounts
│   └── ...
│
├── app/                      # FastAPI web application
│   ├── main.py               # Application entry point
│   ├── routers/              # API endpoints (businesses, reviews, incidents)
│   ├── services/             # Business logic (incident auto-detection)
│   ├── templates/            # Jinja2 HTML templates (dashboard, attack UI)
│   └── static/               # CSS and JavaScript
│
├── streaming/                # Real-time review streaming app
│   ├── review_streamer.py    # Main application (replay/inject/mixed modes)
│   └── ...
│
├── mappings/                 # Elasticsearch index mappings
│   ├── businesses.json
│   ├── users.json
│   ├── reviews.json
│   └── incidents.json
│
├── queries/                  # ES|QL detection queries
│   ├── detection/
│   └── investigation/
│
├── workflows/                # Workflow definitions (YAML)
│   ├── review-bomb-detection.yaml
│   ├── reviewer-flagging.yaml
│   └── incident-resolution.yaml
│
├── agent-tools/              # Agent Builder tool definitions
│   ├── incident-summary.json
│   └── reviewer-pattern-analysis.json
│
├── instruqt/                 # Workshop challenges
│   └── challenges/
│       ├── 01-getting-to-know-your-data/
│       ├── 02-workflows/
│       ├── 03-agent-builder/
│       └── 04-end-to-end-scenario/
│
├── presentation/             # Slides and talk track
│   ├── slides.md
│   └── images/
│
└── docs/                     # Additional documentation
    ├── admin-setup-guide.md
    └── troubleshooting.md
```

---

## Prerequisites

### For Workshop Facilitators

- Access to Elastic Cloud or self-managed Elasticsearch 9.3+
- Yelp Academic Dataset ([download here](https://www.yelp.com/dataset))
- Python 3.9+
- Instruqt account (for hosting workshop)

### For Workshop Participants

- Basic Elasticsearch knowledge
- Familiarity with ES|QL syntax (helpful but not required)
- Web browser with access to Kibana

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/elastic/elastic-workflow-workshop.git
cd elastic-workflow-workshop
```

### 2. Set Up Python Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Elasticsearch credentials
```

```bash
# .env contents
ELASTICSEARCH_URL=https://your-cluster.es.cloud.elastic.co:443
ELASTICSEARCH_API_KEY=your-api-key
```

### 4. Download Yelp Dataset

Download the Yelp Academic Dataset from https://www.yelp.com/dataset and extract to `data/raw/`:

```
data/raw/
├── yelp_academic_dataset_business.json
├── yelp_academic_dataset_user.json
└── yelp_academic_dataset_review.json
```

### 5. Prepare Workshop Data

```bash
cd admin
./prepare-data.sh
```

This script:

- Filters businesses to selected cities/categories
- Calculates user trust scores
- Partitions reviews into historical and streaming sets
- Generates synthetic attacker accounts and reviews
- Creates Elasticsearch indices
- Loads historical data

### 6. Verify Environment

```bash
python verify-environment.py
```

---

## Running the Demo

### Option 1: Web Application (Recommended)

The FastAPI web app provides a dashboard, attack simulator, and incident management UI.

```bash
# Start the web application
python -m app.main

# Access at http://localhost:8000
```

**Web App Features:**
- **Dashboard** - Real-time attack monitoring with auto-refresh
- **Attack Simulator** - Launch turbo attacks against target businesses
- **Incidents** - View and resolve detected incidents
- **Businesses** - Browse and search business data

**Key API Endpoints:**
```bash
# Launch attack (creates reviews + attacker users)
POST /api/reviews/bulk-attack?business_id=<ID>&count=15

# Run detection workflow (creates incident + executes response actions)
POST /api/incidents/detect?business_id=<ID>&hours=1

# Check business protection status
GET /api/businesses/<ID>

# List incidents
GET /api/incidents?business_id=<ID>
```

### Option 2: Streaming Application (CLI)

For CLI-based demos or automated testing.

```bash
cd streaming

# Replay legitimate reviews
python review_streamer.py --mode replay

# Inject attack reviews
python review_streamer.py --mode inject --business-id <BUSINESS_ID> --count 15

# Mixed mode (normal traffic, then attack)
python review_streamer.py --mode mixed --business-id <BUSINESS_ID> --normal-duration 60
```

The mixed mode runs normal traffic for a configurable period, then injects the attack automatically.

### Option 3: Agent Builder Setup (Quick Start)

Set up all Agent Builder tools and the investigation agent with a single command:

```bash
python admin/setup_agent_builder.py
```

This creates:
- **incident_summary** tool - ES|QL query for incident details
- **reviewer_analysis** tool - Attacker pattern analysis with risk levels
- **similar_reviews** tool - ELSER semantic search for attack narratives
- **Review Campaign Investigator** agent - Custom agent with all tools assigned

Options:
```bash
python admin/setup_agent_builder.py --delete   # Delete and recreate all resources
python admin/setup_agent_builder.py --dry-run  # Preview without making changes
```

---

## Data Sources

### Real Data (Yelp Academic Dataset)

| Data                 | Source | Usage                                          |
| -------------------- | ------ | ---------------------------------------------- |
| Businesses           | Yelp   | Restaurant and food establishment profiles     |
| Users                | Yelp   | Reviewer accounts with calculated trust scores |
| Reviews (Historical) | Yelp   | Baseline review activity                       |
| Reviews (Streaming)  | Yelp   | Held back for real-time replay                 |

### Synthetic Data (Generated)

| Data              | Purpose                                              |
| ----------------- | ---------------------------------------------------- |
| Attacker Accounts | Low-trust profiles for coordinated attack simulation |
| Attack Reviews    | Negative review content targeting selected business  |

**Note:** The Yelp Academic Dataset is for educational and academic use. Please review and comply with their [terms of use](https://www.yelp.com/dataset/documentation/main).

---

## Workshop Customization

### Changing Target Cities

Edit `admin/filter-businesses.py`:

```python
CITIES = ["Las Vegas", "Phoenix", "Toronto"]  # Modify as needed
CATEGORIES = ["Restaurants", "Food", "Bars"]
```

### Adjusting Detection Thresholds

Edit `workflows/review-bomb-detection.yaml`:

```yaml
# Adjust these thresholds based on your data volume
| WHERE review_count > 10 AND avg_stars < 2.0 AND avg_trust < 0.4
```

### Modifying Attack Intensity

Edit `config/config.yaml`:

```yaml
injection:
  delay_before_attack_seconds: 60
  reviews_per_second: 15 # Increase for more dramatic demo
```

---

## Instruqt Deployment

### Build the Track

```bash
cd instruqt
instruqt track validate
instruqt track push
```

### Track Configuration

The `track.yml` defines:

- Virtual machine specifications
- Elasticsearch cluster provisioning
- Pre-installed tools and data

See `instruqt/README.md` for detailed deployment instructions.

---

## Documentation

| Document                                       | Description                       |
| ---------------------------------------------- | --------------------------------- |
| [Specification](docs/review-bomb-workshop-spec.md)  | Complete technical specification  |
| [Admin Setup Guide](docs/admin-setup-guide.md) | Detailed facilitator instructions |
| [Talk Track](docs/talk-track.md)               | Presenter speaking notes          |
| [Troubleshooting](docs/troubleshooting.md)     | Common issues and solutions       |

---

## Related Resources

- [Elastic Workflows Documentation](https://www.elastic.co/guide/en/workflows/)
- [ES|QL Reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/esql.html)
- [Agent Builder Guide](https://www.elastic.co/guide/en/agent-builder/)
- [Elastic Search Labs Blog](https://www.elastic.co/search-labs)
- [Keep (Workflows) Open Source](https://github.com/keephq/keep)

---

## Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black .

# Lint
flake8
```

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

**Note:** The Yelp Academic Dataset has its own license terms. This workshop code is separate from the dataset license.

---

## Acknowledgments

- **Yelp** for providing the Academic Dataset
- **Keep** team for the open-source Workflows engine
- **Elastic Search Labs** for ongoing innovation
- Workshop contributors and reviewers

---

## Support

- **Issues:** [GitHub Issues](https://github.com/elastic/elastic-workflow-workshop/issues)
- **Discussions:** [Elastic Community](https://discuss.elastic.co/)
- **Slack:** [Elastic Community Slack](https://ela.st/slack)
