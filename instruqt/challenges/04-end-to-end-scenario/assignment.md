# End-to-End Fraud Simulation

## Time
15 minutes

## Theme Focus: ALL THREE
> **SIMPLIFY:** Readable detection queries | **OPTIMIZE:** Automated instant response | **INNOVATE WITH AI:** Natural language investigation

## Objective
Run a complete fraud simulation to see your detection workflow, automated responses, and investigation tools working together in real-time.

---

## Background

You've built all the pieces:
- **Challenge 1:** ES|QL queries to detect suspicious patterns + semantic search
- **Challenge 2:** Automated workflow to respond to attacks
- **Challenge 3:** Agent Builder tools and a custom **Review Campaign Investigator** agent

Now it's time to put everything together and watch the system in action.

In this challenge, you will:
1. Verify a target business's baseline state
2. Launch a simulated negative review campaign
3. Watch your workflow detect and respond automatically
4. Use your custom agent to investigate the incident
5. Resolve the incident and restore normal operations

This simulates how your system would protect real businesses from coordinated attacks.

---

## The Attack Lifecycle

```
+-------------+     +-------------+     +-------------+     +-------------+
|  1. NORMAL  |---->|  2. ATTACK  |---->|  3. DETECT  |---->|  4. RESPOND |
|  Baseline   |     |  Begins     |     |  Workflow   |     |  Auto-hold  |
+-------------+     +-------------+     +-------------+     +-------------+
                                                                   |
+-------------+     +-------------+     +-------------+            |
|  7. NORMAL  |<----|  6. RESOLVE |<----|  5. INVEST- |<-----------+
|  Restored   |     |  Incident   |     |  IGATE      |
+-------------+     +-------------+     +-------------+
```

---

## Tasks

> **Target Business:** This challenge uses **Reading Terminal Market** (`ytynqOUb3hjKeJfRj5Tshw`), a famous Philadelphia landmark with a 4.5 star rating and 5,700+ reviews - a realistic high-value target for attackers.

### Open the ElasticEats Consumer UI

Before we begin, open the **ElasticEats** consumer interface - this is a Yelp-like UI where you can browse businesses and see reviews just like a real user would.

1. Open **ElasticEats** in a new browser tab: `http://localhost:8000/elasticeats`
2. Search for "Reading Terminal Market" or browse the **Restaurants** category
3. Click on **Reading Terminal Market** to view its business page
4. Keep this tab open - you'll use it throughout this challenge to see the attack unfold visually

**Direct link to target business:** `http://localhost:8000/elasticeats/biz/ytynqOUb3hjKeJfRj5Tshw`

---

### Task 1: Check Baseline State (2 min)

Before the attack, verify the target business is in a normal state.

1. Open **Kibana** and navigate to **Discover**, then select **ES|QL** mode

2. Check the target business:
   ```esql
   FROM businesses
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | KEEP business_id, name, city, stars, review_count, rating_protected
   ```

   **Expected result:**
   - Name: "Reading Terminal Market"
   - Rating: 4.5 stars
   - `rating_protected`: false (not under protection)

3. Verify no active incidents exist for this business:
   ```esql
   FROM incidents
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw" AND status == "detected"
   | STATS count = COUNT(*)
   ```

   **Expected result:** count = 0

4. Check recent review activity:
   ```esql
   FROM reviews
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | WHERE date > NOW() - 1 hour
   | STATS total = COUNT(*), avg_stars = AVG(stars) BY status
   ```

   **Expected result:** Little to no recent activity (likely 0 results)

**What you've verified:** The business is operating normally with no ongoing attacks.

---

### Task 2: Launch the Attack (3 min)

Now you'll launch a simulated negative review campaign against the target business.

1. Open the **Attack Simulator** tab
   - URL: `http://localhost:8000/attack` or use the "Attack Simulator" tab in Instruqt

2. Configure the attack:

   | Setting | Value |
   |---------|-------|
   | **Target Business** | Reading Terminal Market |
   | **Business ID** | `ytynqOUb3hjKeJfRj5Tshw` |
   | **Number of Reviews** | 15 |
   | **Rating Range** | 1-2 stars |
   | **Attacker Profiles** | Low trust (0.1-0.3) |

3. Click **Launch Attack**

4. **Watch the attack in ElasticEats:**
   - Switch to your ElasticEats tab with Reading Terminal Market
   - **Refresh the page** to see the attack reviews appear
   - Notice the negative reviews with **SIMULATED** badges
   - See the **Low Trust** badges on attacker accounts
   - Check the "Recent Activity (24h)" sidebar - review count and velocity spike

