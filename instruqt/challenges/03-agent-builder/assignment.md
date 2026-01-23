# Creating Investigation Tools with Agent Builder

## Time
15 minutes

## Theme Focus: INNOVATE WITH AI
> Ask questions in plain English—no query skills required. AI handles the investigation, democratizing access for all analysts.

## Objective
Create AI-powered investigation tools and a custom agent using Agent Builder that lets analysts ask natural language questions about review fraud incidents.

---

## Background

Automated detection is great for catching attacks quickly, but analysts still need to investigate incidents. Traditional investigation requires writing complex queries and interpreting raw data - a time-consuming process.

**Agent Builder** changes this by letting you create custom tools that an AI assistant can use. Instead of writing queries, analysts can ask questions like:

- "Summarize the latest incident"
- "Who were the attackers?"
- "What patterns do the attackers have in common?"

In this challenge, you'll create three investigation tools and an agent to use them:

1. **Incident Summary** - Get an overview of a review fraud incident
2. **Reviewer Analysis** - Analyze the attackers involved in an incident
3. **Similar Reviews** - Find reviews with similar content using semantic search
4. **Review Fraud Investigator Agent** - A custom agent configured to investigate attacks

---

## How Agent Builder Works

```
+------------------+     +------------------+     +------------------+
|  Analyst asks    |---->|  Custom Agent    |---->|  Tool executes   |
|  natural language|     |  selects tool    |     |  ES|QL query     |
|  question        |     |  & parameters    |     |                  |
+------------------+     +------------------+     +--------+---------+
                                                          |
                                                          v
                         +------------------+     +------------------+
                         |  Agent formats   |<----|  Query returns   |
                         |  response        |     |  results         |
                         +------------------+     +------------------+
```

**Tools** are ES|QL queries with parameters that execute against your data.

**Agents** are AI models with custom instructions and assigned tools that determine how they respond to questions.

---

## Tasks

> **Quick Setup Alternative:** If you prefer to skip the manual steps, you can run a script that creates all tools and the agent automatically:
>
> ```bash
> python admin/setup_agent_builder.py
> ```
>
> Then skip to **Task 6: Test Your Agent** to verify everything works. The script creates the same tools and agent described in Tasks 2-5.

---

### Task 1: Navigate to Agent Builder (1 min)

1. Open **Kibana** in your browser
2. Click the hamburger menu in the top left
3. Navigate to **Management** > **AI** > **Agent Builder**
   - Or use the search bar and type "Agent Builder"
4. You'll see the Agent Builder home page with options for **Agents** and **Tools**

**Tip:** If you don't see Agent Builder, it may need to be enabled. Contact your administrator.

---

### Task 2: Create the Incident Summary Tool (3 min)

This tool retrieves details about a specific incident.

1. Click **Manage tools** (or navigate to the Tools section)
2. Click **New Tool**

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
    time_since_detection = DATE_DIFF("minute", detected_at, NOW()),
    business_original_rating = stars
| KEEP incident_id, incident_type, status, severity, business_name, city,
       review_count, avg_rating, avg_trust_score,
       unique_reviewers, detected_at, time_since_detection,
       impact_assessment, business_original_rating
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
  Retrieves a summary of a review fraud incident including the targeted business,
  attack severity, and current status. Use this tool when asked about incident
  details, incident status, or what happened to a specific business.
  ```

#### Step 5: Save the Tool

Click **Save**.

---

### Task 3: Create the Reviewer Analysis Tool (3 min)

This tool analyzes the attackers involved in an incident.

1. Click **New Tool** again

#### Step 1: Set the Type

Select **ES|QL** from the Type dropdown.

#### Step 2: Enter the ES|QL Query

```esql
FROM reviews
| WHERE business_id == "{{business_id}}"
| WHERE date > NOW() - 24 hours
| WHERE stars <= 2
| LOOKUP JOIN users ON user_id
| WHERE trust_score < 0.5
| STATS
    reviews_submitted = COUNT(*),
    avg_rating_given = AVG(stars),
    first_review = MIN(date),
    last_review = MAX(date)
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

#### Step 3: Define ES|QL Parameters

