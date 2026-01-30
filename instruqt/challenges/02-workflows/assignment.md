# Building Detection Workflows

## Time
20 minutes

## Theme Focus: SIMPLIFY + OPTIMIZE
> **SIMPLIFY:** Build automation visually—no code required.
> **OPTIMIZE:** Automated 24/7 detection eliminates manual monitoring costs.

## Objective
Create an automated workflow that detects negative review campaign attacks and responds in real-time using Elastic Workflows.

---

## Background

In Challenge 1, you learned to identify suspicious review patterns using ES|QL queries. But running queries manually isn't practical for real-time protection. Bad actors can submit dozens of fake reviews in minutes - you need automated detection.

**Elastic Workflows** lets you:
- Run detection queries on a schedule
- Take automated actions when threats are detected
- Create audit trails and notifications

In this challenge, you'll create a workflow that:
1. Runs every 1 minute
2. Detects businesses under negative review campaign attack
3. Holds suspicious reviews for manual review
4. Protects targeted businesses
5. Creates incidents for investigation

---

## How Workflows Work

Workflows are defined in YAML and consist of:

| Component | Description | Example |
|-----------|-------------|---------|
| **Triggers** | When the workflow runs | Schedule (every 1 min), Document change, Webhook |
| **Steps** | What the workflow does | ES|QL queries, Updates, Conditionals |
| **Actions** | Effects on your data | Hold reviews, Create incidents, Send alerts |

```
+-------------------+     +----------------------+     +------------------+
|  Schedule Trigger |---->|  ES|QL Detection     |---->|  For Each Attack |
|  (Every 1 min)    |     |  Query               |     |                  |
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

### Task 1: Open the Workflows App (2 min)

1. Open **Kibana** in your browser
2. In the left navigation, click the **Workflows** icon (or use the search bar and type "Workflows")
3. You should see the Workflows management page

If Workflows doesn't appear in the navigation, it may need to be enabled:
1. Go to **Dev Tools** (search bar > "Dev Tools")
2. Run this command to enable the feature:
```
POST kbn://internal/kibana/settings
{
  "changes": {
    "workflows:ui:enabled": true
  }
}
```
3. Refresh the page and navigate to Workflows

---

### Task 2: Create the Negative Review Campaign Detection Workflow (10 min)

1. In the Workflows app, click **Create a new workflow**
2. You'll see a YAML editor. **Delete any placeholder content** and paste the following workflow definition:

```yaml
name: Negative Review Campaign Detection
description: Detects coordinated review bombing attacks and automatically protects targeted businesses.
enabled: true

triggers:
  - type: scheduled
    with:
      every: 1m

steps:
  - name: detect_review_bombs
    type: elasticsearch.esql.query
    with:
      query: |
        FROM reviews
        | WHERE date > NOW() - 30 minutes AND stars <= 2 AND status != "held"
        | LOOKUP JOIN users ON user_id
        | WHERE trust_score < 0.4
        | STATS review_count = COUNT(*), avg_stars = AVG(stars), avg_trust = AVG(trust_score), unique_attackers = COUNT_DISTINCT(user_id) BY business_id
        | WHERE review_count >= 5 AND unique_attackers >= 3
        | LOOKUP JOIN businesses ON business_id
        | KEEP business_id, name, city, review_count, avg_stars, avg_trust, unique_attackers
        | SORT review_count DESC

  - name: log_detection
    type: console
    with:
      message: "Detected {{ steps.detect_review_bombs.output.values | size }} potential attacks"

  # ES|QL results are arrays: [business_id, name, city, review_count, avg_stars, avg_trust, unique_attackers]
  - name: process_attacks
    type: foreach
    foreach: "{{ steps.detect_review_bombs.output.values }}"
    steps:
      - name: hold_reviews
        type: elasticsearch.request
        with:
          method: POST
          path: /reviews/_update_by_query
          body:
            query:
              bool:
                must:
                  - term:
                      business_id: "{{ foreach.item[0] }}"
                  - range:
                      date:
                        gte: "now-30m"
                  - range:
                      stars:
                        lte: 2
                filter:
                  - term:
                      status: pending
            script:
              source: "ctx._source.status = 'held'"

      - name: protect_business
        type: elasticsearch.request
        with:
          method: POST
          path: /businesses/_update_by_query
          body:
            query:
              term:
                business_id: "{{ foreach.item[0] }}"
            script:
              source: "ctx._source.rating_protected = true; ctx._source.protection_reason = 'review_bomb_detected'"

      - name: create_incident
        type: elasticsearch.request
        with:
          method: POST
          path: /incidents/_doc
          body:
            incident_type: review_bomb
            status: detected
            severity: high
            business_id: "{{ foreach.item[0] }}"
            business_name: "{{ foreach.item[1] }}"
            detected_at: "{{ execution.startedAt }}"
            metrics:
              review_count: "{{ foreach.item[3] }}"
              average_rating: "{{ foreach.item[4] }}"
              avg_trust: "{{ foreach.item[5] }}"
              unique_attackers: "{{ foreach.item[6] }}"

      - name: create_notification
        type: elasticsearch.request
        with:
          method: POST
          path: /notifications/_doc
          body:
            type: review_bomb_detected
            severity: high
            title: "Negative Review Campaign Detected: {{ foreach.item[1] }}"
            business_id: "{{ foreach.item[0] }}"
            read: false

  - name: completion_log
    type: console
    with:
      message: Negative review campaign detection workflow completed
