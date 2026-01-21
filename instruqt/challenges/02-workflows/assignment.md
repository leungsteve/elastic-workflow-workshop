# Building Detection Workflows

## Time
20 minutes

## Objective
Create an automated workflow that detects review bomb attacks and responds in real-time using Elastic Workflows.

---

## Background

In Challenge 1, you learned to identify suspicious review patterns using ES|QL queries. But running queries manually isn't practical for real-time protection. Bad actors can submit dozens of fake reviews in minutes - you need automated detection.

**Elastic Workflows** lets you:
- Run detection queries on a schedule
- Take automated actions when threats are detected
- Create audit trails and notifications

In this challenge, you'll create a workflow that:
1. Runs every 5 minutes
2. Detects businesses under review bomb attack
3. Holds suspicious reviews for manual review
4. Protects targeted businesses
5. Creates incidents for investigation

> **Note:** We'll use **Dev Tools** to create workflows via API commands. This is faster than navigating the UI and lets you quickly copy/paste the workflow definitions. The `kbn://` prefix tells Dev Tools to route the request to the Kibana API instead of Elasticsearch.

---

## How Workflows Work

Workflows are defined in YAML and consist of:

| Component | Description | Example |
|-----------|-------------|---------|
| **Triggers** | When the workflow runs | Schedule (every 5 min), Document change, Webhook |
| **Steps** | What the workflow does | ES|QL queries, Updates, Conditionals |
| **Actions** | Effects on your data | Hold reviews, Create incidents, Send alerts |

```
+-------------------+     +----------------------+     +------------------+
|  Schedule Trigger |---->|  ES|QL Detection     |---->|  For Each Attack |
|  (Every 5 min)    |     |  Query               |     |                  |
+-------------------+     +----------------------+     +--------+---------+
                                                               |
                         +-------------------------------------+
                         |
         +---------------+---------------+---------------+
         |               |               |               |
         v               v               v               v
   +-----------+   +-----------+   +-----------+   +-----------+
   | Hold      |   | Protect   |   | Create    |   | Send      |
   | Reviews   |   | Business  |   | Incident  |   | Alert     |
   +-----------+   +-----------+   +-----------+   +-----------+
```

---

## Tasks

### Task 1: Enable Workflows and Open Dev Tools (2 min)

We'll use **Dev Tools** to create workflows quickly via API commands.

1. Open **Kibana** in your browser
2. Navigate to **Dev Tools** (use the search bar and type "Dev Tools")
3. First, enable the Workflows feature by running:

```
POST kbn://internal/kibana/settings
{
  "changes": {
    "workflows:ui:enabled": true
  }
}
```

You should see `{"settings":{"workflows:ui:enabled":{"userValue":true}}}` in the response.

---

### Task 2: Create the Review Bomb Detection Workflow (10 min)

Run the following command in Dev Tools to create the workflow. The API expects the workflow definition as a YAML string in the `yaml` field.

```
POST kbn://api/workflows
{
  "yaml": "name: Review Bomb Detection\ndescription: Detects coordinated review bombing attacks and automatically protects targeted businesses.\nenabled: true\ntriggers:\n  - type: scheduled\n    with:\n      every: 5m\nsteps:\n  - name: detect_review_bombs\n    type: elasticsearch.esql.query\n    with:\n      query: |\n        FROM reviews\n        | WHERE date > NOW() - 30 minutes AND stars <= 2 AND status != \"held\"\n        | LOOKUP JOIN users ON user_id\n        | WHERE trust_score < 0.4\n        | STATS review_count = COUNT(*), avg_stars = AVG(stars), avg_trust = AVG(trust_score), unique_attackers = COUNT_DISTINCT(user_id) BY business_id\n        | WHERE review_count >= 5 AND unique_attackers >= 3\n        | LOOKUP JOIN businesses ON business_id\n        | KEEP business_id, name, city, review_count, avg_stars, avg_trust, unique_attackers\n        | SORT review_count DESC\n  - name: log_detection\n    type: console\n    with:\n      message: \"Detected {{ steps.detect_review_bombs.output.values | size }} potential attacks\"\n  - name: process_attacks\n    type: foreach\n    foreach: \"{{ steps.detect_review_bombs.output.values }}\"\n    steps:\n      - name: protect_business\n        type: elasticsearch.update\n        with:\n          index: businesses\n          id: \"{{ foreach.item.business_id }}\"\n          doc:\n            rating_protected: true\n            protection_reason: review_bomb_detected\n      - name: create_incident\n        type: elasticsearch.bulk\n        with:\n          index: incidents\n          operations:\n            - incident_type: review_bomb\n              status: open\n              severity: high\n              business_id: \"{{ foreach.item.business_id }}\"\n              detected_at: \"{{ execution.startedAt }}\"\n      - name: create_notification\n        type: elasticsearch.bulk\n        with:\n          index: notifications\n          operations:\n            - type: review_bomb_detected\n              severity: high\n              title: \"Review Bomb Detected: {{ foreach.item.name }}\"\n              business_id: \"{{ foreach.item.business_id }}\"\n              read: false\n  - name: completion_log\n    type: console\n    with:\n      message: Review bomb detection workflow completed"
}
```

