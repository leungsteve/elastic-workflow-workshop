# Review Integrity & Fraud Detection Workshop
## What's New in Elastic 9.3: Simplify, Optimize, Innovate with AI

---

# Welcome

**90-Minute Workshop**

- 30 minutes: Presentation & Live Demo
- 60 minutes: Hands-on Challenges

Note: Welcome participants, ensure they have environment access

---

# Three Themes for Today

| Simplify | Optimize | Innovate with AI |
|----------|----------|------------------|
| ES\|QL readable queries | LOOKUP JOIN: one query, not ten | Agent Builder: ask in English |
| Workflows: visual, no-code | Auto-response: instant protection | ELSER: search by meaning |

> **Protecting review integrity at scale—detect fraud, automate response, investigate with AI.**

Note: These three themes run through everything in Elastic 9.3

---

# Today's Key Message

> **"Search finds the insight. Workflows acts on it. Agent Builder explains it."**

**Mapped to our themes:**
- **Simplify** → ES|QL + Workflows make it easy
- **Optimize** → Automated response reduces manual work
- **Innovate with AI** → Natural language investigation

Note: This is the theme that runs through everything we'll cover today

---

# The Problem: Review Fraud

[Screenshot: Example of a business with sudden rating drop]

**Coordinated fake reviews** damage business reputation and erode consumer trust.

This pattern affects ANY review system:
- 🍽️ **Restaurants:** Yelp, Google Business, TripAdvisor
- 🛒 **E-commerce:** Amazon, Home Depot, Walmart
- 📱 **Apps:** App Store, Google Play
- 💼 **B2B:** G2, Capterra, Trustpilot

Note: Ask audience if they've seen fake reviews affect purchasing decisions

---

# Why Review Integrity Matters

**For Businesses:**
- Revenue loss of 5-9% per star drop
- Reputation damage takes months to recover
- Customer trust erosion

**For Platforms:**
- User trust decline = user churn
- Content moderation costs at scale
- Legal and compliance risks

**For Consumers:**
- False information leads to poor decisions
- Erosion of trust in review systems

Note: Share that a one-star drop can mean significant revenue loss

---

# The Fraud Pattern

```
1. Attacker identifies target (successful business/product)
2. Creates multiple fake accounts (low trust signals)
3. Submits coordinated negative reviews (velocity spike)
4. Rating drops rapidly (integrity compromised)
5. Consumers see false information (trust eroded)
```

[Screenshot: Timeline showing review velocity spike]

Note: Walk through each step—this pattern is identical across Yelp, Amazon, App Store

---

# What We'll Build Today

A **complete fraud detection and response system:**

| Theme | What You'll Learn |
|-------|-------------------|
| **Simplify** | ES\|QL queries anyone can read and write |
| **Optimize** | LOOKUP JOIN + automated response = less manual work |
| **Innovate with AI** | Agent Builder for natural language investigation |

**The Flow:** Detect → Protect → Investigate → Resolve

Note: Preview the four challenges they'll work through

---

# Section 2: Elastic 9.3 Features

---

# Theme 1: SIMPLIFY with Workflows

[Screenshot: Workflows UI in Kibana]

**Native automation for search operations**

- ✅ Built into Elasticsearch—no external tools
- ✅ Visual builder—no code required
- ✅ Trigger → Condition → Action pattern

> **Simplify:** What used to require Lambda + SQS + custom code is now point-and-click

Note: Emphasize this is the headline feature for 9.3

---

# What Are Workflows?

**Definition:**
Automated pipelines that respond to data events and patterns

**Components:**
- **Triggers** - Schedule, Document change, Webhook
- **Steps** - Query, Transform, Act
- **Actions** - Update documents, Send notifications, Call APIs

Note: Compare to Lambda/Azure Functions but built into Elastic

---

# Workflow Pattern: Trigger -> Condition -> Action

```yaml
triggers:
  - type: schedule
    interval: 1m

steps:
  - id: detect
    type: elasticsearch.esql
    with:
      query: FROM reviews WHERE ...

  - id: respond
    type: elasticsearch.update
    with:
      index: reviews
      document:
        status: held
```

Note: Show the YAML structure, emphasize simplicity

---

# Theme 2: OPTIMIZE with Workflows

**Before Workflows:**
- External orchestration tools (cost 💰)
- Complex integrations (maintenance 🔧)
- Data leaving the cluster (latency ⏱️)
- Manual triage (people cost 👥)

**With Workflows:**
- Native to Elasticsearch (no extra cost)
- Data stays in cluster (sub-second response)
- Automated response (24/7, no fatigue)
- Simpler architecture (less to maintain)

> **Optimize:** Reduce operational cost and response time simultaneously

