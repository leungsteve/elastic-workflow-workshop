#!/usr/bin/env python3
"""
Generate synthetic attacker accounts and attack reviews for the Review Fraud Workshop.

Creates attacker users with low trust scores and generates negative reviews
targeting a selected business from the filtered dataset.

The attack data simulates a coordinated review frauding scenario where multiple
new accounts post negative reviews within a short time window.
"""

import json
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# Allow running as script or module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from faker import Faker
from tqdm import tqdm

from admin.utils.cli import (
    common_options,
    env_option,
    load_config_file,
    echo_success,
    echo_error,
    echo_info,
    echo_warning,
    echo_verbose,
)


# Initialize Faker
fake = Faker()

# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_BUSINESSES = PROJECT_ROOT / "data" / "processed" / "businesses.ndjson"
DEFAULT_USERS_OUTPUT = PROJECT_ROOT / "data" / "attack" / "users.ndjson"
DEFAULT_REVIEWS_OUTPUT = PROJECT_ROOT / "data" / "attack" / "reviews.ndjson"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"

# Attack review templates - negative content
ATTACK_REVIEW_TEMPLATES = [
    "Terrible experience. Avoid this place at all costs!",
    "Worst restaurant ever. Food was disgusting.",
    "Never coming back. Complete waste of money.",
    "Horrible service and terrible food. 0 stars if I could.",
    "Do not eat here! You will regret it.",
    "This place is a scam. Stay away!",
    "Absolutely awful. Food made me sick.",
    "Rude staff, bad food, dirty restaurant.",
    "The worst meal I've ever had. Disgusting.",
    "Save your money and go somewhere else.",
    "Found a hair in my food. Gross!",
    "Waited an hour for cold food. Never again.",
    "Owner was incredibly rude when I complained.",
    "Health code violation waiting to happen.",
    "Overpriced garbage. Total ripoff.",
    "Bugs crawling on the table. Ran out immediately.",
    "Got food poisoning. Spent the night in the ER.",
    "Fake reviews got me here. Real experience was terrible.",
    "Kitchen looked filthy from the dining area.",
    "Staff was on their phones while we waited forever.",
    "Wrong order, cold food, rude attitude. Avoid!",
    "Tried to charge us twice. Scammers!",
    "Smelled like mold inside. How are they still open?",
    "Microwaved everything. Could taste it.",
    "Saw a mouse run across the floor. Left immediately.",
]


def load_businesses(businesses_path: Path) -> List[Dict]:
    """
    Load businesses from the filtered businesses file.

    Args:
        businesses_path: Path to businesses.ndjson

    Returns:
        List of business records
    """
    businesses = []
    with open(businesses_path, "r") as f:
        for line in f:
            try:
                business = json.loads(line.strip())
                businesses.append(business)
            except json.JSONDecodeError:
                continue
    return businesses


def find_target_business(
    businesses: List[Dict],
    min_stars: float = 4.0,
    min_reviews: int = 50,
    max_reviews: int = 200
) -> Optional[Dict]:
    """
    Find a suitable target business for the attack.

    Criteria:
    - Good rating (4+ stars)
    - Moderate review count (50-200 reviews)
    - Still open

    Args:
        businesses: List of business records
        min_stars: Minimum star rating
        min_reviews: Minimum review count
        max_reviews: Maximum review count

    Returns:
        A suitable business record, or None if not found
    """
    candidates = [
        b for b in businesses
        if b.get("stars", 0) >= min_stars
        and min_reviews <= b.get("review_count", 0) <= max_reviews
        and b.get("is_open", False)
    ]

    if not candidates:
        # Relax criteria if no candidates found
        candidates = [
            b for b in businesses
            if b.get("stars", 0) >= 3.5
            and b.get("review_count", 0) >= 20
            and b.get("is_open", False)
        ]

    if not candidates:
        return None

    # Pick a random candidate
    return random.choice(candidates)


def generate_attacker_user(
    trust_range: Tuple[float, float] = (0.05, 0.20),
    age_range: Tuple[int, int] = (1, 30),
    seed_offset: int = 0
) -> Dict:
    """
    Generate a synthetic attacker user.

    Attackers have:
    - Very low trust scores
    - New accounts (1-30 days old)
    - No friends or fans
    - Few or no reviews
    - No elite status

    Args:
        trust_range: Range for trust score (min, max)
        age_range: Range for account age in days (min, max)
        seed_offset: Offset for reproducibility

    Returns:
        Attacker user record
    """
    user_id = str(uuid.uuid4())
    trust_score = round(random.uniform(*trust_range), 4)
    account_age_days = random.randint(*age_range)

    # Calculate yelping_since date
    yelping_since = datetime.now() - timedelta(days=account_age_days)

    return {
        "user_id": user_id,
        "name": fake.name(),
        "review_count": random.randint(0, 3),
        "yelping_since": yelping_since.strftime("%Y-%m-%d %H:%M:%S"),
        "useful": 0,
        "funny": 0,
        "cool": 0,
        "fans": 0,
        "elite": [],
        "average_stars": round(random.uniform(1.0, 2.0), 2),
        "compliment_hot": 0,
        "compliment_more": 0,
        "compliment_profile": 0,
        "compliment_cute": 0,
        "compliment_list": 0,
        "compliment_note": 0,
        "compliment_plain": 0,
        "compliment_cool": 0,
        "compliment_funny": 0,
        "compliment_writer": 0,
        "compliment_photos": 0,
        # Workshop-specific fields
        "trust_score": trust_score,
        "account_age_days": account_age_days,
        "flagged": False,
        "synthetic": True,
    }


