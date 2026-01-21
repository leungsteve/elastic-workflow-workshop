# Review Bomb Detection Workshop - Talk Track

## Speaker Notes and Demo Script

**Workshop Duration:** 90 minutes
- Presentation & Demo: 30 minutes
- Hands-on Labs: 60 minutes

**Key Message:** "Search finds the insight - ES|QL detects the anomaly, semantic search reveals the narrative. Workflows acts on it. Agent Builder explains it."

---

## Section 1: Introduction (5 minutes)

### Slide: Welcome

**Time:** 0:00 - 1:00

**Key Points:**
- Welcome everyone to the workshop
- Introduce yourself and any co-facilitators
- Confirm participants have access to their lab environments
- Quick overview: 30 min presentation, then 60 min hands-on

**Say:**
> "Welcome to 'What's New in Elastic Search 9.3.' Today we're going to build a complete review bomb detection system using powerful new features: Workflows, ES|QL with LOOKUP JOIN, Semantic Search with ELSER, and Agent Builder."

**Do:**
- Ask participants to raise hands if they've used Elasticsearch before
- Gauge ES|QL familiarity

---

### Slide: Today's Key Message

**Time:** 1:00 - 2:00

**Key Points:**
- Introduce the core theme that ties everything together
- This message will be reinforced throughout
- Emphasize the two types of search working together

**Say:**
> "Here's the key message I want you to take away today: Search finds the insight - but search comes in two flavors. ES|QL detects the anomaly through metadata patterns - velocity, trust scores, timing. Semantic search reveals the narrative - what attackers are actually claiming. Workflows acts on the insight - automating the response. And Agent Builder explains it - enabling natural language investigation. By the end of this workshop, you'll see how these four capabilities work together seamlessly."

---

### Slide: The Problem - Review Bombing

**Time:** 2:00 - 3:30

**Key Points:**
- Define review bombing
- Make it relatable with real examples
- Set up why this matters

**Say:**
> "Let me start with a question - has anyone heard of review bombing? It's a coordinated attack where bad actors create multiple fake accounts and flood a business with negative reviews. The goal is simple: destroy a business's reputation."

**Engagement:**
- Ask if anyone has personally seen this happen
- Mention high-profile cases (games, restaurants during controversies)

**Do:**
- Show the screenshot of a business with a sudden rating drop

---

### Slide: Real-World Impact

**Time:** 3:30 - 4:30

**Key Points:**
- Quantify the business impact
- Explain platform risks

**Say:**
> "The impact is very real. Studies show businesses can lose 5-9% of revenue for each star they drop. For a restaurant doing a million dollars a year, that's $50,000 to $90,000. For platforms, it's about trust - if users see fake reviews everywhere, they stop trusting the platform entirely."

---

### Slide: The Attack Pattern

**Time:** 4:30 - 5:00

**Key Points:**
- Walk through how attacks actually work
- Set up the detection challenge

**Say:**
> "The attack pattern is pretty consistent. Attackers identify a successful business - usually one with good ratings that depends on reviews. They create fake accounts, often many at once. Then they submit coordinated negative reviews, typically all 1-star, within a short time window. The business rating plummets before anyone notices."

**Transition:**
> "So how do we detect this? That's what we're building today - and we'll use two complementary search approaches to do it."

---

## Section 2: Elastic 9.3 Features (10 minutes)

### Slide: Headline Feature - Workflows

**Time:** 5:00 - 6:30

**Key Points:**
- Workflows is THE headline feature for 9.3
- Native automation - no external tools needed

**Say:**
> "The headline feature for Elastic Search 9.3 is Workflows. This is native automation built directly into Elasticsearch. No more external orchestration tools. No more moving data out of the cluster for processing. You can now build complete automated pipelines that respond to your data in real-time."

**Do:**
- Show the Workflows UI screenshot
- Point out key elements

---

### Slide: What Are Workflows?

**Time:** 6:30 - 8:00

**Key Points:**
- Define components: Triggers, Steps, Actions
- Compare to familiar concepts

**Say:**
> "Think of Workflows like AWS Lambda or Azure Functions, but built into Elastic. You have Triggers - things that start the workflow like a schedule or a document change. You have Steps - queries and transformations. And you have Actions - updates, notifications, API calls. The key difference is your data never leaves the cluster."

---

