# Creating Investigation Tools with Agent Builder

## Time
10 minutes

## Objective
Create AI-powered investigation tools using Agent Builder that let analysts ask natural language questions about review bomb incidents.

---

## Background

Automated detection is great for catching attacks quickly, but analysts still need to investigate incidents. Traditional investigation requires writing complex queries and interpreting raw data - a time-consuming process.

**Agent Builder** changes this by letting you create custom tools that an AI assistant can use. Instead of writing queries, analysts can ask questions like:

- "Summarize the latest incident"
- "Who were the attackers?"
- "What patterns do the attackers have in common?"

In this challenge, you'll create two investigation tools:

1. **Incident Summary** - Get an overview of a review bomb incident
2. **Reviewer Analysis** - Analyze the attackers involved in an incident

---

## How Agent Builder Works

```
+------------------+     +------------------+     +------------------+
|  Analyst asks    |---->|  AI Assistant    |---->|  Tool executes   |
|  natural language|     |  selects tool    |     |  ES|QL query     |
|  question        |     |  & parameters    |     |                  |
+------------------+     +------------------+     +--------+---------+
                                                          |
                                                          v
                         +------------------+     +------------------+
                         |  AI formats      |<----|  Query returns   |
                         |  response        |     |  results         |
                         +------------------+     +------------------+
```

Each tool you create has:
- **Name** - How the AI identifies the tool
- **Description** - Helps the AI understand when to use it
- **Parameters** - Input values the AI extracts from the question
- **ES|QL Query** - The actual query that runs against your data
- **Response Template** - How results are formatted for the analyst

---

## Tasks

### Task 1: Navigate to Agent Builder (1 min)

1. Open **Kibana** in your browser
2. Click the hamburger menu in the top left
3. Navigate to **Machine Learning** > **Agent Builder**
   - Or use the search bar and type "Agent Builder"
4. Click **Create Tool**

**Tip:** If you don't see Agent Builder, it may be under a different menu path depending on your Kibana version. Try searching for "AI Assistant" or "Tools".

---

### Task 2: Create the Incident Summary Tool (4 min)

This tool retrieves details about a specific incident.

1. Click **Create Tool**

2. Enter the basic information:
   - **Name:** `incident_summary`
   - **Description:** `Retrieves a summary of a review bomb incident including the targeted business, attack severity, and current status. Use this tool when asked about incident details, incident status, or what happened to a specific business.`

3. Define the parameters:
   ```json
   {
     "incident_id": {
       "type": "string",
       "description": "The incident ID to look up (e.g., INC-biz123-20240115). Can also accept a business name to find the latest incident for that business.",
       "required": true
     }
   }
   ```

4. Enter the ES|QL query:
   ```esql
   FROM incidents
   | WHERE incident_id == "{{incident_id}}" OR business_name LIKE "*{{incident_id}}*"
   | SORT detected_at DESC
   | LIMIT 1
   | LOOKUP JOIN businesses ON business_id
   | EVAL
       impact_assessment = CASE(
         severity == "critical", "SEVERE - Business reputation at immediate risk. Urgent action required.",
         severity == "high", "SIGNIFICANT - Notable impact on business rating. Prompt investigation needed.",
         TRUE, "MODERATE - Limited impact so far. Standard investigation protocol."
       ),
       time_since_detection = DATE_DIFF("minute", detected_at, NOW())
   | KEEP incident_id, incident_type, status, severity, business_name, city,
          metrics.review_count, metrics.avg_stars, metrics.avg_trust,
          metrics.unique_attackers, detected_at, time_since_detection,
          impact_assessment, stars AS business_original_rating
   ```

5. (Optional) Add a response template:
   ```markdown
   ## Incident Summary: {{incident_id}}

   **Business:** {{business_name}} ({{city}})
   **Original Rating:** {{business_original_rating}} stars
   **Status:** {{status}} | **Severity:** {{severity}}

   ### Attack Metrics
   | Metric | Value |
   |--------|-------|
   | Suspicious Reviews | {{metrics.review_count}} |
   | Unique Attackers | {{metrics.unique_attackers}} |
   | Average Attack Rating | {{metrics.avg_stars}} stars |
   | Average Attacker Trust | {{metrics.avg_trust}} |

   ### Impact Assessment
   {{impact_assessment}}

   **Detected:** {{detected_at}} ({{time_since_detection}} minutes ago)
   ```

6. Click **Save Tool**

---

### Task 3: Create the Reviewer Analysis Tool (4 min)

This tool analyzes the attackers involved in an incident.

1. Click **Create Tool**

2. Enter the basic information:
   - **Name:** `reviewer_analysis`
   - **Description:** `Analyzes the reviewers/attackers involved in a review bomb incident. Shows their trust scores, account ages, review patterns, and risk levels. Use this to understand who is behind an attack and identify coordination patterns.`

3. Define the parameters:
   ```json
   {
     "business_id": {
       "type": "string",
       "description": "The business ID that was attacked. Can be found in the incident details.",
       "required": true
     },
     "time_window": {
       "type": "string",
       "description": "How far back to look for suspicious reviews. Use format like '1h', '24h', '7d'. Defaults to 24h if not specified.",
       "required": false,
       "default": "24 hours"
     }
   }
   ```

