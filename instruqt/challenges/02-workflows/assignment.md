# Building a Detection Workflow

## Time
20 minutes

## Objective
Build an automated workflow that detects review bomb attacks and responds in real-time using Elastic Workflows.

---

## Background

In Challenge 1, you learned to identify suspicious review patterns using ES|QL queries. But running queries manually is not practical for real-time protection. Bad actors can submit dozens of fake reviews in minutes - you need automated detection.

**Elastic Workflows** lets you:
- Run detection queries on a schedule
- Take automated actions when threats are detected
- Create audit trails and notifications

In this challenge, you'll build a workflow that:
1. Runs every 5 minutes
2. Detects businesses under review bomb attack
3. Holds suspicious reviews for manual review
4. Protects targeted businesses
5. Creates incidents for investigation

---

## The Workflow Architecture

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
5. Click **Create Workflow**

**Tip:** If you don't see Workflows, use the search bar at the top of Kibana and type "Workflows".

---

### Task 2: Configure Workflow Basics (2 min)

1. Enter the workflow details:
   - **Name:** `Review Bomb Detection`
   - **Description:** `Detects coordinated negative review attacks and protects targeted businesses`

2. Click **Add Trigger** and select **Schedule**

3. Configure the schedule:
   - **Interval:** `5` minutes
   - This means the detection runs every 5 minutes

4. Click **Save Trigger**

**What you've done:** Created a workflow that will automatically run every 5 minutes.

---

### Task 3: Add the Detection Query (5 min)

Now add the ES|QL query that identifies review bombs.

1. Click **Add Step**
2. Select **ES|QL Query**
3. Name the step: `Detect Review Bombs`

4. Enter this detection query:

```esql
FROM reviews
| WHERE date > NOW() - 30 minutes
| WHERE stars <= 2
| WHERE status != "held"
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
| EVAL severity = CASE(
    review_count >= 15, "critical",
    review_count >= 10, "high",
    TRUE, "medium"
  )
| LOOKUP JOIN businesses ON business_id
| KEEP business_id, name, city, stars AS original_rating, review_count,
       avg_stars, avg_trust, unique_attackers, severity, review_ids
| SORT review_count DESC
```

5. Click **Save Step**

**Understanding the query:**
- Looks at reviews from the last 30 minutes
- Filters for low ratings (2 stars or less) from low-trust users (<0.4)
- Groups by business and counts suspicious reviews
- Only triggers if 5+ suspicious reviews from 3+ different users
- Calculates severity based on attack volume
- Enriches with business details

---

### Task 4: Add Response Steps (8 min)

For each detected attack, we need to take protective actions. Add a **For Each** loop to process each result.

#### Step 4a: Add For Each Loop

1. Click **Add Step**
2. Select **For Each**
3. Configure:
   - **Collection:** `{{Detect Review Bombs.results}}`
   - **Item variable:** `attack`

This loop will execute the following steps for each business under attack.

#### Step 4b: Hold Suspicious Reviews

Inside the For Each loop, add a step to hold the reviews:

1. Click **Add Step** (inside the loop)
2. Select **Elasticsearch Update By Query**
3. Name: `Hold Suspicious Reviews`
4. Configure:
   - **Index:** `reviews`
   - **Query:**
   ```json
   {
     "bool": {
       "must": [
         { "term": { "business_id": "{{attack.business_id}}" } },
         { "range": { "date": { "gte": "now-30m" } } },
         { "range": { "stars": { "lte": 2 } } },
         { "range": { "trust_score": { "lt": 0.4 } } }
       ],
       "must_not": [
         { "term": { "status": "held" } }
       ]
     }
   }
   ```
   - **Script:**
   ```painless
   ctx._source.status = 'held';
   ctx._source.held_reason = 'review_bomb_detection';
   ctx._source.held_at = params.timestamp;
   ```
   - **Script params:** `{ "timestamp": "{{_timestamp}}" }`

5. Click **Save Step**