def generate_attack_review(
    user_id: str,
    business_id: str,
    review_date: datetime,
    default_stars: int = 1
) -> Dict:
    """
    Generate a synthetic attack review.

    Attack reviews have:
    - Low star rating (typically 1 star)
    - Negative review text
    - Recent timestamps (within attack window)
    - No helpful/funny/cool votes

    Args:
        user_id: ID of the attacker user
        business_id: ID of the target business
        review_date: Date/time for the review
        default_stars: Star rating (default: 1)

    Returns:
        Attack review record
    """
    review_id = str(uuid.uuid4())

    return {
        "review_id": review_id,
        "user_id": user_id,
        "business_id": business_id,
        "stars": default_stars,
        "date": review_date.strftime("%Y-%m-%d %H:%M:%S"),
        "text": random.choice(ATTACK_REVIEW_TEMPLATES),
        "useful": 0,
        "funny": 0,
        "cool": 0,
        "partition": "attack",
        "status": "pending",
        "synthetic": True,
    }


@click.command()
@click.option(
    "--businesses", "-b",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_BUSINESSES,
    help="Path to filtered businesses file (NDJSON)."
)
@click.option(
    "--users-output", "-u",
    type=click.Path(path_type=Path),
    default=DEFAULT_USERS_OUTPUT,
    help="Path for attacker users output (NDJSON)."
)
@click.option(
    "--reviews-output", "-r",
    type=click.Path(path_type=Path),
    default=DEFAULT_REVIEWS_OUTPUT,
    help="Path for attack reviews output (NDJSON)."
)
@click.option(
    "--target-business-id",
    default=None,
    help="Specific business ID to target. If not provided, auto-selects."
)
@click.option(
    "--num-attackers",
    type=int,
    default=15,
    help="Number of attacker accounts to generate."
)
@click.option(
    "--num-reviews",
    type=int,
    default=50,
    help="Number of attack reviews to generate."
)
@click.option(
    "--attack-window-minutes",
    type=int,
    default=30,
    help="Time window for attack reviews (in minutes)."
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility."
)
@common_options
@env_option
def main(
    businesses: Path,
    users_output: Path,
    reviews_output: Path,
    target_business_id: Optional[str],
    num_attackers: int,
    num_reviews: int,
    attack_window_minutes: int,
    seed: Optional[int],
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Generate synthetic attacker accounts and attack reviews.

    Creates a set of fake attacker users with low trust scores and
    generates negative reviews targeting a selected business. This
    simulates a coordinated review frauding attack for workshop demos.

    The generated data is suitable for injection during the workshop
    to demonstrate the detection workflow.

    Prerequisites:
    - filter_businesses.py must have been run first

    Examples:

        # Generate default attack data (auto-select target)
        python -m admin.generate_attackers

        # Target a specific business
        python -m admin.generate_attackers --target-business-id abc123

        # Generate larger attack
        python -m admin.generate_attackers --num-attackers 25 --num-reviews 100

        # Preview without writing
        python -m admin.generate_attackers --dry-run
    """
    # Load configuration
    config_data = {}
    config_path = Path(config) if config else DEFAULT_CONFIG
    if config_path.exists():
        try:
            config_data = load_config_file(str(config_path))
            echo_verbose(f"Loaded config from {config_path}", verbose)
        except Exception as e:
            echo_warning(f"Could not load config: {e}")

    # Get attack settings from config
    attack_config = config_data.get("attack", {})
    default_stars = attack_config.get("default_stars", 1)
    trust_range = tuple(attack_config.get("reviewer_trust_range", [0.05, 0.20]))
    age_range = tuple(attack_config.get("reviewer_account_age_range", [1, 30]))

    # Set random seed if provided
    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)
        echo_verbose(f"Random seed set to {seed}", verbose)

    echo_info(f"Businesses file: {businesses}")
    echo_info(f"Attacker users output: {users_output}")
    echo_info(f"Attack reviews output: {reviews_output}")
    echo_info(f"Number of attackers: {num_attackers}")
    echo_info(f"Number of reviews: {num_reviews}")
    echo_info(f"Attack window: {attack_window_minutes} minutes")

    # Validate businesses file
    if not businesses.exists():
        echo_error(f"Businesses file not found: {businesses}")
        echo_error("Run filter_businesses.py first.")
        raise SystemExit(1)

    # Create output directories
    users_output.parent.mkdir(parents=True, exist_ok=True)
    reviews_output.parent.mkdir(parents=True, exist_ok=True)

    # Load businesses
    echo_info("\nLoading businesses...")
    all_businesses = load_businesses(businesses)
    echo_info(f"Loaded {len(all_businesses):,} businesses")

    # Find or validate target business
    if target_business_id:
        target_business = next(
            (b for b in all_businesses if b["business_id"] == target_business_id),
            None
        )
        if not target_business:
            echo_error(f"Target business not found: {target_business_id}")
            raise SystemExit(1)
    else:
        echo_info("\nFinding suitable target business...")
        target_business = find_target_business(all_businesses)
        if not target_business:
            echo_error("No suitable target business found!")
            echo_error("Need a business with 4+ stars and 50-200 reviews.")
            raise SystemExit(1)

    echo_info(f"\nTarget business:")
    echo_info(f"  Name: {target_business['name']}")
    echo_info(f"  ID: {target_business['business_id']}")
    echo_info(f"  Rating: {target_business['stars']} stars")
    echo_info(f"  Reviews: {target_business['review_count']}")
    echo_info(f"  City: {target_business['city']}")

    # Generate attacker users
    echo_info(f"\nGenerating {num_attackers} attacker accounts...")
    attacker_users = []
    for i in tqdm(range(num_attackers), desc="Attackers", unit="user"):
        user = generate_attacker_user(
            trust_range=trust_range,
            age_range=age_range,
            seed_offset=i
        )
        attacker_users.append(user)

    attacker_user_ids = [u["user_id"] for u in attacker_users]

    # Calculate attack timestamps
    # Reviews are spread over the attack window, starting from "now"
    attack_start = datetime.now()
    attack_end = attack_start + timedelta(minutes=attack_window_minutes)

    # Generate attack reviews
    echo_info(f"\nGenerating {num_reviews} attack reviews...")
    attack_reviews = []
    for i in tqdm(range(num_reviews), desc="Reviews", unit="rev"):
        # Pick an attacker (with some doing multiple reviews)
        user_id = random.choice(attacker_user_ids)

        # Calculate review time within window
        time_offset_seconds = random.randint(0, attack_window_minutes * 60)
        review_date = attack_start + timedelta(seconds=time_offset_seconds)

        review = generate_attack_review(
            user_id=user_id,
            business_id=target_business["business_id"],
            review_date=review_date,
            default_stars=default_stars
        )
        attack_reviews.append(review)

    # Sort reviews by date
    attack_reviews.sort(key=lambda r: r["date"])

    # Calculate statistics
    reviews_per_attacker = {}
    for review in attack_reviews:
        uid = review["user_id"]
        reviews_per_attacker[uid] = reviews_per_attacker.get(uid, 0) + 1

    avg_reviews = sum(reviews_per_attacker.values()) / len(reviews_per_attacker)
    max_reviews = max(reviews_per_attacker.values())
    min_reviews = min(reviews_per_attacker.values())

    echo_info(f"\nAttack Statistics:")
    echo_info(f"  Reviews per attacker: min={min_reviews}, avg={avg_reviews:.1f}, max={max_reviews}")
    echo_info(f"  Attack window: {attack_start.strftime('%Y-%m-%d %H:%M')} to {attack_end.strftime('%H:%M')}")

    avg_trust = sum(u["trust_score"] for u in attacker_users) / len(attacker_users)
    avg_age = sum(u["account_age_days"] for u in attacker_users) / len(attacker_users)
    echo_info(f"  Average attacker trust score: {avg_trust:.4f}")
    echo_info(f"  Average attacker account age: {avg_age:.1f} days")

    # Write output files
    if dry_run:
        echo_info("\n[DRY RUN] Would write files:")
        echo_info(f"  {users_output}: {len(attacker_users)} attacker users")
        echo_info(f"  {reviews_output}: {len(attack_reviews)} attack reviews")
    else:
        echo_info("\nWriting output files...")

        with open(users_output, "w") as f:
            for user in attacker_users:
                f.write(json.dumps(user) + "\n")
        echo_success(f"Wrote {len(attacker_users)} attacker users to {users_output}")

        with open(reviews_output, "w") as f:
            for review in attack_reviews:
                f.write(json.dumps(review) + "\n")
        echo_success(f"Wrote {len(attack_reviews)} attack reviews to {reviews_output}")

    # Write target business info for reference
    target_info_path = reviews_output.parent / "target_business.json"
    if not dry_run:
        with open(target_info_path, "w") as f:
            json.dump({
                "business_id": target_business["business_id"],
                "name": target_business["name"],
                "stars": target_business["stars"],
                "review_count": target_business["review_count"],
                "city": target_business["city"],
                "attack_summary": {
                    "num_attackers": num_attackers,
                    "num_reviews": num_reviews,
                    "attack_window_minutes": attack_window_minutes,
                    "generated_at": datetime.now().isoformat(),
                }
            }, f, indent=2)
        echo_success(f"Wrote target info to {target_info_path}")

    echo_info("\nAttack data generation complete!")
    echo_info("Use this data with the streaming/injection tools to simulate an attack.")


if __name__ == "__main__":
    main()