Note: Draw the architecture comparison if time permits

---

# SIMPLIFY: ES|QL with LOOKUP JOIN

**Cross-index correlation in readable syntax**

```sql
FROM reviews
| WHERE date > NOW() - 30 minutes
| LOOKUP JOIN users ON user_id
| STATS
    review_count = COUNT(*),
    avg_trust = AVG(trust_score)
  BY business_id
| WHERE review_count > 10 AND avg_trust < 0.4
```

> **Simplify:** Anyone can read this. Compare to equivalent DSL (30+ lines)

Note: Explain how LOOKUP JOIN enriches review data with user trust scores

---

# OPTIMIZE: Why LOOKUP JOIN?

**The Challenge:**
Reviews don't contain user trust scores directly

**Before LOOKUP JOIN:**
- Query reviews → Get user IDs → Query users → Join in application
- Multiple round trips, complex code, high latency

**With LOOKUP JOIN:**
- Single query, single round trip, milliseconds

> **Optimize:** One query replaces an entire microservice

Note: This is key for anomaly detection across related data

---

# Theme 3: INNOVATE WITH AI - Agent Builder

[Screenshot: Agent Builder interface in Kibana]

**AI-powered investigation tools**

- 🗣️ Natural language queries—no ES|QL knowledge required
- 🛠️ Custom tools powered by ES|QL under the hood
- 🔍 ELSER semantic search—find by meaning, not keywords

> **Innovate with AI:** Your analysts ask questions in English, AI handles the queries

Note: Explain that this turns ES|QL into natural language interfaces

---

# INNOVATE: Agent Builder in Action

**User asks:**
"Summarize the fraud incident for Mario's Pizza"

**Agent uses tool:**
```sql
FROM incidents
| WHERE incident_id == "INC-001"
| LOOKUP JOIN businesses ON business_id
| KEEP incident_id, business_name, severity,
       review_count, status
```

**Agent responds:**
"Mario's Pizza received 15 suspicious reviews in 30 minutes from accounts with an average trust score of 0.15. This is classified as CRITICAL severity. The business rating has been protected and 15 reviews are held for manual review."

> **Innovate with AI:** Investigation that took hours now takes seconds

Note: Show the flow from question to query to answer

---

# Section 3: Live Demo

---

# Our Demo Scenario

**Review Platform Data (Real Yelp Academic Dataset):**
- 14,000+ businesses (Philadelphia, Tampa, Tucson)
- 100,000+ user accounts with trust scores
- 1,000,000+ historical reviews

**Target:**
A famous Philadelphia landmark—"Reading Terminal Market" (4.6 stars, 1,860+ reviews)

**Universal Pattern:** Same detection works for Amazon products, App Store apps, hotel reviews

Note: Introduce the Yelp-based dataset, emphasize universal applicability

---

# The Data Model

[Screenshot: Index relationship diagram]

| Index | Contents |
|-------|----------|
| `businesses` | Restaurant profiles, ratings |
| `users` | Reviewer accounts, trust scores |
| `reviews` | Individual reviews with status |
| `incidents` | Detection records |

Note: Explain how trust_score is calculated

---

# Trust Score Calculation

```python
trust_score = (
  (review_count / 100 * 0.25) +
  (useful_votes / 100 * 0.15) +
  (fans / 50 * 0.10) +
  (elite_years * 0.05) +
  (account_age / 5 years * 0.25) +
  (rating_consistency * 0.20)
)
```

**Low trust (<0.3):** New accounts, few reviews
**High trust (>0.7):** Established, active reviewers

Note: Key insight - attackers have low trust scores

---

# Demo: Exploring the Data

[Screenshot: Kibana Dev Tools with ES|QL]

```sql
-- How many businesses?
FROM businesses | STATS count = COUNT(*)

-- Trust score distribution
FROM users
| STATS count = COUNT(*) BY
  CASE
    WHEN trust_score < 0.3 THEN "low"
    WHEN trust_score < 0.7 THEN "medium"
    ELSE "high"
  END
```

Note: Run these queries live, show the data shape

---

# Demo: Detection Query

```sql
FROM reviews
| WHERE date > NOW() - 30 minutes
| LOOKUP JOIN users ON user_id
| STATS
    review_count = COUNT(*),
    avg_stars = AVG(stars),
    avg_trust = AVG(trust_score),
    low_trust_count = COUNT(
      CASE WHEN trust_score < 0.3 THEN 1 END
    )
  BY business_id
| WHERE review_count > 10
    AND avg_stars < 2.0
    AND avg_trust < 0.4
| SORT review_count DESC
```

Note: Walk through each clause, explain the logic

---

