# Getting to Know Your Data

## Time
15 minutes

## Theme Focus: SIMPLIFY
> In this challenge, you'll see how ES|QL makes complex queries **readable and accessible** to anyone—not just query experts.

## Objective
Explore the review platform data, understand the data model, and write detection queries using ES|QL and LOOKUP JOIN.

---

## Background

You are a Trust & Safety analyst at a popular review platform called "ElasticEats" - a restaurant discovery site where diners leave reviews for local businesses.

Recently, your platform has been experiencing **negative review campaigns (review bombs)** — coordinated attacks that can devastate small businesses overnight.

A **negative review campaign** — commonly called a **review bomb** — is a coordinated attack where bad actors flood a business with fake negative reviews to damage its reputation. These campaigns can tank a restaurant's star rating in hours, driving away customers before the business even knows what happened.

Your job is to detect these attacks before they cause harm. But first, you need to understand your data.

### The Data Model

Your platform has three main indices:

| Index | Description | Key Fields |
|-------|-------------|------------|
| `businesses` | Restaurant profiles | `business_id`, `name`, `stars`, `city`, `categories` |
| `users` | Reviewer accounts | `user_id`, `name`, `trust_score`, `account_age_days` |
| `reviews` | Individual reviews | `review_id`, `user_id`, `business_id`, `stars`, `date`, `text_semantic` |

The **trust_score** (0.0 - 1.0) is a calculated metric based on account age, review history, and community interactions. Legitimate reviewers typically have scores above 0.5, while suspicious accounts often have scores below 0.3.

The **text_semantic** field uses ELSER (Elastic Learned Sparse Encoder) to enable semantic search - finding reviews by meaning rather than exact keywords. This is powerful for understanding attack narratives.

---

## Tasks

### Task 1: Explore ElasticEats (2 min)

Before diving into queries, let's see the platform you're protecting. ElasticEats is a consumer-facing restaurant review site — think Yelp for Philadelphia. Your workshop environment is running a live instance.

1. Open the **ElasticEats** tab
2. Browse the home page — you'll see top-rated Philadelphia restaurants with star ratings, review counts, and categories
3. Click on a business (try **Reading Terminal Market** or **Zahav**) to see its detail page with individual reviews
4. Notice the information available: star ratings, review text, reviewer names, and dates. This is what real users see — and what attackers try to manipulate

**Keep this tab open** throughout the workshop. As you explore the data with ES|QL in the next tasks, you'll recognize the same businesses and reviews you just browsed. In later challenges, you'll watch an attack unfold on this very interface.

---

### Task 2: Explore the Businesses Index (3 min)

Now let's look at the same data from the analyst's perspective using ES|QL in Kibana.

1. Open **Kibana** in the browser tab
2. Navigate to **Discover** (Menu > Analytics > Discover)
3. Click the language dropdown (usually shows "KQL") and select **ES|QL**
4. Run this query to count businesses:

```esql
FROM businesses
| STATS count = COUNT(*)
```

**Expected output:** You should see a count of **100 businesses** (all located in Philadelphia).

5. Now explore the top-rated restaurants:

```esql
FROM businesses
| WHERE stars >= 4.0
| STATS count = COUNT(*) BY city
| SORT count DESC
| LIMIT 5
```

**Expected output:** **84** of 100 businesses have 4+ stars, all in Philadelphia. These successful businesses are prime targets for negative review campaigns.

6. Find specific high-profile targets:

```esql
FROM businesses
| WHERE stars >= 4.5 AND review_count > 100
| KEEP name, city, stars, review_count, categories
| SORT review_count DESC
| LIMIT 10
```

**What to notice:** Businesses with high ratings AND many reviews have built strong reputations - exactly what attackers want to destroy. You may recognize some of these names from browsing ElasticEats in Task 1.

---

### Task 3: Understand User Trust Scores (3 min)

The `trust_score` field is crucial for detecting fake reviewers. Let's explore its distribution.

1. Get the overall trust score statistics:

```esql
FROM users
| STATS
    total_users = COUNT(*),
    avg_trust = AVG(trust_score),
    min_trust = MIN(trust_score),
    max_trust = MAX(trust_score)
| EVAL avg_trust = ROUND(avg_trust, 2)
```

**Expected output:**
- Average trust score: approximately **0.43**
- Min: approximately **0.20**
- Max: **1.0**