> **Note:** The workflow YAML is passed as a single string. In a real workflow editor, you'd paste the YAML directly into the editor UI instead of using the API.

The response will include the workflow ID - save this for later:
```json
{
  "id": "workflow-abc123",
  "name": "Review Bomb Detection",
  ...
}
```

---

### Task 3: Understand the Workflow Structure (5 min)

Let's break down each section of the workflow:

#### Metadata
```yaml
name: Review Bomb Detection
description: |
  Detects coordinated review bombing attacks...
enabled: true
```
- `name`: Display name in the UI
- `description`: Explains what the workflow does
- `enabled`: Set to `true` to activate the workflow

#### Trigger
```yaml
triggers:
  - type: scheduled
    with:
      every: 5m
```
- `type: scheduled` runs automatically at intervals
- `every: 5m` means every 5 minutes
- Other trigger types: `manual` (on-demand), `alert` (from detection rules)

#### Detection Query (ES|QL)
```yaml
- name: detect_review_bombs
  type: elasticsearch.esql.query
  with:
    query: |
      FROM reviews
      | WHERE @timestamp > NOW() - 30 minutes
      | LOOKUP JOIN users ON user_id
      ...
```
- `name:` identifies the step (used for referencing output)
- `type: elasticsearch.esql.query` runs an ES|QL query
- Access results via `{{ steps.detect_review_bombs.output.values }}`

#### For Each Loop
```yaml
- name: process_attacks
  type: foreach
  foreach: "{{ steps.detect_review_bombs.output.values }}"
  steps:
    ...
```
- `type: foreach` iterates over an array
- `foreach:` specifies what to iterate (reference previous step output)
- Inside the loop, access current item with `{{ foreach.item }}`
- Access index with `{{ foreach.index }}`

#### Response Actions
Each action in the loop:
1. **log_attack** - Logs what's being processed (type: `console`)
2. **protect_business** - Updates business document (type: `elasticsearch.update`)
3. **create_incident** - Indexes incident document (type: `elasticsearch.bulk`)
4. **create_notification** - Creates alert (type: `elasticsearch.bulk`)

#### Template Variables
Access data using Liquid-style templates:
- `{{ steps.step_name.output }}` - Previous step results
- `{{ foreach.item.field }}` - Current loop item field
- `{{ execution.startedAt }}` - When workflow started
- `{{ execution.id }}` - Unique execution ID

---

### Task 4: Verify and Test the Workflow (3 min)

**List all workflows to verify it was created:**
```
POST kbn://api/workflows/search
{
  "limit": 20,
  "page": 1,
  "query": ""
}
```

You should see your "Review Bomb Detection" workflow in the results.

**Execute the workflow manually (without waiting 5 minutes):**
```
POST kbn://api/workflows/<workflow-id>/execute
{}
```

Replace `<workflow-id>` with the ID returned when you created the workflow.

**Check execution status:**
```
GET kbn://api/workflows/<workflow-id>/executions
```

**Expected result:** If there are no current attacks, the workflow completes but the foreach loop has no items to process. This is normal - in Challenge 4, you'll trigger an actual attack to see the full response.

---

## Verify Your Workflow

Run these queries in Dev Tools to verify the workflow is ready:

**Check that the incidents index exists:**
```
POST /_query?format=txt
{
  "query": "FROM incidents | STATS count = COUNT(*)"
}
```

**Check notifications index exists:**
```
POST /_query?format=txt
{
  "query": "FROM notifications | STATS count = COUNT(*)"
}
```

**List workflows again to confirm:**
```
POST kbn://api/workflows/search
{
  "limit": 20,
  "page": 1,
  "query": "Review Bomb"
}
```

---

## Success Criteria