Add this parameter in the **ES|QL Parameters** section:

| Name | Description | Type | Optional |
|------|-------------|------|----------|
| `business_id` | The business ID that was attacked. Can be found in incident details. | `text` | ☐ (unchecked) |

#### Step 4: Fill in Details

- **Tool ID:** `reviewer_analysis`
- **Description:**
  ```
  Analyzes the reviewers/attackers involved in a review fraud incident. Shows their
  trust scores, account ages, review patterns, and risk levels. Use this to understand
  who is behind an attack and identify coordination patterns.
  ```

#### Step 5: Save the Tool

Click **Save**.

---

### Task 4: Create the Similar Reviews Tool (3 min)

This tool uses semantic search to find reviews with similar content - powerful for understanding attack narratives and patterns.

1. Click **New Tool** again

#### Step 1: Set the Type

Select **ES|QL** from the Type dropdown.

**Note:** This tool uses a special semantic search capability that finds reviews by meaning, not just keywords.

#### Step 2: Enter the ES|QL Query

```esql
FROM reviews METADATA _score
| WHERE text_semantic: "{{search_text}}"
| SORT _score DESC
| KEEP review_id, user_id, business_id, stars, text, date, _score
| LIMIT 10
```

**Note:** The `text_semantic` field uses ELSER embeddings to find semantically similar content. The `:` operator performs semantic search, and `_score` indicates relevance.

#### Step 3: Define ES|QL Parameters

Add this parameter in the **ES|QL Parameters** section:

| Name | Description | Type | Optional |
|------|-------------|------|----------|
| `search_text` | The text to search for semantically similar reviews. Describe the content you're looking for. | `text` | ☐ (unchecked) |

#### Step 4: Fill in Details

- **Tool ID:** `similar_reviews`
- **Description:**
  ```
  Finds reviews that are semantically similar to a given text using ELSER.
  Use this to understand attack narratives, find common themes in malicious
  reviews, or discover patterns in what attackers are claiming. Works by
  meaning, not just keywords - "food poisoning" will find reviews about
  illness even if they don't use those exact words.
  ```

#### Step 5: Save the Tool

Click **Save**.

---

### Task 5: Create the Review Fraud Investigator Agent (3 min)

Now that you have tools, create a custom agent that uses them to investigate review fraud attacks.

1. Navigate back to the **Agents** section in Agent Builder
2. Click **New agent**

#### Step 1: Configure Required Settings

In the **Settings** tab, fill in:

- **Agent ID:** `review_fraud_investigator`
- **Display Name:** `Review Fraud Investigator`
- **Display Description:**
  ```
  Investigates review fraud attacks on businesses. Can summarize incidents,
  analyze attacker patterns, and find similar malicious reviews.
  ```

#### Step 2: Add Custom Instructions

In the **Custom Instructions** field, enter:

```
You are a Trust & Safety analyst investigating review fraud attacks on the FreshEats platform.

When investigating incidents:
1. Start by getting the incident summary to understand the scope
2. Analyze the attackers to identify patterns and risk levels
3. Use semantic search to understand what narratives attackers are using

Always provide actionable insights:
- Highlight the most suspicious accounts (lowest trust scores, newest accounts)
- Note any coordination patterns (similar timing, similar text)
- Recommend next steps for the investigation

Be concise but thorough. Format your responses with clear sections when presenting multiple pieces of information.
```

#### Step 3: Assign Tools

Switch to the **Tools** tab. Select the three tools you created:

- ☑ `incident_summary`
- ☑ `reviewer_analysis`
- ☑ `similar_reviews`

You can also include built-in tools if desired:
- ☑ `platform.core.search` (optional - for general searches)

#### Step 4: Customize Appearance (Optional)

- Choose an **Avatar Color** (e.g., red for security/trust)
- Choose an **Avatar Symbol** (e.g., shield icon)

#### Step 5: Save the Agent

Click **Save** to create the agent.

---

### Task 6: Test Your Agent (2 min)

Now test your custom agent with natural language questions.

1. Click **Save and Chat** (or open the agent from the Agents list)
2. The chat interface opens with your Review Fraud Investigator agent

