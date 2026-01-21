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

In this challenge, you'll create three investigation tools:

1. **Incident Summary** - Get an overview of a review bomb incident
2. **Reviewer Analysis** - Analyze the attackers involved in an incident
3. **Similar Reviews** - Find reviews with similar content using semantic search

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
- **Type** - The query language (ES|QL)
- **ES|QL Query** - The actual query with `{{parameter}}` placeholders
- **ES|QL Parameters** - Input values the AI extracts from questions
- **Tool ID** - Unique identifier for the tool
- **Description** - Helps the AI understand when to use it
- **Labels** - Optional tags for organizing tools

---

## Tasks

> **Note:** You can create Agent Builder tools either through the UI or via Dev Tools API commands. We'll show both approaches - use whichever you prefer.

### Task 1: Navigate to Agent Builder (1 min)

**Option A: Using the UI**

1. Open **Kibana** in your browser
2. Click the hamburger menu in the top left
3. Navigate to **Machine Learning** > **Agent Builder**
   - Or use the search bar and type "Agent Builder"
4. Click **Create a new tool**

**Tip:** If you don't see Agent Builder, it may be under a different menu path. Try searching for "AI Assistant" or "Tools".

**Option B: Using Dev Tools (faster)**

If you prefer using API commands like in Challenge 2, you can create tools via Dev Tools. Skip the UI navigation and proceed to Task 2 - we'll provide API commands for each tool.

---

### Task 2: Create the Incident Summary Tool (4 min)

This tool retrieves details about a specific incident.

#### Step 1: Set the Type

In the **Type** dropdown, select **ES|QL**.

#### Step 2: Enter the ES|QL Query

Copy this query into the **ES|QL Query** editor:

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

#### Step 3: Define ES|QL Parameters

In the **ES|QL Parameters** section, add a parameter:

| Name | Description | Type | Optional |
|------|-------------|------|----------|
| `incident_id` | The incident ID to look up (e.g., INC-biz123-2024). Can also accept a business name to find the latest incident. | `text` | ☐ (unchecked) |

**Tip:** You can click **Infer parameter** to automatically detect parameters from your query's `{{placeholder}}` syntax.

#### Step 4: Fill in Details

- **Tool ID:** `incident_summary`
- **Description:**
  ```
  Retrieves a summary of a review bomb incident including the targeted business,
  attack severity, and current status. Use this tool when asked about incident
  details, incident status, or what happened to a specific business.
  ```

#### Step 5: Save the Tool

Click **Save** (or **Save & test** to test immediately).

**Alternative: Create via Dev Tools**

If you prefer the API approach, run this command in Dev Tools:

```
POST kbn://api/agent_builder/tools
{
  "id": "incident_summary",
  "type": "esql",
  "description": "Retrieves a summary of a review bomb incident including the targeted business, attack severity, and current status. Use this tool when asked about incident details, incident status, or what happened to a specific business.",
  "configuration": {
    "query": "FROM incidents | WHERE incident_id == \"{{incident_id}}\" OR business_name LIKE \"*{{incident_id}}*\" | SORT detected_at DESC | LIMIT 1 | LOOKUP JOIN businesses ON business_id | EVAL impact_assessment = CASE(severity == \"critical\", \"SEVERE - Business reputation at immediate risk. Urgent action required.\", severity == \"high\", \"SIGNIFICANT - Notable impact on business rating. Prompt investigation needed.\", TRUE, \"MODERATE - Limited impact so far. Standard investigation protocol.\"), time_since_detection = DATE_DIFF(\"minute\", detected_at, NOW()) | KEEP incident_id, incident_type, status, severity, business_name, city, metrics.review_count, metrics.avg_stars, metrics.avg_trust, metrics.unique_attackers, detected_at, time_since_detection, impact_assessment, stars AS business_original_rating",
    "params": {
      "incident_id": {
        "type": "text",
        "description": "The incident ID to look up (e.g., INC-biz123-2024). Can also accept a business name to find the latest incident."
      }
    }
  }
}
```

---

### Task 3: Create the Reviewer Analysis Tool (4 min)

This tool analyzes the attackers involved in an incident.

#### Step 1: Create New Tool

Click **Create a new tool** again.

#### Step 2: Set the Type

Select **ES|QL** from the Type dropdown.

#### Step 3: Enter the ES|QL Query

