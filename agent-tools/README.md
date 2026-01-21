# Agent Builder Tools for Review Bomb Detection

This directory contains tool definitions for Elastic's Agent Builder feature. These tools enable AI-powered investigation of review bomb attacks using ES|QL queries.

**Key Message:** *"Search finds the insight. Workflows acts on it. Agent Builder explains it."*

## Overview

Agent Builder tools allow the AI assistant to query Elasticsearch data and provide intelligent analysis of review bomb incidents. Each tool is defined as a JSON file containing:

- Tool name and description (helps the AI know when to use it)
- Input parameters with descriptions
- ES|QL query with parameter substitution (`{{ param }}` syntax)
- Output field descriptions for result interpretation

## Available Tools

### 1. incident-summary.json
**Purpose:** Get a comprehensive overview of a specific review bomb incident.

**Use Cases:**
- Understanding what happened to a business
- Getting attack metrics and timeline
- Checking incident status and resolution

**Parameters:**
- `incident_id` (required): The incident ID (e.g., "INC-abc123")

**Example Prompts:**
- "Tell me about incident INC-12345"
- "What happened in the review bomb attack on Joe's Pizza?"
- "Summarize the latest incident"

---

### 2. reviewer-pattern-analysis.json
**Purpose:** Analyze patterns among reviewers to identify coordination and attack signatures.

**Use Cases:**
- Detecting fake account patterns
- Identifying coordinated attack behavior
- Understanding attacker profiles

**Parameters:**
- `incident_id` (required): The incident ID to analyze

**Example Prompts:**
- "Analyze the reviewers involved in incident INC-12345"
- "Who attacked Joe's Pizza? Are they fake accounts?"
- "Show me the attacker patterns for the latest incident"
- "Were the attackers using new accounts?"

---

### 3. business-health-check.json
**Purpose:** Assess a business's current review health and risk profile.

**Use Cases:**
- Checking if a business is under attack
- Monitoring recovery after an incident
- Identifying businesses at risk

**Parameters:**
- `business_id` (required): The business ID to assess
- `days_back` (optional): Number of days to analyze (default: 7)

**Example Prompts:**
- "Check the health of business biz_12345"
- "Is Joe's Pizza still under attack?"
- "How is the restaurant recovering after the review bomb?"
- "Show me the review health for the past 14 days"

---

### 4. attack-timeline.json
**Purpose:** Generate a chronological timeline of attack events.

**Use Cases:**
- Understanding how an attack unfolded
- Identifying attack phases and peaks
- Correlating with external events

**Parameters:**
- `incident_id` (required): The incident ID to generate timeline for

**Example Prompts:**
- "Show me the timeline for incident INC-12345"
- "When did the attack peak?"
- "How did the review bomb unfold over time?"
- "Were there multiple waves of attacks?"

---

### 5. recent_incidents.json
**Purpose:** List recent review bomb incidents for triage and monitoring.

**Use Cases:**
- Dashboard overview of incidents
- Finding incidents needing attention
- Filtering by status

**Parameters:**
- `status` (optional): Filter by status ("open", "resolved", "all")
- `limit` (optional): Maximum results (default: 10)

**Example Prompts:**
- "Show me open incidents"
- "List recent review bombs"
- "What incidents need attention?"

---

### 6. business_risk_assessment.json
**Purpose:** Quick risk assessment based on recent 7-day activity.

**Parameters:**
- `business_id` (required): The business ID to assess

**Example Prompts:**
- "What's the risk level for business biz_12345?"
- "Is this business at risk of attack?"

---

### 7. similar-reviews.json
**Purpose:** Find reviews semantically similar to a given phrase using ELSER - the AI understands meaning, not just keywords.

**Use Cases:**
- Discovering coordinated attack patterns where attackers use similar language
- Finding reviews with matching themes, sentiment, or talking points
- Identifying template-based fake reviews even with varied wording
- Investigating specific complaint patterns (e.g., "food poisoning" claims)
- Uncovering attack campaigns with consistent messaging

**How It Helps Investigation:**
Attackers often coordinate their messaging, using similar phrases, themes, or templates. This tool uses **semantic search** (via the `:` operator on `text_semantic`) to find reviews with similar *meaning*, even if they use different words. For example, searching "terrible service slow food" will also find "waited forever, staff was rude" because they share semantic similarity.

**Parameters:**
- `search_text` (required): The phrase to search for semantically
- `business_id` (optional): Limit search to a specific business
- `limit` (optional): Maximum results to return (default: 10)

**Example Prompts:**
- "Find reviews similar to 'food poisoning made me sick'"
- "Search for reviews about terrible service and rude staff"
- "Are there reviews like 'worst experience ever' for business MTSW4McQd7CbVtyjqoe9mw?"
- "Find reviews semantically similar to 'scam ripoff stay away'"
- "Search for reviews that talk about health code violations"

---

## Deploying Tools to Kibana Agent Builder

### Prerequisites
- Elasticsearch 8.x or later with ES|QL support
- Kibana with Agent Builder feature enabled
- Appropriate permissions to create Agent Builder tools

### Deployment Steps

1. **Navigate to Agent Builder** in Kibana:
   ```
   Management > Stack Management > Agent Builder
   ```

2. **Create a new tool** for each JSON file:
   - Click "Create Tool"
   - Enter the tool name from the JSON file
   - Copy the description
   - Add each parameter with its type and description
   - Paste the ES|QL query in the query field
   - Save the tool

3. **Test the tool** using the preview feature:
   - Provide sample parameter values
   - Verify the query executes correctly
   - Check that output fields are populated

4. **Enable the tool** for your AI assistant:
   - Go to Assistant Settings
   - Enable the newly created tools
   - Test with example prompts

### Using the API

You can also deploy tools programmatically:

```bash
# Example: Deploy incident-summary tool via API
curl -X POST "https://your-kibana:5601/api/agent_builder/tools" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d @agent-tools/incident-summary.json
```

## Tool Schema Reference

```json
{
  "name": "tool_name",
  "description": "Clear description of what the tool does and when to use it",
  "parameters": {
    "param_name": {
      "type": "string|integer|boolean",
      "description": "What this parameter is for",
      "required": true|false,
      "default": "optional default value"
    }
  },
  "esql": "FROM index | WHERE field == \"{{ param_name }}\" | STATS ...",
  "output_fields": {
    "field_name": "Description of what this output field contains"
  }
}
```

## ES|QL Query Tips

1. **Parameter Substitution:** Use `{{ param_name }}` syntax for dynamic values
2. **JOIN Operations:** Use `LOOKUP JOIN` to combine data from multiple indices
3. **Aggregations:** Use `STATS` with `BY` for grouping
4. **Filtering:** Use `WHERE` clauses with date ranges like `NOW() - 7 days`
5. **Computed Fields:** Use `EVAL` to create derived fields and percentages

## Best Practices

1. **Descriptive Names:** Use clear, action-oriented tool names
2. **Helpful Descriptions:** Include use cases in descriptions so the AI knows when to apply each tool
3. **Parameter Documentation:** Describe expected formats and examples
4. **Output Interpretation:** Document output fields to help the AI explain results
5. **Analysis Tips:** Include thresholds and interpretation guidance

## Related Resources

- ES|QL queries: `../queries/`
- Index mappings: `../mappings/`
- Workflow definitions: `../workflows/`