```

3. Click **Save** to create the workflow
4. Note the workflow ID shown in the URL or workflow details - you'll need it for testing

---

### Task 3: Understand the Workflow Structure (5 min)

Let's break down each section of the workflow:

#### Metadata
```yaml
name: Negative Review Campaign Detection
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
      every: 1m
```
- `type: scheduled` runs automatically at intervals
- `every: 1m` means every 1 minute
- Other trigger types: `manual` (on-demand), `alert` (from detection rules)

#### Detection Query (ES|QL)
```yaml
- name: detect_review_bombs
  type: elasticsearch.esql.query
  with:
    query: |
      FROM reviews
      | WHERE date > NOW() - 30 minutes
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
1. **hold_reviews** - Sets suspicious reviews to "held" status via `_update_by_query` (type: `elasticsearch.request`)
2. **protect_business** - Flags business as protected via `_update_by_query` (type: `elasticsearch.request`)
3. **create_incident** - Indexes incident document (type: `elasticsearch.request`)
4. **create_notification** - Creates alert (type: `elasticsearch.request`)

#### Template Variables
Access data using Liquid-style templates:
- `{{ steps.step_name.output }}` - Previous step results
- `{{ foreach.item[0] }}` - First column of current ES|QL row (ES|QL returns arrays)
- `{{ execution.startedAt }}` - When workflow started
- `{{ execution.id }}` - Unique execution ID

**Note:** ES|QL query results are arrays of arrays (rows), so use index notation like `foreach.item[0]` for the first column, `foreach.item[1]` for the second, etc.

---

### Task 4: Verify and Test the Workflow (3 min)

**Verify the workflow was created:**
1. In the Workflows app, you should see "Negative Review Campaign Detection" in the list
2. Click on the workflow to view its details
3. Verify the status shows "Enabled"

**Execute the workflow manually (without waiting for the next scheduled run):**
1. Click on your workflow to open it
2. Click the **Run** button (or "Execute" / "Test")
3. Watch the execution progress

**Check execution history:**
1. In the workflow details, look for an "Executions" or "History" tab
2. You should see your manual execution listed
3. Click on it to see the step-by-step results

**Expected result:** If there are no current attacks, the workflow completes but the foreach loop has no items to process. This is normal - in Challenge 4, you'll trigger an actual attack to see the full response.

---

## Verify Your Workflow

Verify the workflow is ready by checking the indices in **Discover** (ES|QL mode):

**Check that the incidents index exists:**
```esql
FROM incidents | STATS count = COUNT(*)
```

**Check notifications index exists:**
```esql
FROM notifications | STATS count = COUNT(*)
```

These indices may show 0 documents initially - that's expected. They'll be populated when the workflow detects an actual attack.

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

**Workflows not visible in navigation?**
- Go to Dev Tools and run: `POST kbn://internal/kibana/settings` with `{"changes": {"workflows:ui:enabled": true}}`
- Refresh the page

**Workflow creation fails?**
- Check YAML syntax (proper indentation, quotes)
- Ensure all required fields are present (`name`, `triggers`, `steps`)
- Look for error messages in the editor

**Test run shows errors?**
- Check that index names match your environment (reviews, users, businesses, incidents, notifications)
- Verify the ES|QL query syntax is correct
- Check field names match your index mappings

**No results on test run?**
- This is expected if there's no attack happening
- The foreach loop simply processes zero items
- In Challenge 4, you'll trigger an attack to see the full flow

---

## Bonus: Simple Manual Workflow

If you have extra time, create a simple manual workflow to understand the basics.

### Business Health Check Workflow

This workflow runs on-demand to check for businesses that might be under attack.

1. In the Workflows app, click **Create a new workflow**
2. Paste this YAML:

```yaml
name: Business Health Check
description: Manual check for businesses with suspicious review activity
enabled: true

triggers:
  - type: manual

steps:
  - name: find_suspicious_activity
    type: elasticsearch.esql.query
    with:
      query: |
        FROM reviews
        | WHERE date > NOW() - 1 hour AND stars <= 2
        | LOOKUP JOIN users ON user_id
        | WHERE trust_score < 0.4
        | STATS suspicious_count = COUNT(*), avg_trust = AVG(trust_score) BY business_id
        | WHERE suspicious_count >= 3
        | LOOKUP JOIN businesses ON business_id
        | KEEP business_id, name, suspicious_count, avg_trust
        | SORT suspicious_count DESC
        | LIMIT 10

  - name: log_results
    type: console
    with:
      message: "Health check complete. Found {{ steps.find_suspicious_activity.output.values | size }} businesses with suspicious activity."

  # ES|QL results are arrays: [business_id, name, suspicious_count, avg_trust]
  - name: alert_on_suspicious
    type: foreach
    foreach: "{{ steps.find_suspicious_activity.output.values }}"
    steps:
      - name: log_business
        type: console
        with:
          message: "WARNING: {{ foreach.item[1] }} has {{ foreach.item[2] }} suspicious reviews"
```

3. Click **Save**
4. Click **Run** to execute it manually
5. Check the execution results to see any suspicious activity

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
| `scheduled` | Run at intervals using `every:` (e.g., `1m`, `5m`, `1h`, `1d`) |
| `alert` | Triggered by detection rules |

---

In the next challenge, you'll create Agent Builder tools for investigating incidents!