**What this does:** Marks all suspicious reviews as "held" so they don't affect the business's rating while under investigation.

#### Step 4c: Protect the Business

1. Click **Add Step** (inside the loop)
2. Select **Elasticsearch Update**
3. Name: `Enable Rating Protection`
4. Configure:
   - **Index:** `businesses`
   - **Document ID:** `{{attack.business_id}}`
   - **Document:**
   ```json
   {
     "rating_protected": true,
     "protection_reason": "review_bomb_detected",
     "protected_since": "{{_timestamp}}"
   }
   ```

5. Click **Save Step**

**What this does:** Flags the business as protected, preventing held reviews from affecting its displayed rating.

#### Step 4d: Create an Incident

1. Click **Add Step** (inside the loop)
2. Select **Elasticsearch Index**
3. Name: `Create Incident`
4. Configure:
   - **Index:** `incidents`
   - **Document:**
   ```json
   {
     "incident_id": "INC-{{attack.business_id}}-{{_execution_id}}",
     "incident_type": "review_bomb",
     "status": "open",
     "severity": "{{attack.severity}}",
     "business_id": "{{attack.business_id}}",
     "business_name": "{{attack.name}}",
     "city": "{{attack.city}}",
     "metrics": {
       "review_count": {{attack.review_count}},
       "avg_stars": {{attack.avg_stars}},
       "avg_trust": {{attack.avg_trust}},
       "unique_attackers": {{attack.unique_attackers}}
     },
     "affected_review_ids": {{attack.review_ids}},
     "detected_at": "{{_timestamp}}",
     "created_at": "{{_timestamp}}"
   }
   ```

5. Click **Save Step**

**What this does:** Creates an incident document that tracks the attack details for investigation and audit.

---

### Task 5: Add Conditional Alerting (3 min)

For critical attacks, we want to send an alert. Add conditional logic.

1. Inside the For Each loop, click **Add Step**
2. Select **Condition**
3. Name: `Check Severity`
4. Configure:
   - **Condition:** `{{attack.severity}} == "critical"`

5. In the **True** branch, click **Add Step**
6. Select **Elasticsearch Index** (to create a notification)
7. Name: `Create Critical Alert`
8. Configure:
   - **Index:** `notifications`
   - **Document:**
   ```json
   {
     "notification_type": "critical_alert",
     "priority": "critical",
     "title": "CRITICAL: Review Bomb Attack Detected",
     "message": "Business '{{attack.name}}' in {{attack.city}} is under severe attack. {{attack.review_count}} suspicious reviews from {{attack.unique_attackers}} attackers detected.",
     "business_id": "{{attack.business_id}}",
     "created_at": "{{_timestamp}}",
     "read": false
   }
   ```

9. Click **Save Step**

---

### Task 6: Save and Test the Workflow

1. Review your complete workflow structure:
   ```
   Trigger: Schedule (every 5 minutes)
   |
   +-- Step 1: Detect Review Bombs (ES|QL)
   |
   +-- Step 2: For Each (attack in results)
       |
       +-- Step 2.1: Hold Suspicious Reviews
       +-- Step 2.2: Enable Rating Protection
       +-- Step 2.3: Create Incident
       +-- Step 2.4: Check Severity (Condition)
           |
           +-- If True: Create Critical Alert
   ```

2. Click **Save Workflow**

3. To test immediately (without waiting for the schedule):
   - Click **Run Now** or **Test Workflow**
   - Review the execution log

**Expected result:** If there are no current attacks, the workflow completes but creates no incidents. In Challenge 4, you'll trigger an actual attack to see the full response.

---

## Verify Your Workflow

Run these queries to verify the workflow infrastructure is ready:

**Check that the incidents index exists:**
```esql
FROM incidents
| STATS count = COUNT(*)
```

**Check for any existing incidents:**
```esql
FROM incidents
| WHERE status == "open"
| KEEP incident_id, business_name, severity, detected_at
| SORT detected_at DESC
| LIMIT 5
```