### Slide: Workflow Pattern

**Time:** 8:00 - 9:00

**Key Points:**
- Show the YAML structure
- Emphasize simplicity

**Say:**
> "Here's what a workflow looks like. It's YAML-based, declarative, and readable. A schedule trigger, an ES|QL query for detection, and an action to respond. This particular workflow detects suspicious review patterns and marks those reviews as held. Simple, powerful, native."

---

### Slide: Why Workflows Matter

**Time:** 9:00 - 9:30

**Key Points:**
- Before/after comparison
- Architecture simplification

**Say:**
> "Before Workflows, you'd need external tools - maybe Kafka for streaming, Lambda for processing, custom integrations to write back to Elastic. Now, all of that happens inside the cluster. Simpler architecture, lower latency, easier to maintain."

---

### Slide: ES|QL with LOOKUP JOIN

**Time:** 9:30 - 10:30

**Key Points:**
- This is the detection engine
- Cross-index correlation is key

**Say:**
> "ES|QL is our analytical detection engine. But here's the challenge: reviews don't contain user trust scores. That data is in a separate users index. LOOKUP JOIN lets us correlate across indices at query time. Now I can ask: show me reviews from the last 30 minutes, enriched with user trust scores, grouped by business. If a business has many reviews from low-trust users, that's our signal."

**Do:**
- Walk through the query on screen
- Explain each clause

---

### Slide: Why LOOKUP JOIN

**Time:** 10:30 - 11:00

**Key Points:**
- Solve the data correlation problem
- Enable anomaly detection across related data

**Say:**
> "Without LOOKUP JOIN, you'd have to denormalize everything into one index - which means data duplication and staleness issues. Or you'd have to do multiple queries and join in application code. LOOKUP JOIN gives you real-time correlation at query time. This is essential for any anomaly detection across related entities."

---

### Slide: Semantic Search with ELSER

**Time:** 11:00 - 12:00

**Key Points:**
- Introduce semantic search as complementary to ES|QL
- The `semantic_text` field type
- ELSER model for embeddings

**Say:**
> "ES|QL finds anomalies in metadata - velocity, trust scores, timing. But what about the content itself? That's where semantic search comes in. With ELSER - the Elastic Learned Sparse EncodeR - we can understand what reviews actually mean, not just match keywords. The `semantic_text` field type makes this simple: just mark a field as semantic, and Elasticsearch automatically generates embeddings at index time."

**Do:**
- Show the mapping with `semantic_text` field type
- Explain automatic inference

---

### Slide: Why Semantic Search Matters

**Time:** 12:00 - 12:30

**Key Points:**
- Content understanding vs. metadata patterns
- Revealing the attack narrative
- Finding similar legitimate complaints

**Say:**
> "Here's why this matters for fraud detection: attackers often use similar language - they're copying from a template or following a script. Semantic search can find reviews with similar meaning even when the words are different. And critically, it lets us ask: are there legitimate reviews with the same complaints? That's how we distinguish a real problem from a coordinated attack."

**Transition:**
> "So we have two types of search working together: ES|QL detects the anomaly through patterns, semantic search reveals what attackers are claiming."

---

### Slide: Agent Builder

**Time:** 12:30 - 13:30

**Key Points:**
- AI-powered investigation
- Custom tools with ES|QL backend
- Semantic search tools for content analysis

**Say:**
> "Once we detect an incident, someone needs to investigate. That's where Agent Builder comes in. You create custom tools - powered by ES|QL queries and semantic search - and the AI assistant can use them to answer natural language questions. Instead of writing queries, an analyst can simply ask: 'Tell me about the incident at Mario's Pizza' or 'Find reviews similar to this complaint.'"

---

### Slide: Agent Builder in Action

**Time:** 13:30 - 15:00

**Key Points:**
- Show the flow: question -> tool -> query -> answer
- Highlight both analytical and semantic tools

**Say:**
> "Here's how it works. The user asks a natural language question. The Agent selects the appropriate tool you created. The tool executes an ES|QL query or semantic search. The Agent formats the response naturally. The analyst never needs to write a query - they just ask questions. And with semantic search tools, they can ask things like 'find similar reviews' or 'what complaints are people making?'"

**Transition:**
> "Now let's see all of this in action."

---

## Section 3: Live Demo (15 minutes)