```esql
FROM reviews
| WHERE business_id == "{{business_id}}"
| WHERE @timestamp > NOW() - 24 hours
| WHERE stars <= 2
| LOOKUP JOIN users ON user_id
| WHERE trust_score < 0.5
| STATS
    reviews_submitted = COUNT(*),
    avg_rating_given = AVG(stars),
    first_review = MIN(@timestamp),
    last_review = MAX(@timestamp)
  BY user_id, trust_score, account_age_days
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

#### Step 4: Define ES|QL Parameters

Add this parameter in the **ES|QL Parameters** section:

| Name | Description | Type | Optional |
|------|-------------|------|----------|
| `business_id` | The business ID that was attacked. Can be found in incident details. | `text` | ☐ (unchecked) |

#### Step 5: Fill in Details

- **Tool ID:** `reviewer_analysis`
- **Description:**
  ```
  Analyzes the reviewers/attackers involved in a review bomb incident. Shows their
  trust scores, account ages, review patterns, and risk levels. Use this to understand
  who is behind an attack and identify coordination patterns.
  ```

#### Step 6: Save the Tool

Click **Save**.

**Alternative: Create via Dev Tools**

If you prefer the API approach, run this command in Dev Tools:

```
POST kbn://api/agent_builder/tools
{
  "id": "reviewer_analysis",
  "type": "esql",
  "description": "Analyzes the reviewers/attackers involved in a review bomb incident. Shows their trust scores, account ages, review patterns, and risk levels. Use this to understand who is behind an attack and identify coordination patterns.",
  "configuration": {
    "query": "FROM reviews | WHERE business_id == \"{{business_id}}\" | WHERE @timestamp > NOW() - 24 hours | WHERE stars <= 2 | LOOKUP JOIN users ON user_id | WHERE trust_score < 0.5 | STATS reviews_submitted = COUNT(*), avg_rating_given = AVG(stars), first_review = MIN(@timestamp), last_review = MAX(@timestamp) BY user_id, trust_score, account_age_days | EVAL risk_level = CASE(trust_score < 0.2 AND account_age_days < 7, \"CRITICAL\", trust_score < 0.3 AND account_age_days < 14, \"HIGH\", trust_score < 0.4 AND account_age_days < 30, \"MEDIUM\", TRUE, \"LOW\"), account_type = CASE(account_age_days < 7, \"Brand New\", account_age_days < 30, \"New\", account_age_days < 90, \"Recent\", TRUE, \"Established\") | SORT trust_score ASC, reviews_submitted DESC | LIMIT 20",
    "params": {
      "business_id": {
        "type": "text",
        "description": "The business ID that was attacked. Can be found in incident details."
      }
    }
  }
}
```

---

### Task 4: Create the Similar Reviews Tool (3 min)

This tool uses semantic search to find reviews with similar content - powerful for understanding attack narratives and patterns.

#### Step 1: Create New Tool

Click **Create a new tool** again.

#### Step 2: Set the Type

Select **ES|QL** from the Type dropdown.

**Note:** This tool uses a special semantic search capability that finds reviews by meaning, not just keywords.

#### Step 3: Enter the ES|QL Query

```esql
FROM reviews
| WHERE text_semantic MATCH "{{search_text}}"
| KEEP review_id, user_id, business_id, stars, text, date
| LIMIT 10
```

**Note:** The `text_semantic` field uses ELSER embeddings to find semantically similar content.

#### Step 4: Define ES|QL Parameters

Add this parameter in the **ES|QL Parameters** section:

| Name | Description | Type | Optional |
|------|-------------|------|----------|
| `search_text` | The text to search for semantically similar reviews. Describe the content you're looking for. | `text` | ☐ (unchecked) |

#### Step 5: Fill in Details

- **Tool ID:** `similar_reviews`
- **Description:**
  ```
  Finds reviews that are semantically similar to a given text using ELSER.
  Use this to understand attack narratives, find common themes in malicious
  reviews, or discover patterns in what attackers are claiming. Works by
  meaning, not just keywords - "food poisoning" will find reviews about
  illness even if they don't use those exact words.
  ```

#### Step 6: Save the Tool

Click **Save**.

**Alternative: Create via Dev Tools**

If you prefer the API approach, run this command in Dev Tools:

```
POST kbn://api/agent_builder/tools
{
  "id": "similar_reviews",
  "type": "esql",
  "description": "Finds reviews that are semantically similar to a given text using ELSER. Use this to understand attack narratives, find common themes in malicious reviews, or discover patterns in what attackers are claiming. Works by meaning, not just keywords.",
  "configuration": {
    "query": "FROM reviews | WHERE text_semantic MATCH \"{{search_text}}\" | KEEP review_id, user_id, business_id, stars, text, date | LIMIT 10",
    "params": {
      "search_text": {
        "type": "text",
        "description": "The text to search for semantically similar reviews. Describe the content you're looking for."
      }
    }
  }
}
```

---

### Task 5: Test Your Tools (2 min)

Now test your tools using the AI Assistant.

1. Open the **AI Assistant** panel
   - Look for a chat icon or "Assistant" in the Kibana interface
   - Or navigate to **AI Assistant** from the menu

2. Try these natural language queries:

   **Test Incident Summary:**
   > "What can you tell me about the most recent incident?"

   > "Summarize the incident for The Happy Diner"

   > "What's the status of incident INC-biz_sample_001?"

   **Test Reviewer Analysis:**
   > "Analyze the attackers who targeted business biz_sample_001"

   > "Show me who was involved in the review bomb attack"

   > "What patterns do the attackers have in common?"

   **Test Similar Reviews (Semantic Search):**
   > "Find reviews similar to 'food poisoning made me sick'"

   > "What reviews mention terrible service or rude staff?"

   > "Find attack reviews claiming health violations"

3. Observe how the AI:
   - Understands your question
   - Selects the appropriate tool
   - Extracts parameters from your question
   - Executes the query
   - Formats a helpful response

---

## Parameter Types Reference

When defining parameters, choose the appropriate type:

| Type | Use For | Example |
|------|---------|---------|
| `text` | Free-form strings, IDs, names | incident_id, business_name |
| `keyword` | Exact match values, enums | status, severity |
| `long` | Large integers | count thresholds |
| `integer` | Small integers | limits, offsets |
| `double` | Decimal numbers | scores, ratings |
| `float` | Decimal numbers (less precision) | percentages |
| `boolean` | True/false flags | include_resolved |
| `date` | Timestamps | start_date, end_date |

---

## Success Criteria

Before proceeding, verify:

- [ ] `incident_summary` tool is created and saved
- [ ] `reviewer_analysis` tool is created and saved
- [ ] `similar_reviews` tool is created and saved
- [ ] Tools respond correctly to natural language queries
- [ ] You can get incident details by asking in plain English
- [ ] You can analyze attackers without writing queries manually
- [ ] You can find semantically similar reviews by describing what you're looking for

---

## Key Takeaways

1. **Natural language investigation** - Analysts can ask questions without knowing ES|QL
2. **Semantic search** - Find content by meaning, not just keywords, to understand attack narratives
3. **Contextual tools** - Good descriptions help the AI choose the right tool
4. **Parameter extraction** - The AI pulls values from questions automatically
5. **Type safety** - Parameters have specific types (text, keyword, integer, etc.)
6. **Reusability** - Once created, tools work for any incident

---

## Bonus: Additional Tools to Consider

If you have extra time, consider creating these additional tools:

**Recent Incidents Tool:**
```esql
FROM incidents
| WHERE detected_at > NOW() - 24 hours
| SORT detected_at DESC
| KEEP incident_id, business_name, severity, status, detected_at
| LIMIT 10
```
- Parameter: None (or optional `hours` parameter with type `integer`)
- Useful for "Show me all recent attacks" queries

**Dev Tools command:**
```
POST kbn://api/agent_builder/tools
{
  "id": "recent_incidents",
  "type": "esql",
  "description": "Lists recent review bomb incidents from the last 24 hours. Use this when asked about recent attacks, latest incidents, or what's happening across the platform.",
  "configuration": {
    "query": "FROM incidents | WHERE detected_at > NOW() - 24 hours | SORT detected_at DESC | KEEP incident_id, business_name, severity, status, detected_at | LIMIT 10",
    "params": {}
  }
}
```

**Business Risk Assessment:**
```esql
FROM reviews
| WHERE business_id == "{{business_id}}"
| WHERE @timestamp > NOW() - 7 days
| LOOKUP JOIN users ON user_id
| STATS
    total_reviews = COUNT(*),
    avg_rating = AVG(stars),
    low_trust_reviews = COUNT(CASE WHEN trust_score < 0.4 THEN 1 END),
    new_account_reviews = COUNT(CASE WHEN account_age_days < 30 THEN 1 END)