---

## Success Criteria

Before proceeding, verify:

- [ ] Workflow is created and saved with name "Review Bomb Detection"
- [ ] Trigger is set to run every 5 minutes
- [ ] Detection query uses ES|QL with LOOKUP JOIN
- [ ] Response steps are configured: Hold reviews, Protect business, Create incident
- [ ] Conditional alerting is set up for critical severity

---

## Key Takeaways

1. **Scheduled triggers** enable continuous, automated monitoring
2. **ES|QL in workflows** lets you use the same detection logic you developed interactively
3. **For Each loops** allow you to process multiple detected threats
4. **Conditional logic** enables different responses based on severity
5. **Document creation** provides audit trails and enables further automation

---

## Troubleshooting

**Workflow doesn't appear in the list?**
- Ensure you clicked Save Workflow
- Refresh the Workflows page

**ES|QL query shows errors?**
- Check that all field names match your index mappings
- Verify the date field is named correctly (may be `date` or `@timestamp`)

**Test run shows no results?**
- This is expected if there's no attack happening
- The workflow will detect attacks when they occur

In the next challenge, you'll create Agent Builder tools for investigating incidents!

---

## Appendix: Complete Workflow YAML Definitions

If you prefer to create workflows by importing YAML directly, here are the complete definitions for all three workshop workflows.

### Workflow 1: Review Bomb Detection

This is the main detection workflow you built in this challenge.