### Slide: Our Demo Scenario

**Time:** 15:00 - 15:30

**Key Points:**
- Introduce the dataset
- Set the scene

**Say:**
> "We have a review platform with real Yelp data - over 10,000 restaurants, 50,000 user accounts, 200,000 reviews. We're going to target a popular restaurant in Las Vegas and launch a review bomb attack. Then we'll watch our automated defenses respond - and use semantic search to understand what the attackers are claiming."

---

### Slide: The Data Model

**Time:** 15:30 - 16:00

**Key Points:**
- Quick overview of indices
- Focus on relationships
- Mention semantic field

**Say:**
> "Four key indices: businesses with ratings, users with trust scores, reviews linking them together, and incidents for tracking detections. The trust score is calculated from user activity - account age, review count, usefulness votes, and so on. Notice that the review text field is a `semantic_text` type - this enables semantic search out of the box."

---

### Slide: Trust Score Calculation

**Time:** 16:00 - 17:00

**Key Points:**
- Explain what makes a user trustworthy
- Contrast with attacker profiles

**Say:**
> "Low trust scores - below 0.3 - typically mean new accounts with few reviews and no engagement. High trust scores - above 0.7 - are established reviewers who've been active for years with lots of useful content. Attackers almost always have low trust scores because they're using fresh accounts."

---

### Demo: Exploring the Data

**Time:** 17:00 - 19:00

**Do:**
1. Open Kibana Dev Tools
2. Run: `FROM businesses | STATS count = COUNT(*)`
3. Show the count (around 10K)
4. Run: `FROM users | STATS avg_trust = AVG(trust_score), min_trust = MIN(trust_score), max_trust = MAX(trust_score)`
5. Show the trust score distribution

**Say:**
> "Let me show you the data. We have about 10,000 businesses... and our users have trust scores ranging from very low to very high. Most legitimate users cluster around 0.5 to 0.7."

---

### Demo: Detection Query

**Time:** 19:00 - 21:00

**Do:**
1. Copy the detection query to Dev Tools
2. Walk through each line before running
3. Run the query (should return no results if no attack)

**Say:**
> "Here's our ES|QL detection query - this is the analytical search. We look at reviews in the last 30 minutes. We JOIN with users to get trust scores. We aggregate by business - counting reviews, averaging stars and trust. Then we filter: if a business has more than 10 reviews AND those reviews average less than 2 stars AND the reviewers have low trust scores, that's suspicious. Right now, no results - no attacks in progress."

---

### Demo: The Workflow

**Time:** 21:00 - 23:00

**Do:**
1. Navigate to Workflows in Kibana
2. Open the Review Bomb Detection workflow
3. Walk through the structure

**Say:**
> "Here's the workflow that runs every 5 minutes. First, it runs our detection query. For each suspicious business found, it holds the reviews, protects the business rating, creates an incident, and sends notifications. All automated, all native."

---

### Demo: Launching the Attack

**Time:** 23:00 - 25:00

**Do:**
1. Open the workshop web application
2. Search for a target business (4.5 stars)
3. Note the current rating
4. Generate and submit 15 attack reviews rapidly
5. Watch the recent reviews panel update

**Say:**
> "Let's launch an attack. I'll select this restaurant - currently 4.5 stars, very successful. I'll generate some fake reviews... and submit them rapidly. Watch the recent reviews panel - you can see them appearing with 'pending' status."

**Tip:**
- Use "Turbo Attack" button if available for dramatic effect

---

### Demo: Workflow Response

**Time:** 25:00 - 26:00

**Do:**
1. Either wait for scheduled execution or trigger manually
2. Show the workflow execution history
3. Show reviews changing to "held" status
4. Show business now has "rating_protected: true"
5. Show the incident in the incidents index

**Say:**
> "Now watch the workflow respond. It's detected the anomaly... reviews are being marked as held... the business rating is protected... and an incident has been created. All within seconds of the attack."

**Query to verify:**
```sql
FROM reviews
| WHERE business_id == "[TARGET_ID]"
| WHERE date > NOW() - 10 minutes
| STATS count = COUNT(*) BY status
```

---

### Demo: Semantic Search - Revealing the Attack Narrative

**Time:** 26:00 - 27:30

**Do:**
1. Open Dev Tools or the web application
2. Run a semantic search query on the held reviews
3. Show the common themes/language patterns