5. Monitor with this query (run every 30 seconds):
   ```esql
   FROM reviews
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | WHERE date > NOW() - 10 minutes
   | LOOKUP JOIN users ON user_id
   | STATS total = COUNT(*), avg_stars = AVG(stars), avg_trust = AVG(trust_score)
   ```

   **What to watch for:** Review count climbing, average stars dropping, average trust score low (below 0.4 indicates attackers).

---

### Task 3: Watch Workflow Detection (3 min)

Your workflow should detect the attack automatically. Let's observe it in action.

1. Navigate to **Workflows** in Kibana

2. Find your **Negative Review Campaign Detection** workflow

3. Click on the workflow to see its details and execution history

4. Wait for the next scheduled execution (runs every 1 minute)
   - Or click the **Play/Run** button to trigger immediately

5. Watch the execution steps:
   - Detection query runs and finds suspicious pattern
   - For Each loop processes the detected attack
   - Reviews are held
   - Business is protected
   - Incident is created

6. **See the response in ElasticEats:**
   - Switch to your ElasticEats tab and **refresh the page**
   - You should now see:
     - **"Rating Protected"** badge in the business header
     - **Orange incident alert banner** below the header
     - Attack reviews now show **"HELD"** badges with yellow background
     - The 4.5 star rating is preserved (protected from the attack!)

7. Verify the response with these queries:

   **Check held reviews:**
   ```esql
   FROM reviews
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | WHERE status == "held"
   | WHERE date > NOW() - 30 minutes
   | STATS held_count = COUNT(*)
   ```

   **Expected result:** Multiple reviews now held

   **Check business protection:**
   ```esql
   FROM businesses
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | KEEP name, rating_protected, protection_reason, protected_since
   ```

   **Expected result:** `rating_protected`: true

   **Check incident creation:**
   ```esql
   FROM incidents
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | WHERE status == "detected"
   | KEEP incident_id, severity, metrics.review_count, metrics.unique_attackers, detected_at
   ```

   **Expected result:** New incident with attack details

---

### Task 4: Investigate with Your Custom Agent (5 min)

Now use the **Review Campaign Investigator** agent you created in Challenge 3 to understand the attack.

1. Open **Agent Builder** and select your **Review Campaign Investigator** agent
   - Or click **Chat** next to your agent in the Agents list

2. Ask about the incident:
   ```
   What can you tell me about the latest incident?
   ```

   or

   ```
   Summarize the incident for Reading Terminal Market
   ```

3. Review the incident summary - you should see:
   - Business name and location
   - Severity level
   - Number of suspicious reviews
   - Number of unique attackers
   - Impact assessment

4. Analyze the attackers:
   ```
   Analyze the attackers who targeted ytynqOUb3hjKeJfRj5Tshw in the last hour
   ```

5. Review the attacker profiles:
   - Low trust scores
   - New accounts
   - Risk levels

6. **Use semantic search to understand the attack narrative:**

   ```
   Find reviews similar to 'food poisoning made me sick'
   ```

   ```
   What are the attackers claiming in their reviews?
   ```

   This uses the `similar_reviews` tool to find reviews by meaning. You'll discover the common themes attackers use - health complaints, service issues, food quality claims.

7. **Compare attack reviews to legitimate reviews:**

   ```
   Find reviews similar to 'great food and excellent service'
   ```

   Notice how legitimate reviews have different themes - genuine positive experiences versus the manufactured negative narratives from attackers.

8. Ask follow-up questions:
   ```
   What patterns do these attackers have in common?
   ```

   ```
   Were any of these accounts involved in previous attacks?
   ```

   ```
   What would be the rating impact if these reviews were published?
   ```

9. Generate an investigation summary:
   ```
   Generate an incident report for the attack on Reading Terminal Market
   ```

---

### Task 5: Resolve the Incident (3 min)

Complete the incident lifecycle by resolving it.

1. Review the held reviews in Kibana:
   ```esql
   FROM reviews
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | WHERE status == "held"
   | KEEP review_id, user_id, stars, text, date
   | SORT date DESC
   | LIMIT 15
   ```

2. Confirm they are malicious by checking patterns:
   - Similar negative text
   - Low ratings (1-2 stars)
   - Recent timestamps clustered together
   - Different users but same attack characteristics

3. Take resolution actions. In a real system, you would:
   - **Delete** the malicious reviews (or keep them held permanently)
   - **Flag** the attacker accounts for suspension
   - **Update** the incident status to "resolved"