```yaml
version: 1

name: Review Bomb Detection
description: |
  Detects coordinated review bombing attacks by analyzing review patterns.
  Identifies businesses receiving suspicious clusters of low-trust, negative reviews
  and automatically creates incidents for investigation.

  Detection Criteria:
  - recent_review_count >= 5 AND (rating_trend < -1.0 OR review_velocity > 2.0 OR suspicious_count > 3)

  Workflow Actions:
  1. Detect anomalous review patterns using ES|QL
  2. Create incidents for investigation
  3. Hold suspicious reviews
  4. Enable rating protection on affected businesses
  5. Notify stakeholders

enabled: true

config:
  elasticsearch_connector_id: "${ELASTICSEARCH_CONNECTOR_ID}"
  detection_window_minutes: 30
  min_review_count: 5
  low_trust_threshold: 0.4
  max_stars_threshold: 2

triggers:
  - type: schedule
    interval: 5m
  - type: webhook
    path: /workflow/review-bomb-detection/trigger

steps:
  # Step 1: Detect potential review bombs using ES|QL
  - id: detect_review_bombs
    type: elasticsearch.esql
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      query: |
        FROM reviews
        | WHERE @timestamp > NOW() - 30 minutes
          AND trust_score < 0.4
          AND stars <= 2
          AND status = "pending"
        | STATS
            review_count = COUNT(*),
            avg_trust_score = AVG(trust_score),
            avg_stars = AVG(stars),
            unique_reviewers = COUNT_DISTINCT(user_id),
            review_ids = MV_SORT(VALUES(review_id))
          BY business_id
        | WHERE review_count >= 5
        | LOOKUP JOIN businesses ON business_id
        | KEEP business_id, business_name, review_count, avg_trust_score,
              avg_stars, unique_reviewers, review_ids, category, city
        | SORT review_count DESC

  # Step 2: Create incidents for each detected attack
  - id: create_incidents
    type: foreach
    collection: "{{detect_review_bombs.results}}"
    as: bomb
    steps:
      - id: determine_severity
        type: if
        condition: "{{bomb.review_count > 20}}"
        then:
          - id: set_critical
            type: set
            with:
              key: severity
              value: critical
        else:
          - id: check_high_severity
            type: if
            condition: "{{bomb.review_count > 10}}"
            then:
              - id: set_high
                type: set
                with:
                  key: severity
                  value: high
            else:
              - id: set_medium
                type: set
                with:
                  key: severity
                  value: medium

      - id: create_incident_doc
        type: elasticsearch.index
        connectorId: "{{config.elasticsearch_connector_id}}"
        with:
          index: incidents
          document:
            incident_id: "INC-{{bomb.business_id}}-{{execution.started_at | date('YYYYMMDDHHmmss')}}"
            incident_type: review_bomb
            status: open
            severity: "{{severity}}"
            business_id: "{{bomb.business_id}}"
            business_name: "{{bomb.business_name}}"
            category: "{{bomb.category}}"
            city: "{{bomb.city}}"
            detection_time: "{{execution.started_at}}"
            metrics:
              review_count: "{{bomb.review_count}}"
              avg_trust_score: "{{bomb.avg_trust_score}}"
              avg_stars: "{{bomb.avg_stars}}"
              unique_reviewers: "{{bomb.unique_reviewers}}"
            affected_review_ids: "{{bomb.review_ids}}"
            created_at: "{{execution.started_at}}"

  # Step 3: Hold affected reviews for investigation
  - id: hold_reviews
    type: foreach
    collection: "{{detect_review_bombs.results}}"
    as: bomb
    steps:
      - id: update_reviews_to_held
        type: elasticsearch.update_by_query
        connectorId: "{{config.elasticsearch_connector_id}}"
        with:
          index: reviews
          query:
            bool:
              must:
                - term:
                    business_id: "{{bomb.business_id}}"
                - range:
                    "@timestamp":
                      gte: "now-30m"
                - range:
                    trust_score:
                      lt: 0.4
                - range:
                    stars:
                      lte: 2
          script:
            source: |
              ctx._source.status = 'held';
              ctx._source.held_reason = 'review_bomb_detection';
              ctx._source.held_at = params.held_at;
            params:
              held_at: "{{execution.started_at}}"

  # Step 4: Enable rating protection on affected businesses
  - id: protect_businesses
    type: foreach
    collection: "{{detect_review_bombs.results}}"
    as: bomb
    steps:
      - id: enable_rating_protection
        type: elasticsearch.update
        connectorId: "{{config.elasticsearch_connector_id}}"
        with:
          index: businesses
          id: "{{bomb.business_id}}"
          document:
            rating_protected: true
            protection_enabled_at: "{{execution.started_at}}"
            protection_reason: review_bomb_detected

  # Step 5: Create notifications
  - id: create_notifications
    type: foreach
    collection: "{{detect_review_bombs.results}}"
    as: bomb
    steps:
      - id: create_ops_notification
        type: elasticsearch.index
        connectorId: "{{config.elasticsearch_connector_id}}"
        with:
          index: notifications
          document:
            notification_id: "NOTIF-{{bomb.business_id}}-{{execution.started_at | date('YYYYMMDDHHmmss')}}"
            notification_type: review_bomb_detected
            recipient_type: operations
            priority: "{{severity}}"
            title: "Review Bomb Detected: {{bomb.business_name}}"
            message: |
              A potential review bombing attack has been detected.

              Business: {{bomb.business_name}}
              Location: {{bomb.city}}

              Attack Metrics:
              - Suspicious Reviews: {{bomb.review_count}}
              - Average Trust Score: {{bomb.avg_trust_score | round(2)}}
              - Average Stars: {{bomb.avg_stars | round(1)}}
              - Unique Attackers: {{bomb.unique_reviewers}}

              Actions Taken:
              - Reviews placed on hold
              - Business rating protection enabled
              - Incident created for investigation
            business_id: "{{bomb.business_id}}"
            created_at: "{{execution.started_at}}"
            read: false
```

---

### Workflow 2: Reviewer Flagging

This workflow automatically flags suspicious user accounts when review bomb incidents are created.