**Say:**
> "ES|QL detected the anomaly through metadata - velocity and trust scores. But what are these attackers actually claiming? Let's use semantic search to find out."

**Query:**
```json
POST reviews/_search
{
  "query": {
    "semantic": {
      "field": "text",
      "query": "food poisoning sick health violation"
    }
  },
  "_source": ["text", "stars", "user_id", "status"],
  "size": 5
}
```

**Say:**
> "Look at this - the attackers are all claiming food poisoning and health issues. This is the attack narrative. They're not just leaving bad reviews; they're making specific allegations designed to scare customers away."

**Key Insight:**
> "Now here's the critical question: are these legitimate complaints, or is this a coordinated attack? Let's check if there are similar complaints from high-trust users."

**Query:**
```sql
FROM reviews
| WHERE stars <= 2
| LOOKUP JOIN users ON user_id
| WHERE trust_score > 0.7
| LIMIT 100
```

**Say:**
> "When we look at low-star reviews from trusted users, we don't see these food poisoning claims. That tells us this is a fabricated narrative, not a real problem. Semantic search revealed what ES|QL couldn't - the content of the attack."

---

### Demo: Investigation with Agent Builder

**Time:** 27:30 - 29:00

**Do:**
1. Open AI Assistant in Kibana
2. Ask: "What incidents were detected recently?"
3. Ask: "Summarize the incident for [business name]"
4. Ask: "Find reviews similar to the attack reviews"
5. Ask: "Are there legitimate reviews with similar complaints?"

**Say:**
> "Now I need to investigate. Instead of writing queries, I'll just ask. 'What incidents were detected recently?' The Agent finds the incident. 'Summarize it for me.' It gives me the details - including what the attackers are claiming. 'Find similar reviews.' It uses semantic search to find related content. 'Are there legitimate reviews with similar complaints?' It compares against high-trust user reviews. This is the power of combining analytical and semantic search."

---

### Demo: Resolution

**Time:** 29:00 - 30:00

**Do:**
1. Mark incident as resolved (confirmed_attack)
2. Show that reviews are deleted
3. Show that business protection is removed

**Say:**
> "To resolve, I mark it as a confirmed attack. The resolution workflow triggers - deleting the malicious reviews, removing the rating protection, notifying the business owner. The business rating is restored to its true value."

**Transition:**
> "That's the complete flow. ES|QL detected the anomaly. Semantic search revealed the narrative. Workflows automated the response. Agent Builder enabled investigation. Now it's your turn to build this."

---

## Section 4: Hands-On Preview (5 minutes)

### Slide: Your Challenges

**Time:** 30:00 - 31:00

**Key Points:**
- Walk through the four challenges
- Set time expectations

**Say:**
> "You have four challenges. First, explore the data and write detection queries - 15 minutes. Second, build the workflow - this is the main challenge, 20 minutes. Third, create Agent Builder tools including a semantic search tool - 10 minutes. Finally, the end-to-end scenario where you'll launch your own attack - 15 minutes."

---

### Slide: Challenge Overviews

**Time:** 31:00 - 33:00

**Walk through each challenge briefly:**

**Challenge 1:**
> "You'll explore the indices, understand trust scores, and write a detection query with LOOKUP JOIN."

**Challenge 2:**
> "You'll create a workflow from scratch - schedule trigger, detection step, response actions."

**Challenge 3:**
> "You'll create Agent Builder tools including both analytical and semantic search tools. One to analyze incidents, one to find similar reviews."

**Challenge 4:**
> "You'll launch an attack, watch everything you built respond automatically, and use semantic search to understand what the attackers claimed."

---

### Slide: Accessing Your Environment

**Time:** 33:00 - 34:00

**Do:**
1. Show the lab URL
2. Walk through the interface
3. Confirm everyone has access

**Say:**
> "Your lab URL is on screen. You'll see tabs for Kibana, the web application, and instructions. Take a moment now to confirm you can access your environment. Raise your hand if you need help."

**Wait for confirmation**

---

### Slide: Tips for Success

**Time:** 34:00 - 35:00

**Key Points:**
- Don't rush
- Copy/paste queries
- Ask for help

**Say:**
> "A few tips: Read the instructions carefully. Copy and paste the provided queries - they're there to help you. If you get stuck, raise your hand. Understanding is more important than completion. And experiment - try variations on the queries and semantic searches to see what happens."