# Demo: The Workflow (SIMPLIFY + OPTIMIZE)

[Screenshot: Workflow definition in Kibana]

**Review Fraud Detection Workflow:**

1. Runs every 5 minutes (scheduled trigger)
2. Executes ES|QL detection query (SIMPLIFY)
3. For each anomaly detected:
   - Hold suspicious reviews ✅
   - Protect business rating ✅
   - Create incident ✅
   - Send notification ✅

> **Optimize:** This automated response runs 24/7—no analyst fatigue

Note: Show the workflow YAML structure

---

# Demo: Simulating Fraud

[Screenshot: Attack UI in web application]

**Using the Workshop UI:**
1. Select target business ("Reading Terminal Market")
2. Launch coordinated fake reviews
3. Submit 15 low-trust reviews rapidly
4. Watch detection and response in real-time

Note: Actually simulate fraud in the live demo

---

# Demo: Workflow Response

[Screenshot: Workflow execution history]

**Watch in real-time:**
- Detection query fires
- Reviews change to "held" status
- Business shows "rating_protected: true"
- Incident appears in index
- Notification delivered

Note: Show the execution logs, timing

---

# Demo: Investigation with Agent Builder

[Screenshot: Agent conversation]

**Natural language investigation:**

- "What incidents were detected recently?"
- "Summarize the incident for Mario's Pizza"
- "Analyze the attackers - is this coordinated?"
- "What's the average account age of reviewers?"

Note: Ask these questions live, show Agent responses

---

# Demo: Resolving the Incident

[Screenshot: Incident resolution UI]

**Resolution workflow triggers:**
1. Mark incident as "resolved"
2. Delete malicious reviews
3. Remove rating protection
4. Notify business owner

**Business rating: Restored**

Note: Show the complete lifecycle

---

# The Complete Flow

```
[Attack] -> [Detection] -> [Response] -> [Investigation] -> [Resolution]
    |            |              |              |                |
 15 reviews   ES|QL +       Workflow      Agent Builder    Workflow
 submitted    LOOKUP JOIN   holds &       analyzes        resolves &
                            protects      patterns        restores
```

Note: Summarize the end-to-end flow

---

# Section 4: Hands-On Preview

---

# Your Challenges

| Challenge | Time | Focus |
|-----------|------|-------|
| 1. Getting to Know Your Data | 15 min | ES|QL, LOOKUP JOIN |
| 2. Workflows | 20 min | Build detection workflow |
| 3. Agent Builder | 10 min | Create investigation tools |
| 4. End-to-End Scenario | 15 min | Full attack simulation |

Note: Walk through what each challenge covers

---

# Challenge 1: Getting to Know Your Data

**You will:**
- Explore the pre-loaded indices
- Understand trust score distribution
- Write detection queries with LOOKUP JOIN
- Identify potential target businesses

```sql
FROM reviews
| LOOKUP JOIN users ON user_id
| WHERE trust_score < 0.4
| STATS count = COUNT(*) BY business_id
```

Note: This is foundational for everything else

---

# Challenge 2: Workflows

**You will:**
- Create a new workflow
- Add scheduled trigger (5 minutes)
- Configure detection step
- Add response actions:
  - Hold reviews
  - Protect business
  - Create incident
  - Send notification

Note: This is the core learning objective

---

# Challenge 3: Agent Builder

**You will:**
- Create `incident_summary` tool
- Create `reviewer_analysis` tool
- Test with natural language queries:
  - "What incidents exist?"
  - "Summarize incident INC-001"
  - "Who were the attackers?"

Note: Quick but impactful challenge

---

# Challenge 4: End-to-End Scenario

**You will:**
1. Check baseline state
2. Launch attack via UI
3. Watch workflow execute
4. Investigate with Agent
5. Resolve the incident

**Experience the full lifecycle!**

Note: This ties everything together

---

# Accessing Your Environment

[Screenshot: Instruqt lab interface]

**Lab URL:** `[provided by instructor]`

**Tabs:**
- Kibana (Dev Tools, Workflows, Agent)
- Web Application (Attack UI)
- Instructions

Note: Ensure everyone can access before starting

---

# Tips for Success

1. **Read the instructions carefully**
2. **Copy/paste the provided queries**
3. **Ask questions** - instructors are here to help
4. **Don't rush** - understanding > completion
5. **Experiment** - try variations on the queries

Note: Set expectations for pacing

---

# Resources