```yaml
version: 1

name: Reviewer Flagging
description: |
  Automatically flags suspicious user accounts when review bomb incidents are created.
  Analyzes the reviewers involved in detected attacks and updates their trust profiles.
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
  # Step 1: Get reviews associated with the incident
  - id: get_incident_reviews
    type: elasticsearch.esql
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      query: |
        FROM reviews
        | WHERE review_id IN ({{trigger.document.affected_review_ids | join(', ')}})
        | EVAL
            is_low_trust = trust_score < 0.4,
            is_new_account = account_age_days < 30,
            is_suspicious = is_low_trust OR is_new_account
        | KEEP review_id, user_id, trust_score, stars, created_at,
              account_age_days, is_low_trust, is_new_account, is_suspicious
        | SORT trust_score ASC

  # Step 2: Analyze suspicious users
  - id: analyze_users
    type: elasticsearch.esql
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      query: |
        FROM reviews
        | WHERE review_id IN ({{trigger.document.affected_review_ids | join(', ')}})
          AND trust_score < 0.5
        | STATS
            incident_reviews = COUNT(*),
            incident_avg_stars = AVG(stars)
          BY user_id
        | LOOKUP JOIN users ON user_id
        | EVAL
            flag_score = CASE(
              trust_score < 0.2, 1.0,
              trust_score < 0.3, 0.8,
              trust_score < 0.4, 0.6,
              0.4
            ),
            should_flag = trust_score < 0.4 OR account_age_days < 14
        | WHERE should_flag == true
        | KEEP user_id, username, trust_score, account_age_days,
              total_reviews, incident_reviews, flag_score
        | SORT flag_score DESC

  # Step 3: Flag each suspicious user
  - id: flag_users
    type: foreach
    collection: "{{analyze_users.results}}"
    as: user
    steps:
      - id: update_user_flagged
        type: elasticsearch.update
        connectorId: "{{config.elasticsearch_connector_id}}"
        with:
          index: users
          id: "{{user.user_id}}"
          document:
            flagged: true
            flagged_at: "{{execution.started_at}}"
            flag_score: "{{user.flag_score}}"
            last_incident_id: "{{trigger.document.incident_id}}"

  # Step 4: Update incident with flagged users
  - id: collect_flagged_users
    type: set
    with:
      key: flagged_user_ids
      value: "{{analyze_users.results | map('user_id')}}"

  - id: update_incident_with_users
    type: elasticsearch.update
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      index: incidents
      id: "{{trigger.document._id}}"
      document:
        flagged_user_ids: "{{flagged_user_ids}}"
        flagged_user_count: "{{flagged_user_ids | length}}"
        user_analysis_completed_at: "{{execution.started_at}}"

  # Step 5: Create notification for trust & safety team
  - id: create_ts_notification
    type: elasticsearch.index
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      index: notifications
      document:
        notification_id: "NOTIF-TS-{{trigger.document.incident_id}}"
        notification_type: users_flagged
        recipient_type: trust_safety
        priority: "{{trigger.document.severity}}"
        title: "{{flagged_user_ids | length}} Users Flagged - {{trigger.document.incident_id}}"
        message: |
          User analysis complete for incident {{trigger.document.incident_id}}.

          Business: {{trigger.document.business_name}}
          Users Flagged: {{flagged_user_ids | length}}

          Please review the flagged users and determine if additional action is needed.
        incident_id: "{{trigger.document.incident_id}}"
        created_at: "{{execution.started_at}}"
        read: false
```

---

### Workflow 3: Incident Resolution

This workflow handles the resolution of review bomb incidents, processing held reviews and restoring business rating protection.

