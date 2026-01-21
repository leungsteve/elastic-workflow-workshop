# Getting to Know Your Data

## Time
15 minutes

## Objective
Explore the review platform data, understand the data model, and write detection queries using ES|QL and LOOKUP JOIN.

---

## Background

You are a Trust & Safety analyst at a popular review platform called "FreshEats" - a restaurant discovery site where diners leave reviews for local businesses.

Recently, your platform has been experiencing **review bomb attacks** - coordinated campaigns where bad actors flood a business with fake negative reviews to damage its reputation. These attacks can devastate small businesses overnight.

Your job is to detect these attacks before they cause harm. But first, you need to understand your data.

### The Data Model

Your platform has three main indices:

| Index | Description | Key Fields |
|-------|-------------|------------|
| `businesses` | Restaurant profiles | `business_id`, `name`, `stars`, `city`, `categories` |
| `users` | Reviewer accounts | `user_id`, `name`, `trust_score`, `account_age_days` |
| `reviews` | Individual reviews | `review_id`, `user_id`, `business_id`, `stars`, `date` |

The **trust_score** (0.0 - 1.0) is a calculated metric based on account age, review history, and community interactions. Legitimate reviewers typically have scores above 0.5, while suspicious accounts often have scores below 0.3.

---

## Tasks

### Task 1: Explore the Businesses Index (3 min)

Let's start by understanding what businesses are on the platform.

1. Open **Kibana** in the browser tab
2. Navigate to **Dev Tools** (Menu > Management > Dev Tools) or use the search bar
3. In ES|QL mode, run this query to count businesses:

```esql
FROM businesses
| STATS count = COUNT(*)
```

**Expected output:** You should see a count of businesses (approximately 5,000-20,000 depending on the dataset).

4. Now explore the top-rated restaurants:

```esql
FROM businesses
| WHERE stars >= 4.0
| STATS count = COUNT(*) BY city
| SORT count DESC
| LIMIT 5
```

**What to notice:** This shows which cities have the most highly-rated restaurants. These successful businesses are prime targets for review bombs.

5. Find specific high-profile targets:

```esql
FROM businesses
| WHERE stars >= 4.5 AND review_count > 100
| KEEP name, city, stars, review_count, categories
| SORT review_count DESC
| LIMIT 10
```

**What to notice:** Businesses with high ratings AND many reviews have built strong reputations - exactly what attackers want to destroy.

---

### Task 2: Understand User Trust Scores (3 min)

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
- Average trust score should be around 0.5-0.7
- Min should be close to 0.0
- Max should be close to 1.0

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

**What to notice:** Most legitimate users should be in the Medium to Very High buckets. A suspicious spike in "Very Low" or "Low" buckets could indicate synthetic attack accounts.

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

**What to notice:** Low-trust accounts typically have newer accounts and fewer reviews - classic signs of fake accounts created for attacks.

---

### Task 3: Examine Review Patterns (4 min)

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

**What to notice:** A healthy platform has reviews across all ratings, with a slight positive skew. An attack creates an unnatural spike of 1-star reviews.

3. Find recent negative review clusters (potential attacks):

```esql
FROM reviews
| WHERE stars <= 2 AND date > NOW() - 7 days
| STATS
    negative_count = COUNT(*),
    unique_reviewers = COUNT_DISTINCT(user_id)
  BY business_id
| WHERE negative_count >= 3
| SORT negative_count DESC
| LIMIT 10
```

**What to notice:** Businesses with many negative reviews from multiple reviewers in a short time are potential attack targets.

---

### Task 4: Use LOOKUP JOIN for Enrichment (5 min)

The real power of ES|QL comes from **LOOKUP JOIN** - the ability to combine data across indices in a single query. This is essential for correlating reviews with user trust scores.

1. First, understand the syntax. LOOKUP JOIN matches records from one index with another:

```esql
FROM reviews
| WHERE date > NOW() - 24 hours
| LOOKUP JOIN users ON user_id
| KEEP review_id, user_id, business_id, stars, trust_score, account_age_days
| LIMIT 10
```

**What to notice:** The query starts with reviews and enriches each review with the reviewer's trust score and account age.

2. Now build a detection query that finds suspicious patterns:

```esql
FROM reviews
| WHERE stars <= 2 AND date > NOW() - 24 hours
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
| WHERE stars <= 2 AND date > NOW() - 7 days
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

Using what you've learned, write a query that identifies potential review bomb attacks with these criteria:

- Reviews from the last 30 minutes
- Rating of 2 stars or less
- From users with trust_score below 0.4
- At least 5 suspicious reviews per business
- Include the business name and city

**Hint:** Combine the patterns from Task 4, adjusting the time window and thresholds.

<details>
<summary>Click to reveal solution</summary>

```esql
FROM reviews
| WHERE stars <= 2 AND date > NOW() - 30 minutes
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
| KEEP business_id, name, city, stars AS original_rating, review_count, avg_stars, avg_trust, unique_attackers
| SORT review_count DESC
```

</details>

---

## Success Criteria

Before proceeding to the next challenge, verify you can:

- [ ] Query all three indices (businesses, users, reviews)
- [ ] Understand the trust_score distribution and what low scores indicate
- [ ] Use LOOKUP JOIN to combine reviews with user data
- [ ] Identify patterns that indicate suspicious review activity

---

## Key Takeaways

1. **Trust scores** are your primary signal for identifying fake accounts
2. **LOOKUP JOIN** lets you enrich data across indices in a single query
3. **Coordinated attacks** show patterns: multiple low-trust users, similar timing, low ratings
4. **High-value targets** are businesses with good ratings and many reviews

In the next challenge, you'll automate this detection using Elastic Workflows!
