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

### Task 1: Navigate to Workflows (2 min)

1. Open **Kibana** in your browser
2. Click the hamburger menu (three lines) in the top left
3. Navigate to **Management** > **Stack Management**
4. In the left sidebar, find and click **Workflows**
5. Click **Create workflow**

**Tip:** If you don't see Workflows, use the search bar at the top of Kibana and type "Workflows".

You'll see a YAML editor where you can define your workflow.

---

### Task 2: Create the Review Bomb Detection Workflow (10 min)

Copy the following YAML into the editor. We'll walk through each section to understand what it does.

```yaml
name: Review Bomb Detection
description: |
  Detects coordinated review bombing attacks and automatically
  protects targeted businesses by holding suspicious reviews.
enabled: true

triggers:
  - type: scheduled
    with:
      every: 5m

steps:
  # Step 1: Detect potential review bombs using ES|QL
  - name: detect_review_bombs
    type: elasticsearch.esql.query
    with:
      query: |
        FROM reviews
        | WHERE @timestamp > NOW() - 30 minutes
          AND stars <= 2
          AND status != "held"
        | LOOKUP JOIN users ON user_id
        | WHERE trust_score < 0.4
        | STATS
            review_count = COUNT(*),
            avg_stars = AVG(stars),
            avg_trust = AVG(trust_score),
            unique_attackers = COUNT_DISTINCT(user_id)
          BY business_id
        | WHERE review_count >= 5 AND unique_attackers >= 3
        | LOOKUP JOIN businesses ON business_id
        | KEEP business_id, name, city, review_count, avg_stars,
              avg_trust, unique_attackers
        | SORT review_count DESC

  # Step 2: Log what was detected
  - name: log_detection
    type: console
    with:
      message: "Detected potential attacks"

  # Step 3: Process each detected attack
  - name: process_attacks
    type: foreach
    foreach: "{{ steps.detect_review_bombs.output.values }}"
    steps:
      # Log current attack being processed
      - name: log_attack
        type: console
        with:
          message: "Processing attack"

      # Enable rating protection on the business
      - name: protect_business
        type: elasticsearch.update
        with:
          index: businesses
          id: "{{ foreach.item.business_id }}"
          doc:
            rating_protected: true
            protection_reason: review_bomb_detected

      # Create an incident record
      - name: create_incident
        type: elasticsearch.bulk
        with:
          index: incidents
          operations:
            - incident_type: review_bomb
              status: open
              severity: high
              detected_at: "{{ execution.startedAt }}"

      # Create a notification
      - name: create_notification
        type: elasticsearch.bulk
        with:
          index: notifications
          operations:
            - type: review_bomb_detected
              severity: high
              title: "Review Bomb Detected"
              read: false

  # Step 4: Final summary
  - name: completion_log
    type: console
    with:
      message: "Review bomb detection workflow completed"
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

### Task 4: Save and Test the Workflow (3 min)

1. **Enable the workflow** using the toggle at the top of the editor

2. Click **Save**

3. To test immediately (without waiting 5 minutes):
   - Click the **Play button** (Run/Test) to execute the workflow now
   - Review the execution log to see each step

4. **Expected result:** If there are no current attacks, the workflow completes but the foreach loop has no items to process. This is normal - in Challenge 4, you'll trigger an actual attack to see the full response.

---

## Verify Your Workflow

Run these queries in Dev Tools to verify the workflow is ready:

**Check that the incidents index exists:**
```esql
FROM incidents
| STATS count = COUNT(*)
```

**Check the workflow saved correctly:**
Navigate to Workflows list - you should see "Review Bomb Detection" with status "Enabled".

**Check notifications index exists:**
```esql
FROM notifications
| STATS count = COUNT(*)
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

**Workflow doesn't save?**
- Check YAML syntax (proper indentation, no tabs)
- Ensure all required fields are present
- Look for error messages at the bottom of the editor

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

```yaml
name: Business Health Check
description: Manual check for businesses with suspicious review activity
enabled: true

triggers:
  - type: manual

steps:
  # Query for suspicious activity
  - name: find_suspicious_activity
    type: elasticsearch.esql.query
    with:
      query: |
        FROM reviews
        | WHERE @timestamp > NOW() - 1 hour
        | WHERE stars <= 2
        | LOOKUP JOIN users ON user_id
        | WHERE trust_score < 0.4
        | STATS
            suspicious_count = COUNT(*),
            avg_trust = AVG(trust_score)
          BY business_id
        | WHERE suspicious_count >= 3
        | LOOKUP JOIN businesses ON business_id
        | KEEP business_id, name, suspicious_count, avg_trust
        | SORT suspicious_count DESC
        | LIMIT 10

  # Log the results
  - name: log_results
    type: console
    with:
      message: |
        Health check complete.
        Found {{ steps.find_suspicious_activity.output.values | size }} businesses with suspicious activity.

  # Process each suspicious business
  - name: alert_on_suspicious
    type: foreach
    foreach: "{{ steps.find_suspicious_activity.output.values }}"
    steps:
      - name: log_business
        type: console
        with:
          message: "WARNING: {{ foreach.item.name }} has {{ foreach.item.suspicious_count }} suspicious reviews (avg trust: {{ foreach.item.avg_trust }})"
```

**To test this workflow:**
1. Save the workflow
2. Click **Save & test** or the Play button
3. View the console output to see results

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