4. Update the incident status:

   First, find the incident ID:
   ```esql
   FROM incidents
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw" AND status == "detected"
   | KEEP incident_id
   | LIMIT 1
   ```

   Then update via the API (in Terminal):
   ```bash
   curl -X POST "${ELASTICSEARCH_URL}/incidents/_update_by_query" \
     -H "Content-Type: application/json" \
     -d '{
       "query": {
         "bool": {
           "must": [
             { "term": { "business_id": "ytynqOUb3hjKeJfRj5Tshw" } },
             { "term": { "status": "detected" } }
           ]
         }
       },
       "script": {
         "source": "ctx._source.status = '\''resolved'\''; ctx._source.resolved_at = params.timestamp; ctx._source.resolution = params.notes",
         "params": {
           "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
           "notes": "Confirmed negative review campaign. Malicious reviews held. Attacker accounts flagged."
         }
       }
     }'
   ```

5. Optionally, remove protection from the business:
   ```bash
   curl -X POST "${ELASTICSEARCH_URL}/businesses/_update/ytynqOUb3hjKeJfRj5Tshw" \
     -H "Content-Type: application/json" \
     -d '{
       "doc": {
         "rating_protected": false,
         "protection_reason": null
       }
     }'
   ```

6. Verify the resolution:
   ```esql
   FROM incidents
   | WHERE business_id == "ytynqOUb3hjKeJfRj5Tshw"
   | SORT detected_at DESC
   | LIMIT 1
   | KEEP incident_id, status, severity, resolved_at, resolution
   ```

   **Expected result:** status = "resolved"

---

## Congratulations!

You've completed a full attack lifecycle:

1. **Detected** - ES|QL queries identified suspicious review patterns
2. **Correlated** - LOOKUP JOIN enriched reviews with user trust data
3. **Automated** - Workflow responded in real-time without human intervention
4. **Protected** - Suspicious reviews held, business rating preserved
5. **Understood** - Semantic search revealed attack narratives and themes
6. **Investigated** - Agent Builder provided natural language analysis
7. **Resolved** - Incident documented and closed

---

## Success Criteria

Verify you have completed all phases:

- [ ] Opened ElasticEats and viewed the target business
- [ ] Checked baseline state of target business
- [ ] Launched attack via simulator
- [ ] Saw attack reviews appear in ElasticEats (SIMULATED badges)
- [ ] Observed workflow detection and response
- [ ] Saw protection badge and held reviews in ElasticEats
- [ ] Reviews were automatically held
- [ ] Business was automatically protected
- [ ] Incident was automatically created
- [ ] Used Agent Builder to investigate
- [ ] Used semantic search to understand attack narratives
- [ ] Compared attack themes to legitimate review themes
- [ ] Resolved the incident with documentation

---

## Key Takeaways

1. **Real-time protection** - Workflows can respond in minutes, not hours
2. **Visual feedback** - ElasticEats UI shows protection badges and held reviews instantly
3. **Minimal false positives** - Multiple signals (trust score, rating, volume) reduce errors
4. **Business continuity** - Rating protection prevents immediate reputation damage
5. **Semantic understanding** - ELSER reveals what attackers claim, beyond just keywords
6. **Audit trail** - Incidents and held reviews provide compliance documentation
7. **Natural language access** - Analysts don't need to be ES|QL experts

---

## What's Next?

This pattern applies to many use cases beyond negative review campaigns:

| Use Case | Detection | Response | Investigation |
|----------|-----------|----------|---------------|
| **Fraud Detection** | Transaction velocity, amount anomalies | Block account, hold transactions | User behavior analysis |
| **Security Ops** | Failed logins, suspicious IPs | Lock account, alert SOC | Attack source analysis |
| **Compliance** | Policy violations, data access | Hold data, notify compliance | Access pattern review |
| **Content Moderation** | Spam patterns, toxic content | Hide content, flag user | Content trend analysis |

---

## Workshop Complete!

Thank you for participating in the Negative Review Campaign Detection Workshop.

**What you learned:**
- ES|QL with LOOKUP JOIN for cross-index correlation
- Semantic search with ELSER to understand content by meaning
- Elastic Workflows for automated detection and response
- Agent Builder for natural language investigation

**Key message:** *Search finds the insight. Semantic search reveals the meaning. Workflows acts on it. Agent Builder explains it.*

For more information:
- [Elastic Workflows Documentation](https://www.elastic.co/guide/en/workflows/)
- [ES|QL Reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/esql.html)
- [Agent Builder Guide](https://www.elastic.co/guide/en/agent-builder/)
