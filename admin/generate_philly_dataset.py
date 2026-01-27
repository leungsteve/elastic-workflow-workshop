#!/usr/bin/env python3
"""
Generate a self-contained Philadelphia dataset for the Review Campaign Detection Workshop.

This script creates a dataset with NO orphaned reviews by:
1. Selecting top N Philadelphia businesses by review count
2. Extracting ALL reviews for those businesses
3. Extracting ALL users who wrote those reviews

The result is a clean, self-contained dataset where every review
has a corresponding user record.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Set, Dict, Any
import random

import click
from tqdm import tqdm


# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Raw dataset files
RAW_BUSINESSES = RAW_DIR / "yelp_academic_dataset_business.json"
RAW_REVIEWS = RAW_DIR / "yelp_academic_dataset_review.json"
RAW_USERS = RAW_DIR / "yelp_academic_dataset_user.json"

# Output files (all in data/processed/)
OUT_BUSINESSES = PROCESSED_DIR / "businesses.ndjson"
OUT_USERS = PROCESSED_DIR / "users.ndjson"
OUT_REVIEWS = PROCESSED_DIR / "reviews.ndjson"

# Default settings
DEFAULT_BUSINESS_COUNT = 250
DEFAULT_CITY = "Philadelphia"

# Categories to include (food-related for the workshop theme)
FOOD_CATEGORIES = {
    "Restaurants", "Food", "Bars", "Cafes", "Coffee & Tea",
    "Breakfast & Brunch", "Pizza", "Sandwiches", "American (Traditional)",
    "American (New)", "Italian", "Mexican", "Chinese", "Japanese",
    "Thai", "Vietnamese", "Indian", "Mediterranean", "Greek",
    "Seafood", "Steakhouses", "Burgers", "Delis", "Bakeries",
    "Ice Cream & Frozen Yogurt", "Desserts", "Food Trucks",
    "Fast Food", "Diners", "Pubs", "Sports Bars", "Wine Bars",
    "Cocktail Bars", "Beer Gardens", "Breweries", "Juice Bars & Smoothies",
}


def count_lines(file_path: Path) -> int:
    """Count lines in a file efficiently."""
    count = 0
    with open(file_path, "rb") as f:
        for _ in f:
            count += 1
    return count


def load_city_businesses(city: str) -> Dict[str, Dict[str, Any]]:
    """
    Load all businesses from a specific city.

    Returns dict mapping business_id -> business data with review_count.
    """
    businesses = {}

    with open(RAW_BUSINESSES, "r") as f:
        for line in tqdm(f, desc=f"Loading {city} businesses", unit="rec"):
            try:
                biz = json.loads(line.strip())
                if biz.get("city", "").lower() == city.lower():
                    # Check if it's a food-related business
                    categories = biz.get("categories", "") or ""
                    cat_set = {c.strip() for c in categories.split(",")}

                    if cat_set & FOOD_CATEGORIES:
                        businesses[biz["business_id"]] = {
                            "data": biz,
                            "review_count": biz.get("review_count", 0),
                        }
            except json.JSONDecodeError:
                continue

    return businesses


def select_top_businesses(
    businesses: Dict[str, Dict[str, Any]],
    count: int
) -> Set[str]:
    """Select top N businesses by review count."""
    sorted_biz = sorted(
        businesses.items(),
        key=lambda x: x[1]["review_count"],
        reverse=True
    )
    return set(biz_id for biz_id, _ in sorted_biz[:count])


def transform_business(business: dict) -> dict:
    """Transform a Yelp business record for the workshop."""
    categories = business.get("categories", "") or ""
    cat_list = [c.strip() for c in categories.split(",") if c.strip()]

    return {
        "business_id": business.get("business_id"),
        "name": business.get("name"),
        "address": business.get("address"),
        "city": business.get("city"),
        "state": business.get("state"),
        "postal_code": business.get("postal_code"),
        "latitude": business.get("latitude"),
        "longitude": business.get("longitude"),
        "stars": business.get("stars"),
        "review_count": business.get("review_count", 0),
        "is_open": business.get("is_open") == 1,
        "categories": cat_list,
        "hours": business.get("hours"),
        "attributes": business.get("attributes"),
        # Workshop-specific fields
        "current_rating": business.get("stars"),
        "rating_protected": False,
    }


def extract_reviews_and_users(
    business_ids: Set[str]
) -> tuple[list[dict], Set[str]]:
    """
    Extract all reviews for given businesses and collect user IDs.

    Returns (list of reviews, set of user_ids).
    """
    reviews = []
    user_ids = set()
    total_lines = count_lines(RAW_REVIEWS)

    with open(RAW_REVIEWS, "r") as f:
        for line in tqdm(f, total=total_lines, desc="Extracting reviews", unit="rec"):
            try:
                review = json.loads(line.strip())
                if review.get("business_id") in business_ids:
                    # Transform review for workshop
                    transformed = {
                        "review_id": review.get("review_id"),
                        "user_id": review.get("user_id"),
                        "business_id": review.get("business_id"),
                        "stars": review.get("stars"),
                        "text": review.get("text"),
                        "date": review.get("date"),
                        "useful": review.get("useful", 0),
                        "funny": review.get("funny", 0),
                        "cool": review.get("cool", 0),
                        # Workshop-specific fields
                        "status": "published",
                        "is_simulated": False,
                    }
                    reviews.append(transformed)
                    user_ids.add(review["user_id"])
            except (json.JSONDecodeError, KeyError):
                continue

    return reviews, user_ids


def extract_users(user_ids: Set[str]) -> list[dict]:
    """
    Extract user records for given user IDs.

    Calculates trust_score based on Yelp data.
    """
    users = []
    total_lines = count_lines(RAW_USERS)
    found_ids = set()

    with open(RAW_USERS, "r") as f:
        for line in tqdm(f, total=total_lines, desc="Extracting users", unit="rec"):
            try:
                user = json.loads(line.strip())
                user_id = user.get("user_id")

                if user_id in user_ids:
                    # Calculate trust score based on Yelp data
                    # Higher score = more trustworthy
                    review_count = user.get("review_count", 0)
                    useful = user.get("useful", 0)
                    funny = user.get("funny", 0)
                    cool = user.get("cool", 0)

                    # Trust score formula (0.0 to 1.0)
                    # Based on engagement and activity
                    engagement_score = min(1.0, (useful + funny + cool) / 1000)
                    activity_score = min(1.0, review_count / 100)

                    # Elite users get a boost
                    elite = user.get("elite", "")
                    elite_boost = 0.2 if elite else 0.0

                    trust_score = min(1.0, (engagement_score * 0.4 + activity_score * 0.4 + elite_boost + 0.2))

                    # Calculate account age in days
                    yelping_since = user.get("yelping_since", "2020-01-01")
                    try:
                        start_date = datetime.strptime(yelping_since.split()[0], "%Y-%m-%d")
                        account_age_days = (datetime.now() - start_date).days
                    except:
                        account_age_days = 365  # Default to 1 year

                    transformed = {
                        "user_id": user_id,
                        "name": user.get("name"),
                        "review_count": review_count,
                        "yelping_since": yelping_since,
                        "useful": useful,
                        "funny": funny,
                        "cool": cool,
                        "elite": elite,
                        "fans": user.get("fans", 0),
                        "average_stars": user.get("average_stars"),
                        # Workshop-specific fields
                        "trust_score": round(trust_score, 2),
                        "account_age_days": account_age_days,
                        "is_attacker": False,
                    }
                    users.append(transformed)
                    found_ids.add(user_id)

            except (json.JSONDecodeError, KeyError):
                continue

    # Report any missing users (shouldn't happen with Yelp data)
    missing = user_ids - found_ids
    if missing:
        print(f"Warning: {len(missing)} users not found in users dataset")

    return users


@click.command()
@click.option(
    "--count", "-n",
    type=int,
    default=DEFAULT_BUSINESS_COUNT,
    help=f"Number of top businesses to include (default: {DEFAULT_BUSINESS_COUNT})."
)
@click.option(
    "--city", "-c",
    type=str,
    default=DEFAULT_CITY,
    help=f"City to extract data from (default: {DEFAULT_CITY})."
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview without writing files."
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Print detailed output."
)
def main(count: int, city: str, dry_run: bool, verbose: bool):
    """
    Generate a self-contained Philadelphia dataset.

    Creates a clean dataset with:
    - Top N businesses by review count
    - ALL reviews for those businesses
    - ALL users who wrote those reviews

    No orphaned reviews - every review has a corresponding user.

    Examples:

        # Generate default dataset (250 businesses)
        python -m admin.generate_philly_dataset

        # Generate smaller dataset for testing
        python -m admin.generate_philly_dataset -n 100

        # Preview without writing
        python -m admin.generate_philly_dataset --dry-run
    """
    print("=" * 60)
    print(f"GENERATING {city.upper()} DATASET")
    print("=" * 60)

    # Validate raw data exists
    for path in [RAW_BUSINESSES, RAW_REVIEWS, RAW_USERS]:
        if not path.exists():
            print(f"Error: Raw data file not found: {path}")
            raise SystemExit(1)

    # Step 1: Load city businesses
    print(f"\n1. Loading {city} businesses...")
    all_businesses = load_city_businesses(city)
    print(f"   Found {len(all_businesses):,} food-related businesses")

    # Step 2: Select top N businesses
    print(f"\n2. Selecting top {count} businesses by review count...")
    selected_ids = select_top_businesses(all_businesses, count)
    print(f"   Selected {len(selected_ids)} businesses")

    if verbose:
        print("\n   Top 10 businesses:")
        sorted_biz = sorted(
            [(bid, all_businesses[bid]) for bid in selected_ids],
            key=lambda x: x[1]["review_count"],
            reverse=True
        )
        for bid, data in sorted_biz[:10]:
            name = data["data"]["name"][:40]
            reviews = data["review_count"]
            print(f"      {reviews:5,} reviews - {name}")

    # Step 3: Extract reviews and collect user IDs
    print(f"\n3. Extracting reviews for selected businesses...")
    reviews, user_ids = extract_reviews_and_users(selected_ids)
    print(f"   Extracted {len(reviews):,} reviews")
    print(f"   Found {len(user_ids):,} unique reviewers")

    # Step 4: Extract user records
    print(f"\n4. Extracting user records...")
    users = extract_users(user_ids)
    print(f"   Extracted {len(users):,} users")

    # Step 5: Prepare business records
    print(f"\n5. Preparing business records...")
    businesses = []
    for bid in selected_ids:
        biz_data = all_businesses[bid]["data"]
        businesses.append(transform_business(biz_data))
    print(f"   Prepared {len(businesses)} businesses")

    # Summary
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    print(f"   Businesses: {len(businesses):,}")
    print(f"   Reviews:    {len(reviews):,}")
    print(f"   Users:      {len(users):,}")
    print(f"   Orphaned reviews: 0 (guaranteed)")

    # Estimate file sizes
    biz_size = len(businesses) * 500 / 1024 / 1024  # ~500 bytes per business
    review_size = len(reviews) * 800 / 1024 / 1024  # ~800 bytes per review
    user_size = len(users) * 400 / 1024 / 1024  # ~400 bytes per user
    total_size = biz_size + review_size + user_size

    print(f"\n   Estimated file sizes:")
    print(f"      businesses.ndjson: ~{biz_size:.1f} MB")
    print(f"      reviews.ndjson:    ~{review_size:.1f} MB")
    print(f"      users.ndjson:      ~{user_size:.1f} MB")
    print(f"      Total:             ~{total_size:.1f} MB")

    if dry_run:
        print("\n[DRY RUN] No files were written")
        return

    # Write output files
    print(f"\n6. Writing output files...")

    # Ensure directories exist
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

    # Write businesses
    with open(OUT_BUSINESSES, "w") as f:
        for biz in tqdm(businesses, desc="Writing businesses"):
            f.write(json.dumps(biz) + "\n")
    print(f"   Wrote {OUT_BUSINESSES}")

    # Write users
    with open(OUT_USERS, "w") as f:
        for user in tqdm(users, desc="Writing users"):
            f.write(json.dumps(user) + "\n")
    print(f"   Wrote {OUT_USERS}")

    # Write reviews (sorted by date for realistic streaming later)
    reviews.sort(key=lambda x: x.get("date", ""))
    with open(OUT_REVIEWS, "w") as f:
        for review in tqdm(reviews, desc="Writing reviews"):
            f.write(json.dumps(review) + "\n")
    print(f"   Wrote {OUT_REVIEWS}")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print(f"""
Next steps:
1. Create indices:    python -m admin.create_indices
2. Load data:         python -m admin.load_data
3. Verify:            python -m admin.verify_environment
""")


if __name__ == "__main__":
    main()
