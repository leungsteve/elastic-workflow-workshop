# Review Bomb Detection Workshop

**What's New in Elastic Search 9.3: From Insight to Action with Workflows**

A hands-on workshop demonstrating Elastic's Workflows feature using a review bomb detection scenario. Participants learn to detect coordinated fake review attacks, automate protective responses, and investigate incidents using Agent Builder.

> **Key Message:** "Search finds the insight. Workflows acts on it. Agent Builder explains it."

---

## Overview

Review bombing is a coordinated attack where bad actors flood a business with fake negative reviews to damage its reputation. This workshop teaches participants to build a complete detection and response system using Elastic's latest features.

**Workshop Duration:** 90 minutes

- Presentation & Demo: 30 minutes
- Hands-on Labs: 60 minutes

**Target Audience:**

- Data analysts building search applications
- Developers implementing search operations
- Solutions architects evaluating Elastic capabilities

---

## What You'll Learn

| Challenge                 | Duration | Skills                                     |
| ------------------------- | -------- | ------------------------------------------ | ---------------------------------------- |
| Getting to Know Your Data | 15 min   | ES                                         | QL queries, LOOKUP JOIN, detection logic |
| Workflows                 | 20 min   | Automated detection and response pipelines |
| Agent Builder             | 10 min   | Natural language investigation tools       |
| End-to-End Scenario       | 15 min   | Full attack lifecycle simulation           |

---

## Features Highlighted

### Elastic 9.3 Capabilities

- **Workflows** - Native automation engine for search operations (headline feature)
- **ES|QL with LOOKUP JOIN** - Cross-index correlation for anomaly detection
- **Agent Builder** - AI-powered investigation tools
- **Semantic Search** - ELSER-powered content analysis

### Workshop Scenario

1. **Detect** - Identify abnormal review patterns using ES|QL
2. **Correlate** - Cross-reference with user trust scores via LOOKUP JOIN
3. **Automate** - Trigger workflows to hold reviews and protect businesses
4. **Investigate** - Use Agent Builder to analyze attack patterns
5. **Resolve** - Process incidents and restore business ratings

---

## Repository Structure

```
review-bomb-workshop/
├── admin/                    # Pre-workshop setup scripts
│   ├── prepare-data.sh       # Master setup script
│   ├── filter-businesses.py  # Filter Yelp data by city/category
│   ├── calculate-trust-scores.py
│   ├── partition-reviews.py  # Split historical/streaming
│   ├── generate-attackers.py # Create synthetic attack accounts
│   └── ...
│
├── streaming/                # Real-time review streaming app
│   ├── review_streamer.py    # Main application
│   ├── config.yaml           # Configuration
│   └── requirements.txt
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
git clone https://github.com/elastic/review-bomb-workshop.git
cd review-bomb-workshop
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

### Start Normal Review Traffic

```bash
cd streaming
python review_streamer.py --config config.yaml --mode replay
```

### Inject Review Bomb Attack

```bash
python review_streamer.py --config config.yaml --mode inject
```

### Mixed Mode (Normal Traffic + Attack)

```bash
python review_streamer.py --config config.yaml --mode mixed
```

The mixed mode runs normal traffic for a configurable period, then injects the attack automatically.

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
| [Specification](review-bomb-workshop-spec.md)  | Complete technical specification  |
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

- **Issues:** [GitHub Issues](https://github.com/elastic/review-bomb-workshop/issues)
- **Discussions:** [Elastic Community](https://discuss.elastic.co/)
- **Slack:** [Elastic Community Slack](https://ela.st/slack)