| EVAL
    risk_score = (low_trust_reviews + new_account_reviews) / total_reviews,
    risk_level = CASE(risk_score > 0.5, "HIGH", risk_score > 0.2, "MEDIUM", "LOW")
```
- Parameter: `business_id` (type: `text`)
- Evaluates a business's vulnerability to attacks

**Dev Tools command:**
```
POST kbn://api/agent_builder/tools
{
  "id": "business_risk_assessment",
  "type": "esql",
  "description": "Evaluates a business's vulnerability to review bomb attacks based on recent review patterns and reviewer characteristics.",
  "configuration": {
    "query": "FROM reviews | WHERE business_id == \"{{business_id}}\" | WHERE @timestamp > NOW() - 7 days | LOOKUP JOIN users ON user_id | STATS total_reviews = COUNT(*), avg_rating = AVG(stars), low_trust_reviews = COUNT(CASE WHEN trust_score < 0.4 THEN 1 END), new_account_reviews = COUNT(CASE WHEN account_age_days < 30 THEN 1 END) | EVAL risk_score = (low_trust_reviews + new_account_reviews) / total_reviews, risk_level = CASE(risk_score > 0.5, \"HIGH\", risk_score > 0.2, \"MEDIUM\", \"LOW\")",
    "params": {
      "business_id": {
        "type": "text",
        "description": "The business ID to assess for attack risk."
      }
    }
  }
}
```

---

## Troubleshooting

**Tool doesn't appear in AI Assistant?**
- Ensure you clicked Save (or the API returned success)
- Refresh the AI Assistant panel
- Check that the Tool ID has no spaces or special characters
- Verify tools exist by running in Dev Tools:
  ```
  GET kbn://api/agent_builder/tools
  ```

**Query returns no results?**
- Verify the incident/business exists in your data
- Check the time window - data may be older than expected
- Use **Save & test** to run the query directly

**AI selects wrong tool?**
- Improve the tool description to be more specific
- Add example queries in the description
- Make parameter descriptions clearer

**Parameter not recognized?**
- Click **Infer parameter** to auto-detect from query
- Ensure parameter name matches `{{placeholder}}` exactly
- Check that the Type is appropriate for the value

In the next challenge, you'll run a full end-to-end attack simulation!