---

### Slide: Questions Before We Begin

**Time:** 35:00 - 37:00 (includes buffer)

**Do:**
- Take 2-3 questions
- Address any access issues

**Say:**
> "Any questions before we start the hands-on portion?"

---

## Hands-On Facilitation Notes

### Challenge 1: Getting to Know Your Data (15 minutes)

**Common Issues:**
- Syntax errors in ES|QL - remind about pipe characters
- Confusion about LOOKUP JOIN syntax
- Questions about trust score ranges
- Confusion about semantic_text field type

**Checkpoints:**
- At 5 minutes: Most should have run basic counts
- At 10 minutes: Should be working on trust score analysis
- At 14 minutes: Give 1-minute warning

**Help Prompts:**
- "Make sure you have a pipe before each clause"
- "LOOKUP JOIN goes right after FROM or a WHERE"
- "The threshold values are suggestions - feel free to experiment"
- "The semantic_text field handles embeddings automatically - you just query it naturally"

---

### Challenge 2: Workflows (20 minutes)

**Common Issues:**
- Finding the Workflows UI location
- YAML indentation
- Variable interpolation syntax

**Checkpoints:**
- At 5 minutes: Should have created workflow and set trigger
- At 12 minutes: Should have detection step working
- At 18 minutes: Should be adding response actions

**Help Prompts:**
- "Workflows is under Management > Stack Management"
- "Watch the indentation - YAML is sensitive to spaces"
- "Use double curly braces for variable interpolation"

---

### Challenge 3: Agent Builder (10 minutes)

**Common Issues:**
- Tool parameter syntax
- ES|QL query in JSON format
- Semantic search query format
- Testing the agent

**Checkpoints:**
- At 5 minutes: Should have first tool created
- At 8 minutes: Should be testing with Agent

**Help Prompts:**
- "Parameters go in a JSON object"
- "The ES|QL query is a string value"
- "For semantic search tools, use the semantic query DSL"
- "Try asking 'What tools do you have?' to see if it recognizes your tool"
- "Try 'find similar reviews' to test the semantic search tool"

---

### Challenge 4: End-to-End Scenario (15 minutes)

**Common Issues:**
- Workflow not triggering (timing)
- Web UI access
- Incident resolution steps
- Understanding semantic search results

**Checkpoints:**
- At 3 minutes: Should have submitted attack reviews
- At 8 minutes: Should see workflow execution
- At 12 minutes: Should be investigating with Agent and semantic search

**Help Prompts:**
- "The workflow runs every 5 minutes - you can trigger it manually"
- "Refresh the web UI to see updated statuses"
- "Resolution is done by updating the incident document"
- "Use semantic search to understand what attackers are claiming"

---

## Common Questions and Answers

### Q: "Can Workflows run in real-time or only on schedule?"

**A:** "Workflows support multiple trigger types. Schedule is one option. You can also trigger on document changes - so a new review could immediately trigger detection. Or use webhooks for external triggers."

---

### Q: "How does LOOKUP JOIN perform at scale?"

**A:** "LOOKUP JOIN is optimized for enrichment scenarios. The 'left' side (reviews) is processed, then lookups happen against the 'right' side (users). For best performance, ensure the lookup index is properly indexed and consider the cardinality of the join key."

---

### Q: "What's the difference between ES|QL and semantic search?"

**A:** "ES|QL is analytical - it's great for aggregations, filters, and pattern detection across structured data and metadata. Semantic search understands meaning - it finds content that's conceptually similar even when the words differ. In fraud detection, use ES|QL to find anomalies in behavior (velocity, trust scores), and semantic search to understand what's being said."

---

### Q: "How does the semantic_text field type work?"

**A:** "When you define a field as `semantic_text`, Elasticsearch automatically runs it through an embedding model (ELSER by default) at index time. The embeddings are stored alongside the text. At query time, your query is also embedded, and we find documents with similar embeddings. You don't need to manage models or vectors yourself - it's all automatic."

---

### Q: "Can semantic search find attacks that ES|QL misses?"

**A:** "Yes! Imagine a sophisticated attacker who uses multiple trusted accounts over several days - they might not trigger velocity thresholds. But semantic search could still identify that all their reviews contain similar fabricated claims. The two approaches complement each other."

