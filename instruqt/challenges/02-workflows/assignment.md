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
