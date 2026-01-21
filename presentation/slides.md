# Review Bomb Detection Workshop
## What's New in Elastic Search 9.3: From Insight to Action with Workflows

---

# Welcome

**90-Minute Workshop**

- 30 minutes: Presentation & Live Demo
- 60 minutes: Hands-on Challenges

Note: Welcome participants, ensure they have environment access

---

# Today's Key Message

> **"Search finds the insight.**
> **Workflows acts on it.**
> **Agent Builder explains it."**

Note: This is the theme that runs through everything we'll cover today

---

# The Problem: Review Bombing

[Screenshot: Example of a business with sudden rating drop]

A **coordinated attack** where bad actors flood a business with fake negative reviews to damage its reputation.

Note: Ask audience if they've heard of review bombing or seen it happen

---

# Real-World Impact

**For Businesses:**
- Revenue loss of 5-9% per star
- Reputation damage
- Customer trust erosion

**For Platforms:**
- User trust decline
- Content moderation costs
- Legal and compliance risks

Note: Share that a one-star drop can mean significant revenue loss

---

# The Attack Pattern

```
1. Attacker identifies target (successful business)
2. Creates multiple fake accounts
3. Submits coordinated negative reviews
4. Business rating drops rapidly
5. Legitimate customers see false information
```

[Screenshot: Timeline showing review velocity spike]

Note: Walk through each step, emphasize the speed and coordination

---

# What We'll Build Today

A **complete detection and response system:**

1. **Detect** - ES|QL queries with LOOKUP JOIN
2. **Automate** - Workflows for real-time response
3. **Investigate** - Agent Builder for analysis
4. **Resolve** - Incident management workflow

Note: Preview the four challenges they'll work through

---

# Section 2: Elastic 9.3 Features

---

# Headline Feature: Workflows

[Screenshot: Workflows UI in Kibana]

**Native automation for search operations**

- Built into Elasticsearch
- No external tools required
- Trigger, Condition, Action pattern

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
    interval: 5m

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

# Why Workflows Matter

**Before Workflows:**
- External orchestration tools
- Complex integrations
- Data leaving the cluster
- Latency in response

**With Workflows:**
- Native to Elasticsearch
- Data stays in cluster
- Sub-second response times
- Simpler architecture

Note: Draw the architecture comparison if time permits

---

# ES|QL with LOOKUP JOIN

**Cross-index correlation for real-time detection**

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

Note: Explain how LOOKUP JOIN enriches review data with user trust scores

---

# Why LOOKUP JOIN?

**The Challenge:**
Reviews don't contain user trust scores directly

**The Solution:**
Join review data with user data at query time

**The Result:**
Rich, correlated insights for detection

Note: This is key for anomaly detection across related data

---

# Agent Builder

[Screenshot: Agent Builder interface in Kibana]

**AI-powered investigation tools**

- Natural language queries
- Custom tools with ES|QL
- Context-aware responses

Note: Explain that this turns ES|QL into natural language interfaces

---

# Agent Builder in Action

**User asks:**
"Summarize the incident for Mario's Pizza"

**Agent uses tool:**
```sql
FROM incidents
| WHERE incident_id == "INC-001"
| LOOKUP JOIN businesses ON business_id
| KEEP incident_id, business_name, severity,
       review_count, status
```

**Agent responds:**
"Mario's Pizza received 15 suspicious reviews in 30 minutes..."

Note: Show the flow from question to query to answer

---

# Section 3: Live Demo

---

# Our Demo Scenario

**Review Platform Data:**
- 10,000+ restaurants
- 50,000+ user accounts
- 200,000+ historical reviews

**Target:**
A popular 4.5-star restaurant in Las Vegas

Note: Introduce the Yelp-based dataset

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

# Demo: The Workflow

[Screenshot: Workflow definition in Kibana]

**Review Bomb Detection Workflow:**

1. Runs every 5 minutes
2. Executes detection query
3. For each anomaly:
   - Hold suspicious reviews
   - Protect business rating
   - Create incident
   - Send notification

Note: Show the workflow YAML structure

---

# Demo: Launching the Attack

[Screenshot: Attack UI in web application]

**Using the Workshop UI:**
1. Select target business
2. Generate attack reviews
3. Submit 15 reviews rapidly
4. Watch the dashboard

Note: Actually launch an attack in the live demo

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

# Incident Summary Tool

```json
{
  "name": "incident_summary",
  "description": "Summarize a review bomb incident",
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