4. Enter the ES|QL query:
   ```esql
   FROM reviews
   | WHERE business_id == "{{business_id}}"
   | WHERE date > NOW() - {{time_window}}
   | WHERE stars <= 2
   | LOOKUP JOIN users ON user_id
   | WHERE trust_score < 0.5
   | STATS
       reviews_submitted = COUNT(*),
       avg_rating_given = AVG(stars),
       first_review = MIN(date),
       last_review = MAX(date)
     BY user_id, name AS username, trust_score, account_age_days, review_count AS total_reviews
   | EVAL
       risk_level = CASE(
         trust_score < 0.2 AND account_age_days < 7, "CRITICAL",
         trust_score < 0.3 AND account_age_days < 14, "HIGH",
         trust_score < 0.4 AND account_age_days < 30, "MEDIUM",
         TRUE, "LOW"
       ),
       account_type = CASE(
         account_age_days < 7, "Brand New",
         account_age_days < 30, "New",
         account_age_days < 90, "Recent",
         TRUE, "Established"
       )
   | SORT trust_score ASC, reviews_submitted DESC
   | LIMIT 20
   ```

5. (Optional) Add a response template:
   ```markdown
   ## Reviewer Analysis

   Found {{_count}} suspicious reviewers targeting this business.

   ### Attacker Profiles

   | Username | Trust Score | Account Age | Attack Reviews | Risk Level |
   |----------|-------------|-------------|----------------|------------|
   {{#each results}}
   | {{username}} | {{trust_score}} | {{account_age_days}} days ({{account_type}}) | {{reviews_submitted}} | {{risk_level}} |
   {{/each}}

   ### Pattern Analysis
   - **Average Trust Score:** {{avg_trust_score}}
   - **New Accounts (< 30 days):** {{new_account_count}}
   - **Multiple Reviewers:** {{multi_review_count}} attackers submitted 2+ reviews

   ### Coordination Indicators
   {{#if high_coordination}}
   **WARNING:** Strong coordination signals detected. Multiple new, low-trust accounts acting simultaneously.
   {{/if}}
   ```

6. Click **Save Tool**

---

### Task 4: Test Your Tools (1 min)

Now test your tools using the AI Assistant.

1. Open the **AI Assistant** panel
   - Look for a chat icon or "Assistant" in the Kibana interface
   - Or navigate to **AI Assistant** from the menu

2. Try these natural language queries:

   **Test Incident Summary:**
   > "What can you tell me about the most recent incident?"

   > "Summarize the incident for Mario's Italian Kitchen"

   > "What's the status of incident INC-biz_sample_001?"

   **Test Reviewer Analysis:**
   > "Analyze the attackers who targeted business biz_sample_001"

   > "Show me who was involved in the review bomb attack in the last 2 hours"

   > "What patterns do the attackers have in common?"

3. Observe how the AI:
   - Understands your question
   - Selects the appropriate tool
   - Extracts parameters from your question
   - Executes the query
   - Formats a helpful response

---

## Expected Results

When you ask about an incident, you should see output like:

```
## Incident Summary: INC-biz_sample_001-20240115

**Business:** Mario's Italian Kitchen (San Francisco)
**Original Rating:** 4.5 stars
**Status:** open | **Severity:** high

### Attack Metrics
| Metric | Value |
|--------|-------|
| Suspicious Reviews | 8 |
| Unique Attackers | 5 |
| Average Attack Rating | 1.3 stars |
| Average Attacker Trust | 0.18 |

### Impact Assessment
SIGNIFICANT - Notable impact on business rating. Prompt investigation needed.

**Detected:** 2024-01-15T14:30:00Z (45 minutes ago)
```

---

## Success Criteria

Before proceeding, verify:

- [ ] `incident_summary` tool is created and saved
- [ ] `reviewer_analysis` tool is created and saved
- [ ] Tools respond correctly to natural language queries
- [ ] You can get incident details by asking in plain English
- [ ] You can analyze attackers without writing queries manually

---

## Key Takeaways

1. **Natural language investigation** - Analysts can ask questions without knowing ES|QL
2. **Contextual tools** - Good descriptions help the AI choose the right tool
3. **Parameter extraction** - The AI pulls values from questions automatically
4. **Formatted responses** - Templates make data easy to understand
5. **Reusability** - Once created, tools work for any incident

---

## Bonus: Additional Tools to Consider

If you have extra time, consider creating these additional tools:

**Recent Incidents Tool:**
- Lists all incidents from the last 24 hours
- Useful for "Show me all recent attacks" queries

**Business Risk Assessment:**
- Evaluates a business's vulnerability to attacks
- Shows review patterns and identifies risks

**Attack Timeline:**
- Shows the progression of an attack over time
- Helps identify when the attack started and ended

---

## Troubleshooting

**Tool doesn't appear in AI Assistant?**
- Ensure you clicked Save
- Refresh the AI Assistant panel
- Check that the tool name has no spaces or special characters

**Query returns no results?**
- Verify the incident/business exists in your data
- Check the time window - data may be older than expected
- Run the query directly in Dev Tools to debug

**AI selects wrong tool?**
- Improve the tool description to be more specific
- Add example queries in the description
- Make parameter descriptions clearer

In the next challenge, you'll run a full end-to-end attack simulation!