```yaml
version: 1

name: Incident Resolution
description: |
  Handles the resolution of review bomb incidents. Processes the final
  disposition of held reviews and restores business rating protection
  based on the investigation outcome.
enabled: true

triggers:
  - type: document
    index: incidents
    filters:
      - field: status
        value: resolved
    on_update: true
    fields_changed:
      - status

steps:
  # Step 1: Get held reviews for this incident
  - id: get_held_reviews
    type: elasticsearch.esql
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      query: |
        FROM reviews
        | WHERE review_id IN ({{trigger.document.affected_review_ids | join(', ')}})
          AND status == "held"
        | KEEP review_id, user_id, business_id, stars, trust_score, held_at
        | SORT held_at ASC

  # Step 2: Process reviews based on resolution type
  - id: process_resolution
    type: if
    condition: "{{trigger.document.resolution == 'confirmed_attack'}}"
    then:
      # Confirmed Attack - Delete malicious reviews
      - id: delete_malicious_reviews
        type: foreach
        collection: "{{get_held_reviews.results}}"
        as: review
        steps:
          - id: mark_review_deleted
            type: elasticsearch.update
            connectorId: "{{config.elasticsearch_connector_id}}"
            with:
              index: reviews
              id: "{{review.review_id}}"
              document:
                status: deleted
                deletion_reason: confirmed_review_bomb
                deleted_at: "{{execution.started_at}}"
                deleted_by_incident: "{{trigger.document.incident_id}}"
    else:
      # False Positive - Publish held reviews
      - id: publish_held_reviews
        type: foreach
        collection: "{{get_held_reviews.results}}"
        as: review
        steps:
          - id: publish_review
            type: elasticsearch.update
            connectorId: "{{config.elasticsearch_connector_id}}"
            with:
              index: reviews
              id: "{{review.review_id}}"
              document:
                status: published
                published_at: "{{execution.started_at}}"
                hold_cleared_by_incident: "{{trigger.document.incident_id}}"
                hold_cleared_reason: "{{trigger.document.resolution}}"

  # Step 3: Remove business rating protection
  - id: remove_rating_protection
    type: elasticsearch.update
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      index: businesses
      id: "{{trigger.document.business_id}}"
      document:
        rating_protected: false
        protection_removed_at: "{{execution.started_at}}"
        protection_removed_reason: incident_resolved

  # Step 4: Recalculate business rating
  - id: recalculate_rating
    type: elasticsearch.esql
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      query: |
        FROM reviews
        | WHERE business_id == "{{trigger.document.business_id}}"
          AND status == "published"
        | STATS
            new_avg_rating = AVG(stars),
            new_review_count = COUNT(*)

  - id: update_business_rating
    type: elasticsearch.update
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      index: businesses
      id: "{{trigger.document.business_id}}"
      document:
        avg_rating: "{{recalculate_rating.results[0].new_avg_rating}}"
        review_count: "{{recalculate_rating.results[0].new_review_count}}"
        rating_updated_at: "{{execution.started_at}}"

  # Step 5: Create resolution notification
  - id: create_resolution_notification
    type: elasticsearch.index
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      index: notifications
      document:
        notification_id: "NOTIF-RES-{{trigger.document.incident_id}}"
        notification_type: incident_resolved
        priority: normal
        title: "Incident Resolved: {{trigger.document.incident_id}}"
        message: |
          Incident {{trigger.document.incident_id}} has been resolved.

          Business: {{trigger.document.business_name}}
          Resolution: {{trigger.document.resolution}}
          Reviews Processed: {{get_held_reviews.results | length}}

          Business rating protection has been removed.
        incident_id: "{{trigger.document.incident_id}}"
        business_id: "{{trigger.document.business_id}}"
        created_at: "{{execution.started_at}}"
        read: false

  # Step 6: Finalize incident record
  - id: finalize_incident
    type: elasticsearch.update
    connectorId: "{{config.elasticsearch_connector_id}}"
    with:
      index: incidents
      id: "{{trigger.document._id}}"
      document:
        resolution_completed_at: "{{execution.started_at}}"
        resolution_metrics:
          reviews_processed: "{{get_held_reviews.results | length}}"
          final_business_rating: "{{recalculate_rating.results[0].new_avg_rating}}"
```

---

### How to Import YAML Workflows

1. Navigate to **Kibana** > **Stack Management** > **Workflows**
2. Click **Create Workflow**
3. Click **Import YAML** (or toggle to YAML view)
4. Paste the workflow YAML
5. Click **Save**

**Note:** You may need to update the `elasticsearch_connector_id` in the config section to match your environment's connector ID.