Before proceeding, verify:

- [ ] Workflow YAML is pasted into the editor
- [ ] Workflow is enabled (toggle is on)
- [ ] Workflow is saved successfully
- [ ] Test run completes without errors
- [ ] You understand the trigger, detection, and response sections

---

## Key Takeaways

1. **YAML-based definition** - Workflows are defined declaratively in YAML
2. **ES|QL integration** - Use the same detection queries you developed in Challenge 1
3. **For Each loops** - Process multiple detected threats in a single execution
4. **Multiple actions** - A single detection can trigger hold, protect, incident, and notify
5. **Scheduled execution** - Continuous monitoring without manual intervention

---

## Troubleshooting

**"workflows:ui:enabled" setting doesn't work?**
- Make sure you're using `kbn://internal/kibana/settings` (not `kbn://api/...`)
- The response should show `{"settings":{"workflows:ui:enabled":{"userValue":true}}}`

**Workflow creation fails?**
- Check JSON syntax (proper quotes, commas, brackets)
- Ensure all required fields are present (`name`, `triggers`, `steps`)
- Look for error messages in the response

**Test run shows errors?**
- Check that index names match your environment (reviews, users, businesses, incidents, notifications)
- Verify the ES|QL query syntax is correct
- Check field names match your index mappings

**No results on test run?**
- This is expected if there's no attack happening
- The foreach loop simply processes zero items
- In Challenge 4, you'll trigger an attack to see the full flow

**"404 Not Found" on workflow endpoints?**
- Make sure you ran the enable command first: `POST kbn://internal/kibana/settings`
- Use `kbn://` prefix for all Kibana API calls in Dev Tools

---

## Bonus: Simple Manual Workflow

If you have extra time, create a simple manual workflow to understand the basics.

### Business Health Check Workflow

This workflow runs on-demand to check for businesses that might be under attack.

```
POST kbn://api/workflows
{
  "yaml": "name: Business Health Check\ndescription: Manual check for businesses with suspicious review activity\nenabled: true\ntriggers:\n  - type: manual\nsteps:\n  - name: find_suspicious_activity\n    type: elasticsearch.esql.query\n    with:\n      query: |\n        FROM reviews\n        | WHERE date > NOW() - 1 hour AND stars <= 2\n        | LOOKUP JOIN users ON user_id\n        | WHERE trust_score < 0.4\n        | STATS suspicious_count = COUNT(*), avg_trust = AVG(trust_score) BY business_id\n        | WHERE suspicious_count >= 3\n        | LOOKUP JOIN businesses ON business_id\n        | KEEP business_id, name, suspicious_count, avg_trust\n        | SORT suspicious_count DESC\n        | LIMIT 10\n  - name: log_results\n    type: console\n    with:\n      message: \"Health check complete. Found {{ steps.find_suspicious_activity.output.values | size }} businesses with suspicious activity.\"\n  - name: alert_on_suspicious\n    type: foreach\n    foreach: \"{{ steps.find_suspicious_activity.output.values }}\"\n    steps:\n      - name: log_business\n        type: console\n        with:\n          message: \"WARNING: {{ foreach.item.name }} has {{ foreach.item.suspicious_count }} suspicious reviews\""
}
```

**To test this workflow:**
1. Copy the workflow ID from the response
2. Execute it manually:
```
POST kbn://api/workflows/<workflow-id>/execute
{}
```
3. Check the execution results:
```
GET kbn://api/workflows/<workflow-id>/executions
```

---

## Available Step Types

Here are the key step types you can use in workflows:

| Step Type | Description |
|-----------|-------------|
| `elasticsearch.esql.query` | Run ES\|QL queries |
| `elasticsearch.search` | Run DSL search queries |
| `elasticsearch.update` | Update a document by ID |
| `elasticsearch.bulk` | Bulk index/update/delete |
| `elasticsearch.delete` | Delete a document |
| `elasticsearch.request` | Generic ES API call |
| `console` | Log messages |
| `foreach` | Loop over arrays |
| `if` | Conditional logic |
| `wait` | Pause execution |
| `http.get` | HTTP GET request |

---

## Available Trigger Types

| Trigger Type | Description |
|--------------|-------------|
| `manual` | Run on-demand via UI or API |
| `scheduled` | Run at intervals using `every:` (e.g., `5m`, `1h`, `1d`) |
| `alert` | Triggered by detection rules |

---

In the next challenge, you'll create Agent Builder tools for investigating incidents!