2. See the distribution of trust scores:

```esql
FROM users
| EVAL trust_bucket = CASE(
    trust_score < 0.2, "Very Low (0-0.2)",
    trust_score < 0.4, "Low (0.2-0.4)",
    trust_score < 0.6, "Medium (0.4-0.6)",
    trust_score < 0.8, "High (0.6-0.8)",
    TRUE, "Very High (0.8-1.0)"
  )
| STATS count = COUNT(*) BY trust_bucket
| SORT trust_bucket ASC
```

**What to notice:** The majority of users fall in the Low (0.2-0.4) bucket, with smaller populations in Medium through Very High. This distribution is normal for this dataset — the trust score reflects account age, review history, and engagement. Users in the Low bucket aren't necessarily attackers, but during an attack, synthetic accounts will cluster at the very bottom of this range.

3. Look at characteristics of low-trust accounts:

```esql
FROM users
| WHERE trust_score < 0.3
| STATS
    count = COUNT(*),
    avg_account_age = AVG(account_age_days),
    avg_reviews = AVG(review_count)
| EVAL avg_account_age = ROUND(avg_account_age, 0)
| EVAL avg_reviews = ROUND(avg_reviews, 1)
```

**What to notice:** Low-trust accounts tend to have fewer reviews compared to high-trust accounts. When an attack is simulated, the synthetic attacker accounts will have very low trust scores AND very new accounts — making them stand out from the existing low-trust population.

---

### Task 4: Examine Review Patterns (4 min)

Now let's look at the reviews themselves.

1. Count total reviews:

```esql
FROM reviews
| STATS count = COUNT(*)
```

2. See the rating distribution:

```esql
FROM reviews
| STATS count = COUNT(*) BY stars
| SORT stars DESC
```

**What to notice:** A healthy platform has reviews across all ratings, with a strong positive skew (5-star is the most common at ~67K, tapering down to ~8K one-star reviews). An attack creates an unnatural spike of 1-star reviews.

> **Tip:** In the chart visualization, drag `stars` from the vertical axis to the horizontal axis for a more intuitive bar chart.

3. Find negative review clusters (potential attacks):

```esql
FROM reviews
| WHERE stars <= 2
| STATS
    negative_count = COUNT(*),
    unique_reviewers = COUNT_DISTINCT(user_id)
  BY business_id
| WHERE negative_count >= 3
| LOOKUP JOIN businesses ON business_id
| KEEP name, business_id, negative_count, unique_reviewers
| SORT negative_count DESC
| LIMIT 10
```

**What to notice:** Businesses with many negative reviews from multiple unique reviewers are potential attack targets. The LOOKUP JOIN adds the business name so you can see which restaurants are affected.

---

### Task 5: Explore Semantic Search (3 min)

The reviews index has a `text_semantic` field that enables searching by meaning, not just keywords. This is powered by ELSER (Elastic Learned Sparse Encoder). **You can do semantic search directly in ES|QL using the `:` operator!**

1. First, see how keyword search works - find reviews with the exact phrase "food poisoning":

```esql
FROM reviews
| WHERE text LIKE "*food poisoning*"
| KEEP review_id, text, stars
| LIMIT 5
```

**What to notice:** This only finds reviews containing the exact phrase "food poisoning".

2. Now use **semantic search** to find reviews about illness - even without those exact words:

```esql
FROM reviews METADATA _score
| WHERE text_semantic: "food poisoning made me ill"
| SORT _score DESC
| KEEP review_id, text, stars, _score
| LIMIT 5
```

**What to notice:** Semantic search finds reviews about stomach problems, getting sick, food-borne illness - even if they use different words like "nausea", "vomiting", or "got sick". It understands **meaning**, not just keywords. The `_score` shows relevance - higher scores mean more semantically similar.

3. Try searching for attack narratives:

```esql
FROM reviews METADATA _score
| WHERE text_semantic: "terrible service rude staff worst experience"
| SORT _score DESC
| KEEP review_id, text, stars, user_id, _score
| LIMIT 5
```

**What to notice:** This finds reviews with similar negative sentiment, even if they use words like "awful", "horrible", "disrespectful", or "disappointing".

4. Combine semantic search with filters to investigate a specific business:

```esql
FROM reviews METADATA _score
| WHERE text_semantic: "scam ripoff stay away"
| WHERE stars <= 2
| SORT _score DESC
| KEEP review_id, business_id, stars, text, _score
| LIMIT 10
```

**Why this matters:** Attackers often use similar narratives. Semantic search in ES|QL helps you find patterns in what they're claiming - all without leaving Discover!

---

### Task 6: Use LOOKUP JOIN for Enrichment (5 min)

The real power of ES|QL comes from **LOOKUP JOIN** - the ability to combine data across indices in a single query. This is essential for correlating reviews with user trust scores.

**Key concept:** LOOKUP JOIN lets you correlate data across indices without leaving ES|QL.

1. First, understand the syntax. LOOKUP JOIN matches records from one index with another:

```esql
FROM reviews
| LOOKUP JOIN users ON user_id
| KEEP review_id, user_id, business_id, stars, trust_score, account_age_days
| LIMIT 10
```

**What to notice:** The query starts with reviews and enriches each review with the reviewer's trust score and account age.

2. Now build a detection query that finds suspicious patterns:

```esql
FROM reviews
| WHERE stars <= 2
| LOOKUP JOIN users ON user_id
| WHERE trust_score < 0.4
| STATS
    suspicious_reviews = COUNT(*),
    avg_rating = AVG(stars),
    avg_trust = AVG(trust_score),
    unique_attackers = COUNT_DISTINCT(user_id)
  BY business_id
| WHERE suspicious_reviews >= 3
| SORT suspicious_reviews DESC
| LIMIT 10
```

**What to notice:** This query finds businesses receiving multiple low-rating reviews from low-trust accounts - a strong signal of a coordinated attack.

3. Add business details with a second LOOKUP JOIN:

```esql
FROM reviews
| WHERE stars <= 2
| LOOKUP JOIN users ON user_id
| WHERE trust_score < 0.4
| STATS
    suspicious_reviews = COUNT(*),
    avg_trust = AVG(trust_score),
    unique_attackers = COUNT_DISTINCT(user_id)
  BY business_id
| WHERE suspicious_reviews >= 3
| LOOKUP JOIN businesses ON business_id
| KEEP business_id, name, city, stars, suspicious_reviews, avg_trust, unique_attackers
| SORT suspicious_reviews DESC
```

**What to notice:** Now you can see which specific businesses are being targeted, along with their original rating. High-rated businesses with many suspicious reviews need immediate attention.

---

## Challenge: Write Your Own Detection Query

Using what you've learned, write a query that identifies potential negative review campaigns with these criteria:

- Rating of 2 stars or less
- From users with trust_score below 0.4
- At least 5 suspicious reviews per business
- Include the business name and city

**Hint:** Combine the patterns from Task 6, adjusting the time window and thresholds.

<details>
<summary>Click to reveal solution</summary>

```esql
FROM reviews
| WHERE stars <= 2
| LOOKUP JOIN users ON user_id
| WHERE trust_score < 0.4
| STATS
    review_count = COUNT(*),
    avg_stars = AVG(stars),
    avg_trust = AVG(trust_score),
    unique_attackers = COUNT_DISTINCT(user_id)
  BY business_id
| WHERE review_count >= 5
| LOOKUP JOIN businesses ON business_id
| EVAL original_rating = stars
| KEEP business_id, name, city, original_rating, review_count, avg_stars, avg_trust, unique_attackers
| SORT review_count DESC
```

</details>

---

## Success Criteria

Before proceeding to the next challenge, verify you can:

- [ ] Browse ElasticEats and view business detail pages with reviews
- [ ] Query all three indices (businesses, users, reviews)
- [ ] Understand the trust_score distribution and what low scores indicate
- [ ] Use semantic search to find reviews by meaning, not just keywords
- [ ] Use LOOKUP JOIN to combine reviews with user data
- [ ] Identify patterns that indicate suspicious review activity

---

## Key Takeaways

1. **Trust scores** are your primary signal for identifying fake accounts
2. **Semantic search** finds reviews by meaning - critical for understanding attack narratives
3. **LOOKUP JOIN** lets you enrich data across indices in a single query
4. **Coordinated attacks** show patterns: multiple low-trust users, similar timing, low ratings
5. **High-value targets** are businesses with good ratings and many reviews

In the next challenge, you'll automate this detection using Elastic Workflows!