---

### Q: "Can Agent Builder tools call external APIs?"

**A:** "Currently, Agent Builder tools execute ES|QL queries or semantic searches. For external API calls, you'd use Workflows with HTTP actions and have the Agent reference the results via incident or notification indices."

---

### Q: "How do we handle false positives?"

**A:** "Great question! The threshold values are tuneable. Start conservative (high thresholds), monitor false positive rates, then adjust. The resolution workflow supports 'false_positive' as a resolution type, which releases held reviews. Semantic search can also help - if attack reviews match legitimate complaints from trusted users, that's a signal to investigate further before confirming."

---

### Q: "Can multiple workflows chain together?"

**A:** "Yes! Workflows can trigger other workflows via document changes. Our incident resolution workflow is triggered when an incident status changes to 'resolved' - that status change comes from a different process or manual action."

---

### Q: "What about rate limiting attackers?"

**A:** "Good extension idea! You could add a step to the workflow that flags attacker accounts, then have a separate workflow that monitors for flagged accounts trying to submit new reviews."

---

## Wrap-Up Notes

### Time: 90:00 (or as time allows)

**Key Takeaways to Reinforce:**
1. Workflows enable native automation - no external tools needed
2. ES|QL with LOOKUP JOIN powers cross-index analytical detection
3. Semantic search reveals the attack narrative - what's being claimed
4. Agent Builder turns queries into natural language tools
5. Together: complete insight-to-action in seconds

**The Story Arc:**
> "Remember the four phases: Detect with ES|QL, Understand with semantic search, Automate with Workflows, Investigate with Agent Builder. That's the complete fraud detection pipeline."

**Feedback Collection:**
- Share feedback form link
- Ask for verbal feedback on what worked well/what to improve

**Resources to Share:**
- Workshop GitHub repo
- Elastic Workflows documentation
- ES|QL reference
- Semantic search and ELSER guide
- Agent Builder guide

**Final Message:**
> "Remember: Search finds the insight - ES|QL detects the anomaly, semantic search reveals the narrative. Workflows acts on it. Agent Builder explains it. You've just built a complete automated detection and response system with both analytical and semantic intelligence. Take these patterns and apply them to your own use cases - fraud detection, security, compliance, operations. Thank you for joining us today!"

---

## Timing Cheatsheet

| Section | Start | End | Duration |
|---------|-------|-----|----------|
| Welcome + Problem | 0:00 | 5:00 | 5 min |
| 9.3 Features (incl. Semantic Search) | 5:00 | 15:00 | 10 min |
| Live Demo | 15:00 | 30:00 | 15 min |
| Hands-on Preview | 30:00 | 35:00 | 5 min |
| Challenge 1 | 35:00 | 50:00 | 15 min |
| Challenge 2 | 50:00 | 70:00 | 20 min |
| Challenge 3 | 70:00 | 80:00 | 10 min |
| Challenge 4 | 80:00 | 95:00 | 15 min |
| Wrap-up | 95:00 | 100:00 | 5 min |

**Total: ~100 minutes** (buffer built in)

---

## Pre-Workshop Checklist

- [ ] Lab environments provisioned and accessible
- [ ] Sample data loaded successfully
- [ ] ELSER model deployed and inference endpoint configured
- [ ] Semantic_text field mappings applied to reviews index
- [ ] Workflows deployed and enabled
- [ ] Web application running
- [ ] Kibana accessible with correct permissions
- [ ] Backup slides/demo environment ready
- [ ] Feedback form prepared
- [ ] Resource links ready to share

---

## Emergency Procedures

### If Demo Fails:
1. Have screenshots ready in slides
2. Walk through the workflow YAML
3. Show query results from pre-captured data
4. Move to hands-on early

### If Lab Environment Issues:
1. Have participants pair up
2. Use shared screen for group exercises
3. Extend demo time, shorten hands-on
4. Focus on concepts over completion

### If Semantic Search Not Working:
1. Check if ELSER model is deployed
2. Verify inference endpoint configuration
3. Fall back to keyword search for demo
4. Focus on ES|QL detection flow

### If Running Behind:
1. Skip appendix slides
2. Reduce Challenge 4 time
3. Combine challenges 3+4 discussion
4. Ensure everyone completes Challenge 2 (core learning)
