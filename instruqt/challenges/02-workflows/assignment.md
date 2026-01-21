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
version: 1

name: Review Bomb Detection
description: |
  Detects coordinated review bombing attacks and automatically
  protects targeted businesses by holding suspicious reviews.
enabled: true

triggers:
  - type: schedule
    interval: 5m

steps:
  # Step 1: Detect potential review bombs using ES|QL
  - id: detect_review_bombs
    type: elasticsearch.esql
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
            unique_attackers = COUNT_DISTINCT(user_id),
            review_ids = VALUES(review_id)
          BY business_id
        | WHERE review_count >= 5 AND unique_attackers >= 3
        | LOOKUP JOIN businesses ON business_id
        | KEEP business_id, name, city, review_count, avg_stars,
              avg_trust, unique_attackers, review_ids
        | SORT review_count DESC

  # Step 2: Process each detected attack
  - id: process_attacks
    type: foreach
    collection: "{{detect_review_bombs.results}}"
    as: attack
    steps:
      # Calculate severity based on attack volume
      - id: set_severity
        type: set
        with:
          key: severity
          value: |
            {{#if (gt attack.review_count 20)}}critical
            {{else if (gt attack.review_count 10)}}high
            {{else}}medium{{/if}}

      # Hold the suspicious reviews
      - id: hold_reviews
        type: elasticsearch.update_by_query
        with:
          index: reviews
          query:
            bool:
              must:
                - term:
                    business_id: "{{attack.business_id}}"
                - range:
                    "@timestamp":
                      gte: "now-30m"
                - range:
                    stars:
                      lte: 2
              must_not:
                - term:
                    status: "held"
          script:
            source: |
              ctx._source.status = 'held';
              ctx._source.held_reason = 'review_bomb_detection';
              ctx._source.held_at = params.timestamp;
            params:
              timestamp: "{{execution.started_at}}"

      # Enable rating protection on the business
      - id: protect_business
        type: elasticsearch.update
        with:
          index: businesses
          id: "{{attack.business_id}}"
          document:
            rating_protected: true
            protection_reason: "review_bomb_detected"
            protected_since: "{{execution.started_at}}"

      # Create an incident record
      - id: create_incident
        type: elasticsearch.index
        with:
          index: incidents
          document:
            incident_id: "INC-{{attack.business_id}}-{{execution.id}}"
            incident_type: "review_bomb"
            status: "open"
            severity: "{{severity}}"
            business_id: "{{attack.business_id}}"
            business_name: "{{attack.name}}"
            city: "{{attack.city}}"
            detected_at: "{{execution.started_at}}"
            metrics:
              review_count: "{{attack.review_count}}"
              avg_stars: "{{attack.avg_stars}}"
              avg_trust: "{{attack.avg_trust}}"
              unique_attackers: "{{attack.unique_attackers}}"
            affected_review_ids: "{{attack.review_ids}}"
            created_at: "{{execution.started_at}}"

      # Create a notification
      - id: create_notification
        type: elasticsearch.index
        with:
          index: notifications
          document:
            notification_id: "NOTIF-{{attack.business_id}}-{{execution.id}}"
            type: "review_bomb_detected"
            severity: "{{severity}}"
            title: "Review Bomb Detected: {{attack.name}}"
            message: |
              Detected {{attack.review_count}} suspicious reviews
              from {{attack.unique_attackers}} attackers targeting
              {{attack.name}} in {{attack.city}}.
            business_id: "{{attack.business_id}}"
            created_at: "{{execution.started_at}}"
            read: false
```

---

### Task 3: Understand the Workflow Structure (5 min)

Let's break down each section of the workflow:

#### Metadata
```yaml
version: 1
name: Review Bomb Detection
description: |
  Detects coordinated review bombing attacks...
enabled: true
```
- `version`: Workflow schema version
- `name`: Display name in the UI
- `enabled`: Set to `true` to activate the workflow

#### Trigger
```yaml
triggers:
  - type: schedule
    interval: 5m
```
- Runs automatically every 5 minutes
- Other trigger types: `document` (on index change), `webhook` (HTTP call)

#### Detection Query
```yaml
- id: detect_review_bombs
  type: elasticsearch.esql
  with:
    query: |
      FROM reviews
      | WHERE @timestamp > NOW() - 30 minutes
      | LOOKUP JOIN users ON user_id
      ...
```
- Uses the same ES|QL + LOOKUP JOIN pattern from Challenge 1
- Finds businesses with 5+ low-trust negative reviews from 3+ different users
- Returns the business details and list of suspicious review IDs

#### For Each Loop
```yaml
- id: process_attacks
  type: foreach
  collection: "{{detect_review_bombs.results}}"
  as: attack
```
- Iterates over each detected attack
- `{{attack.business_id}}` accesses fields from the current item

#### Response Actions
Each action in the loop:
1. **set_severity** - Calculates severity (critical/high/medium) based on volume
2. **hold_reviews** - Updates review status to "held" via update_by_query
3. **protect_business** - Sets `rating_protected: true` on the business
4. **create_incident** - Indexes a new incident document
5. **create_notification** - Creates an alert for the operations team

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

## Bonus: Additional Workflows

If you have extra time, here are two more workflows you can create. These trigger automatically based on document changes rather than a schedule.

### Reviewer Flagging Workflow

This workflow triggers when a new incident is created and flags the suspicious users involved.

```yaml
version: 1

name: Reviewer Flagging
description: Flags suspicious users when incidents are created
enabled: true

triggers:
  - type: document
    index: incidents
    filters:
      - field: incident_type
        value: review_bomb
      - field: status
        value: open

steps:
  - id: get_attackers
    type: elasticsearch.esql
    with:
      query: |
        FROM reviews
        | WHERE review_id IN ({{trigger.document.affected_review_ids}})
        | LOOKUP JOIN users ON user_id
        | WHERE trust_score < 0.4
        | KEEP user_id, trust_score, account_age_days
        | STATS count = COUNT(*) BY user_id, trust_score, account_age_days

  - id: flag_users
    type: foreach
    collection: "{{get_attackers.results}}"
    as: user
    steps:
      - id: update_user_flag
        type: elasticsearch.update
        with:
          index: users
          id: "{{user.user_id}}"
          document:
            flagged: true
            flagged_at: "{{execution.started_at}}"
            flag_reason: "review_bomb_participant"
            last_incident_id: "{{trigger.document.incident_id}}"
```

---

### Incident Resolution Workflow

This workflow triggers when an incident is marked as resolved and cleans up accordingly.

```yaml
version: 1

name: Incident Resolution
description: Processes resolved incidents - deletes or publishes held reviews
enabled: true

triggers:
  - type: document
    index: incidents
    on_update: true
    filters:
      - field: status
        value: resolved

steps:
  - id: check_resolution
    type: if
    condition: "{{trigger.document.resolution == 'confirmed_attack'}}"
    then:
      # Delete malicious reviews
      - id: delete_reviews
        type: elasticsearch.update_by_query
        with:
          index: reviews
          query:
            terms:
              review_id: "{{trigger.document.affected_review_ids}}"
          script:
            source: |
              ctx._source.status = 'deleted';
              ctx._source.deleted_at = params.timestamp;
            params:
              timestamp: "{{execution.started_at}}"
    else:
      # False positive - publish the reviews
      - id: publish_reviews
        type: elasticsearch.update_by_query
        with:
          index: reviews
          query:
            terms:
              review_id: "{{trigger.document.affected_review_ids}}"
          script:
            source: |
              ctx._source.status = 'published';
              ctx._source.published_at = params.timestamp;
            params:
              timestamp: "{{execution.started_at}}"

  # Remove business protection
  - id: remove_protection
    type: elasticsearch.update
    with:
      index: businesses
      id: "{{trigger.document.business_id}}"
      document:
        rating_protected: false
        protection_removed_at: "{{execution.started_at}}"

  # Create resolution notification
  - id: notify_resolution
    type: elasticsearch.index
    with:
      index: notifications
      document:
        notification_id: "NOTIF-RES-{{trigger.document.incident_id}}"
        type: "incident_resolved"
        title: "Incident Resolved: {{trigger.document.business_name}}"
        message: "Resolution: {{trigger.document.resolution}}"
        incident_id: "{{trigger.document.incident_id}}"
        created_at: "{{execution.started_at}}"
        read: false
```

---

In the next challenge, you'll create Agent Builder tools for investigating incidents!