3. Try these investigation queries:

   **Test Incident Summary:**
   > "What can you tell me about the most recent incident?"

   > "Summarize the incident for The Golden Spoon"

   **Test Reviewer Analysis:**
   > "Analyze the attackers who targeted target_biz_001"

   > "What patterns do the attackers have in common?"

   **Test Similar Reviews (Semantic Search):**
   > "Find reviews similar to 'food poisoning made me sick'"

   > "What are the attackers claiming in their reviews?"

   **Test Multi-Step Investigation:**
   > "Investigate the latest attack - give me a full breakdown including who did it and what they're claiming"

4. Observe how the agent:
   - Understands your question
   - Selects the appropriate tool(s)
   - Chains multiple tools for complex questions
   - Formats a helpful, analyst-friendly response

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
- [ ] `review_fraud_investigator` agent is created with all three tools assigned
- [ ] Agent responds correctly to natural language queries
- [ ] You can get incident details by asking in plain English
- [ ] You can analyze attackers without writing queries manually
- [ ] You can find semantically similar reviews by describing what you're looking for

---

## Key Takeaways

1. **Tools vs Agents** - Tools are the queries; agents are the AI personalities that use them
2. **Custom Instructions** - Guide how your agent behaves and responds
3. **Natural language investigation** - Analysts can ask questions without knowing ES|QL
4. **Semantic search** - Find content by meaning, not just keywords, to understand attack narratives
5. **Multi-tool chains** - Agents can use multiple tools to answer complex questions
6. **Reusability** - Once created, agents and tools work for any incident

---

## Bonus: Additional Tools to Consider

If you have extra time, consider creating these additional tools and adding them to your agent.

**Important:** After creating each tool, you must assign it to your agent:
1. Go to **Agents** and click on your **Review Fraud Investigator** agent
2. Switch to the **Tools** tab
3. Check the box next to your new tool
4. Click **Save**

---

**Recent Incidents Tool:**
```esql
FROM incidents
| WHERE detected_at > NOW() - 24 hours
| SORT detected_at DESC
| KEEP incident_id, business_name, severity, status, detected_at
| LIMIT 10
```
- **Tool ID:** `recent_incidents`
- **Parameter:** None (or optional `hours` parameter with type `integer`)
- **Description:** Lists recent review fraud incidents from the last 24 hours. Use this when asked about recent attacks, latest incidents, or what's happening across the platform.

**Test it:** After assigning to your agent, ask: *"What attacks happened in the last 24 hours?"*

---

**Business Risk Assessment:**
```esql
FROM reviews
| WHERE business_id == "{{business_id}}"
| WHERE date > NOW() - 7 days
| LOOKUP JOIN users ON user_id
| STATS
    total_reviews = COUNT(*),
    avg_rating = AVG(stars),
    avg_trust = AVG(trust_score),
    avg_account_age = AVG(account_age_days)
| EVAL
    risk_level = CASE(
      avg_trust < 0.3 AND avg_account_age < 14, "HIGH",
      avg_trust < 0.4 AND avg_account_age < 30, "MEDIUM",
      TRUE, "LOW"
    )
```
- **Tool ID:** `business_risk_assessment`
- **Parameter:** `business_id` (type: `text`)
- **Description:** Evaluates a business's vulnerability to review fraud attacks based on recent review patterns and reviewer characteristics.

**Test it:** After assigning to your agent, ask: *"What's the risk level for business target_biz_001?"*

---

## Troubleshooting

**Tool doesn't appear when assigning to agent?**
- Ensure you clicked Save when creating the tool
- Refresh the page and try again
- Check that the Tool ID has no spaces or special characters

**Query returns no results?**
- Verify the incident/business exists in your data
- Check the time window - data may be older than expected
- Use **Save & test** to run the query directly

**Agent doesn't use the right tool?**
- Improve the tool description to be more specific
- Add example queries in the description
- Refine your agent's custom instructions

**Parameter not recognized?**
- Click **Infer parameter** to auto-detect from query
- Ensure parameter name matches `{{placeholder}}` exactly
- Check that the Type is appropriate for the value

In the next challenge, you'll run a full end-to-end attack simulation!
