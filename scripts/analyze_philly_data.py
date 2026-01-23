#!/usr/bin/env python3
"""Analyze Philadelphia Yelp data for dataset sizing."""

import json
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path("/workspace/elastic-workflow-workshop/data/raw")

def load_philly_businesses():
    """Load all Philadelphia businesses."""
    businesses = {}
    with open(RAW_DIR / "yelp_academic_dataset_business.json") as f:
        for line in f:
            biz = json.loads(line)
            if biz.get("city", "").lower() == "philadelphia":
                businesses[biz["business_id"]] = {
                    "name": biz["name"],
                    "review_count": biz.get("review_count", 0),
                    "stars": biz.get("stars", 0),
                    "categories": biz.get("categories", ""),
                }
    return businesses

def analyze_reviews(business_ids):
    """Count reviews and collect user_ids for given businesses."""
    review_counts = defaultdict(int)
    user_ids = set()
    total_reviews = 0

    with open(RAW_DIR / "yelp_academic_dataset_review.json") as f:
        for line in f:
            review = json.loads(line)
            biz_id = review["business_id"]
            if biz_id in business_ids:
                review_counts[biz_id] += 1
                user_ids.add(review["user_id"])
                total_reviews += 1

    return review_counts, user_ids, total_reviews

def main():
    print("=" * 60)
    print("PHILADELPHIA YELP DATA ANALYSIS")
    print("=" * 60)

    # Load businesses
    print("\n1. Loading Philadelphia businesses...")
    businesses = load_philly_businesses()
    print(f"   Total Philadelphia businesses: {len(businesses):,}")

    # Sort by review count
    sorted_biz = sorted(
        businesses.items(),
        key=lambda x: x[1]["review_count"],
        reverse=True
    )

    # Show top businesses
    print("\n2. Top 20 businesses by review count:")
    print("-" * 60)
    for biz_id, data in sorted_biz[:20]:
        print(f"   {data['review_count']:5d} reviews - {data['name'][:40]}")

    # Review count distribution
    print("\n3. Review count distribution:")
    print("-" * 60)
    brackets = [0, 10, 50, 100, 500, 1000, 5000, float('inf')]
    for i in range(len(brackets) - 1):
        count = sum(1 for _, d in sorted_biz if brackets[i] <= d["review_count"] < brackets[i+1])
        label = f"{brackets[i]}-{brackets[i+1]-1}" if brackets[i+1] != float('inf') else f"{brackets[i]}+"
        print(f"   {label:12s} reviews: {count:,} businesses")

    # Calculate total reviews from business review_count field
    total_reviews_estimate = sum(d["review_count"] for _, d in sorted_biz)
    print(f"\n   Estimated total reviews (from business data): {total_reviews_estimate:,}")

    # Analyze different subset sizes
    print("\n4. Subset analysis (by top N businesses):")
    print("-" * 60)
    print(f"   {'Businesses':>12} | {'Est. Reviews':>14} | {'Avg Rev/Biz':>12}")
    print("   " + "-" * 45)

    subsets = [100, 250, 500, 1000, 2000, 5000, 10000, len(sorted_biz)]
    results = []

    for n in subsets:
        subset = sorted_biz[:n]
        total_rev = sum(d["review_count"] for _, d in subset)
        avg_rev = total_rev / n if n > 0 else 0
        results.append((n, total_rev, avg_rev))
        label = f"{n:,}" if n < len(sorted_biz) else "ALL"
        print(f"   {label:>12} | {total_rev:>14,} | {avg_rev:>12.1f}")

    # Now do actual review/user analysis for key subset sizes
    print("\n5. Detailed analysis (counting actual reviews and unique users):")
    print("-" * 60)
    print("   This scans the review file - may take a minute...")

    key_subsets = [100, 250, 500, 1000]

    for n in key_subsets:
        subset_ids = set(biz_id for biz_id, _ in sorted_biz[:n])
        review_counts, user_ids, total_reviews = analyze_reviews(subset_ids)

        print(f"\n   TOP {n} BUSINESSES:")
        print(f"      Actual reviews: {total_reviews:,}")
        print(f"      Unique users: {len(user_ids):,}")
        print(f"      Avg reviews/business: {total_reviews/n:.1f}")
        print(f"      Estimated data size: ~{(total_reviews * 0.5 + len(user_ids) * 1.5) / 1000:.1f} MB")

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("""
    For Instruqt (fast load times), consider:

    - 100 businesses: ~20k reviews, ~15k users - Very fast load
    - 250 businesses: ~45k reviews, ~30k users - Fast load
    - 500 businesses: ~80k reviews, ~50k users - Moderate load
    - 1000 businesses: ~140k reviews, ~80k users - Slower load

    The top businesses have the most reviews, so you get more
    data density. 250-500 businesses is likely the sweet spot.
    """)

if __name__ == "__main__":
    main()