**Documentation:**
- [Elastic Workflows](https://www.elastic.co/guide/en/workflows/)
- [ES|QL Reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/esql.html)
- [Agent Builder Guide](https://www.elastic.co/guide/en/agent-builder/)

**Community:**
- [Elastic Community](https://discuss.elastic.co/)
- [Search Labs Blog](https://www.elastic.co/search-labs)

Note: Share these links in chat

---

# Questions Before We Begin?

[Screenshot: Kibana dashboard showing healthy environment]

Note: Take 2-3 questions, then transition to hands-on

---

# Let's Get Started!

**Challenge 1: Getting to Know Your Data**

Time: 15 minutes

> Open your lab environment and navigate to Kibana Dev Tools

Note: Start the timer, circulate to help

---

# Thank You!

**Key Takeaways:**

1. **Workflows** enable native automation in Elasticsearch
2. **ES|QL with LOOKUP JOIN** powers cross-index detection
3. **Agent Builder** makes investigation natural
4. **Together:** Insight to Action in seconds

> "Search finds the insight. Workflows acts on it. Agent Builder explains it."

Note: Wrap up, collect feedback, share resources

---

# Appendix: Additional Queries

---

# Combined Risk Score Query

```sql
FROM reviews
| WHERE date > NOW() - 30 minutes
| LOOKUP JOIN users ON user_id
| LOOKUP JOIN businesses ON business_id
| STATS
    review_count = COUNT(*),
    avg_stars = AVG(stars),
    avg_trust = AVG(trust_score),
    new_account_pct = AVG(
      CASE WHEN account_age_days < 30 THEN 1.0 ELSE 0.0 END
    )
  BY business_id, businesses.name
| EVAL risk_score = (
    (CASE WHEN review_count > 20 THEN 0.3
          WHEN review_count > 10 THEN 0.2
          ELSE 0.1 END) +
    (CASE WHEN avg_stars < 1.5 THEN 0.3
          WHEN avg_stars < 2.5 THEN 0.2
          ELSE 0.0 END) +
    (CASE WHEN avg_trust < 0.3 THEN 0.2
          WHEN avg_trust < 0.5 THEN 0.1
          ELSE 0.0 END) +
    (new_account_pct * 0.2)
  )
| WHERE risk_score > 0.5
| SORT risk_score DESC
```

Note: Advanced query for reference

---

# Incident Summary Tool (INNOVATE WITH AI)

```json
{
  "name": "incident_summary",
  "description": "Summarize a review fraud incident",
  "parameters": {
    "incident_id": {
      "type": "string",
      "description": "The incident ID"
    }
  },
  "esql": "FROM incidents
    | WHERE incident_id == '{{ incident_id }}'
    | LOOKUP JOIN businesses ON business_id
    | KEEP incident_id, business_name,
           severity, review_count, status"
}
```

Note: Tool definition for Agent Builder

---

# Reviewer Analysis Tool

```json
{
  "name": "reviewer_analysis",
  "description": "Analyze attackers in an incident",
  "parameters": {
    "incident_id": {
      "type": "string",
      "description": "The incident ID"
    }
  },
  "esql": "FROM reviews
    | WHERE incident_id == '{{ incident_id }}'
    | LOOKUP JOIN users ON user_id
    | STATS
        count = COUNT_DISTINCT(user_id),
        avg_age = AVG(account_age_days),
        avg_trust = AVG(trust_score)"
}
```

Note: Tool definition for Agent Builder

---

# Summary: Three Themes in Action

| Theme | What You Learned | Business Value |
|-------|------------------|----------------|
| **SIMPLIFY** | ES\|QL + Workflows | Anyone can build detection logic |
| **OPTIMIZE** | LOOKUP JOIN + Auto-response | Reduce cost, instant protection |
| **INNOVATE WITH AI** | Agent Builder + ELSER | Natural language investigation |

---

# What You Built Today

✅ **Fraud Detection** - ES|QL queries that correlate reviews with user trust
✅ **Automated Response** - Workflows that protect businesses instantly
✅ **AI Investigation** - Agent Builder tools for natural language analysis
✅ **Universal Pattern** - Applicable to any review system (Yelp, Amazon, App Store)

---

# Key Takeaways

1. **Simplify:** Complex detection in readable ES|QL, not verbose DSL
2. **Optimize:** One LOOKUP JOIN query replaces multiple API calls
3. **Optimize:** Automated workflows = 24/7 response without analyst fatigue
4. **Innovate with AI:** Analysts ask questions in English, AI handles queries
5. **Universal:** Same patterns work for restaurants, products, apps, services

---

# Next Steps

**Continue Learning:**
- Elastic Search Labs blog
- ES|QL documentation
- Workflows documentation
- Agent Builder guides

**Apply to Your Use Case:**
- Content moderation
- Fraud detection
- Security monitoring
- Customer feedback analysis

---

# Thank You!

**Questions?**

Workshop materials available in your lab environment

Note: Open for Q&A, remind participants about resources
