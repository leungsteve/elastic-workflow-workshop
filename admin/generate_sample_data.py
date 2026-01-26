#!/usr/bin/env python3
"""
Sample Data Generator for the Review Fraud Workshop.

Generates realistic sample data for development/testing without needing
the full Yelp dataset. Creates NDJSON files for businesses, users, and reviews,
plus a small set of attack data to simulate review frauding scenarios.

Example usage:
    # Generate default sample data
    python -m admin.generate_sample_data

    # Generate larger dataset
    python -m admin.generate_sample_data --businesses 500 --users 2000 --reviews 10000

    # Preview without writing files
    python -m admin.generate_sample_data --dry-run --verbose
"""

import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Allow running as script or module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from faker import Faker
from tqdm import tqdm

from admin.utils.cli import (
    common_options,
    echo_success,
    echo_info,
    echo_warning,
    echo_verbose,
)
from admin.utils.progress import ProgressLogger


# Initialize Faker with a seed for reproducibility
fake = Faker()
Faker.seed(42)
random.seed(42)


# Constants for data generation
CITIES = ["Las Vegas", "Phoenix", "Toronto"]
CATEGORIES = ["Restaurants", "Food", "Bars", "Cafes"]
RESTAURANT_ADJECTIVES = [
    "Golden", "Blue", "Red", "Royal", "Happy", "Lucky", "Silver", "Green",
    "Sunset", "Mountain", "Ocean", "River", "Valley", "Urban", "Classic",
    "Modern", "Rustic", "Cozy", "Elegant", "Fresh"
]
RESTAURANT_NOUNS = [
    "Kitchen", "Grill", "Bistro", "Cafe", "Diner", "House", "Place", "Spot",
    "Corner", "Garden", "Terrace", "Room", "Table", "Plate", "Bowl", "Fork",
    "Spoon", "Cup", "Sip", "Bite"
]


def generate_restaurant_name() -> str:
    """Generate a realistic restaurant name."""
    style = random.choice([1, 2, 3, 4])

    if style == 1:
        # "The Golden Kitchen"
        return f"The {random.choice(RESTAURANT_ADJECTIVES)} {random.choice(RESTAURANT_NOUNS)}"
    elif style == 2:
        # "Mario's Kitchen"
        return f"{fake.first_name()}'s {random.choice(RESTAURANT_NOUNS)}"
    elif style == 3:
        # "Blue Mountain Grill"
        return f"{random.choice(RESTAURANT_ADJECTIVES)} {fake.last_name()} {random.choice(RESTAURANT_NOUNS)}"
    else:
        # "Cafe Luna"
        return f"{random.choice(RESTAURANT_NOUNS)} {fake.last_name()}"


def weighted_random(values: list, weights: list) -> float:
    """Select a value based on weights."""
    return random.choices(values, weights=weights, k=1)[0]


def generate_stars_weighted_toward_4() -> float:
    """Generate star rating weighted toward 4.0."""
    # Create ratings from 3.0 to 5.0 in 0.5 increments
    ratings = [3.0, 3.5, 4.0, 4.5, 5.0]
    # Weight toward 4.0
    weights = [0.1, 0.2, 0.4, 0.2, 0.1]
    return weighted_random(ratings, weights)


def generate_review_stars_weighted_toward_4() -> int:
    """Generate review star rating (1-5) weighted toward 4."""
    ratings = [1, 2, 3, 4, 5]
    weights = [0.05, 0.1, 0.2, 0.4, 0.25]
    return weighted_random(ratings, weights)


def generate_trust_score_weighted_higher() -> float:
    """Generate trust score (0.3-0.95) weighted toward higher values."""
    # Generate base score with beta distribution weighted toward higher values
    base = random.betavariate(5, 2)  # Skewed toward 1
    # Scale to 0.3-0.95 range
    return round(0.3 + base * 0.65, 4)


def generate_business(business_id: Optional[str] = None) -> dict:
    """Generate a single business record."""
    if business_id is None:
        business_id = str(uuid.uuid4())

    city = random.choice(CITIES)

    # Generate address based on city
    if city == "Las Vegas":
        state = "NV"
        postal_code = fake.numerify("891##")
    elif city == "Phoenix":
        state = "AZ"
        postal_code = fake.numerify("850##")
    else:  # Toronto
        state = "ON"
        postal_code = fake.bothify("M?? ?#?").upper()

    # Select 1-3 categories
    num_categories = random.randint(1, 3)
    categories = random.sample(CATEGORIES, num_categories)

    return {
        "business_id": business_id,
        "name": generate_restaurant_name(),
        "address": fake.street_address(),
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "latitude": float(fake.latitude()),
        "longitude": float(fake.longitude()),
        "stars": generate_stars_weighted_toward_4(),
        "review_count": random.randint(10, 500),
        "is_open": random.choices([True, False], weights=[0.85, 0.15])[0],
        "categories": ", ".join(categories),
        "attributes": {
            "RestaurantsPriceRange2": str(random.randint(1, 4)),
            "WiFi": random.choice(["free", "paid", "no"]),
            "OutdoorSeating": random.choice(["True", "False"]),
            "RestaurantsDelivery": random.choice(["True", "False"]),
            "RestaurantsTakeOut": random.choice(["True", "False"]),
        },
        "hours": {
            "Monday": "11:0-22:0",
            "Tuesday": "11:0-22:0",
            "Wednesday": "11:0-22:0",
            "Thursday": "11:0-22:0",
            "Friday": "11:0-23:0",
            "Saturday": "10:0-23:0",
            "Sunday": "10:0-21:0",
        }
    }


def generate_user(user_id: Optional[str] = None, is_attacker: bool = False) -> dict:
    """Generate a single user record."""
    if user_id is None:
        user_id = str(uuid.uuid4())

    if is_attacker:
        # Attacker profile: low trust, new account
        trust_score = round(random.uniform(0.05, 0.2), 4)
        account_age_days = random.randint(1, 30)
        review_count = random.randint(1, 10)
        useful = random.randint(0, 2)
        funny = random.randint(0, 1)
        cool = random.randint(0, 1)
        fans = 0
    else:
        # Normal user profile
        trust_score = generate_trust_score_weighted_higher()
        account_age_days = random.randint(30, 2000)
        review_count = random.randint(1, 100)
        useful = random.randint(0, 500)
        funny = random.randint(0, 200)
        cool = random.randint(0, 200)
        fans = random.randint(0, 50)

    # Calculate yelping_since date
    yelping_since = datetime.now() - timedelta(days=account_age_days)

    return {
        "user_id": user_id,
        "name": fake.name(),
        "review_count": review_count,
        "yelping_since": yelping_since.isoformat() + "Z",
        "useful": useful,
        "funny": funny,
        "cool": cool,
        "fans": fans,
        "elite": "",
        "friends": "None",
        "average_stars": round(random.uniform(3.0, 4.5), 2),
        "compliment_hot": random.randint(0, 10),
        "compliment_more": random.randint(0, 10),
        "compliment_profile": random.randint(0, 5),
        "compliment_cute": random.randint(0, 5),
        "compliment_list": random.randint(0, 5),
        "compliment_note": random.randint(0, 20),
        "compliment_plain": random.randint(0, 30),
        "compliment_cool": random.randint(0, 15),
        "compliment_funny": random.randint(0, 15),
        "compliment_writer": random.randint(0, 10),
        "compliment_photos": random.randint(0, 10),
        # Custom fields for our workshop
        "trust_score": trust_score,
        "account_age_days": account_age_days,
        "is_attacker": is_attacker,
    }


def generate_review(
    business_id: str,
    user_id: str,
    review_id: Optional[str] = None,
    is_attack: bool = False,
    max_days_ago: int = 730,  # 2 years
) -> dict:
    """Generate a single review record."""
    if review_id is None:
        review_id = str(uuid.uuid4())

    if is_attack:
        # Attack review: 1 star, short negative text
        stars = 1
        text = random.choice([
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
        ])
        # Attack reviews are recent (last 7 days)
        days_ago = random.randint(0, 7)
    else:
        # Normal review
        stars = generate_review_stars_weighted_toward_4()
        # Generate review text based on rating
        if stars >= 4:
            text = fake.paragraph(nb_sentences=random.randint(3, 8))
            if random.random() > 0.5:
                text += f" {random.choice(['Highly recommended!', 'Will definitely come back!', 'Great experience overall.', 'A hidden gem!'])}"
        elif stars == 3:
            text = fake.paragraph(nb_sentences=random.randint(2, 5))
            text += f" {random.choice(['It was okay.', 'Nothing special.', 'Average experience.', 'Might give it another try.'])}"
        else:
            text = fake.paragraph(nb_sentences=random.randint(2, 4))
            text += f" {random.choice(['Disappointed.', 'Expected better.', 'Would not recommend.', 'Needs improvement.'])}"
        days_ago = random.randint(0, max_days_ago)

    review_date = datetime.now() - timedelta(days=days_ago)

    return {
        "review_id": review_id,
        "user_id": user_id,
        "business_id": business_id,
        "stars": stars,
        "useful": random.randint(0, 20) if not is_attack else 0,
        "funny": random.randint(0, 10) if not is_attack else 0,
        "cool": random.randint(0, 10) if not is_attack else 0,
        "text": text,
        "date": review_date.isoformat() + "Z",
        # Custom fields for our workshop
        "partition": "historical",
        "status": "published",
        "is_attack": is_attack,
    }


def write_ndjson(data: list[dict], filepath: Path, dry_run: bool = False) -> int:
    """Write data to an NDJSON file (one JSON object per line)."""
    if dry_run:
        return len(data)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w') as f:
        for record in data:
            f.write(json.dumps(record) + '\n')

    return len(data)


@click.command()
@click.option(
    '--businesses',
    default=100,
    type=int,
    help='Number of businesses to generate (default: 100).'
)
@click.option(
    '--users',
    default=500,
    type=int,
    help='Number of users to generate (default: 500).'
)
@click.option(
    '--reviews',
    default=2000,
    type=int,
    help='Number of reviews to generate (default: 2000).'
)
@click.option(
    '--output',
    default='data/sample/',
    type=click.Path(),
    help='Output directory for generated files (default: data/sample/).'
)
@common_options
def main(
    businesses: int,
    users: int,
    reviews: int,
    output: str,
    dry_run: bool,
    verbose: bool,
    config: Optional[str],
):
    """
    Generate realistic sample data for development/testing.

    Creates NDJSON files for businesses, users, and reviews with realistic
    data using Faker. Also generates a small attack dataset to simulate
    review frauding scenarios.
    """
    # Resolve output path
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path

    echo_info(f"Generating sample data to: {output_path}")
    echo_info(f"  Businesses: {businesses}")
    echo_info(f"  Users: {users}")
    echo_info(f"  Reviews: {reviews}")

    if dry_run:
        echo_warning("DRY RUN - No files will be written")

    # Step 1: Generate businesses
    echo_verbose("Generating businesses...", verbose)
    generated_businesses = []
    with ProgressLogger(total=businesses, desc="Businesses", unit="biz") as progress:
        for _ in range(businesses):
            generated_businesses.append(generate_business())
            progress.update(1)

    business_ids = [b["business_id"] for b in generated_businesses]
    echo_verbose(f"Generated {len(generated_businesses)} businesses", verbose)

    # Step 2: Generate users
    echo_verbose("Generating users...", verbose)
    generated_users = []
    with ProgressLogger(total=users, desc="Users", unit="user") as progress:
        for _ in range(users):
            generated_users.append(generate_user())
            progress.update(1)

    user_ids = [u["user_id"] for u in generated_users]
    echo_verbose(f"Generated {len(generated_users)} users", verbose)

    # Step 3: Generate reviews
    echo_verbose("Generating reviews...", verbose)
    generated_reviews = []
    with ProgressLogger(total=reviews, desc="Reviews", unit="rev") as progress:
        for _ in range(reviews):
            # Pick random business and user
            business_id = random.choice(business_ids)
            user_id = random.choice(user_ids)
            generated_reviews.append(generate_review(business_id, user_id))
            progress.update(1)

    echo_verbose(f"Generated {len(generated_reviews)} reviews", verbose)

    # Step 4: Generate attack data
    echo_info("Generating attack data...")

    # Generate 10 attacker users
    attacker_users = []
    with ProgressLogger(total=10, desc="Attacker Users", unit="user") as progress:
        for _ in range(10):
            attacker_users.append(generate_user(is_attacker=True))
            progress.update(1)

    attacker_user_ids = [u["user_id"] for u in attacker_users]

    # Generate 50 attack reviews targeting first 3 businesses
    attack_reviews = []
    target_business_ids = business_ids[:3] if len(business_ids) >= 3 else business_ids
    with ProgressLogger(total=50, desc="Attack Reviews", unit="rev") as progress:
        for _ in range(50):
            business_id = random.choice(target_business_ids)
            user_id = random.choice(attacker_user_ids)
            attack_reviews.append(generate_review(business_id, user_id, is_attack=True))
            progress.update(1)

    echo_verbose(f"Generated {len(attacker_users)} attacker users", verbose)
    echo_verbose(f"Generated {len(attack_reviews)} attack reviews", verbose)

    # Step 5: Write files
    echo_info("Writing NDJSON files...")

    # Write main data files
    businesses_file = output_path / "businesses.ndjson"
    users_file = output_path / "users.ndjson"
    reviews_file = output_path / "reviews.ndjson"

    # Write attack data files
    attacker_users_file = output_path / "attacker_users.ndjson"
    attack_reviews_file = output_path / "attack_reviews.ndjson"

    files_written = [
        (businesses_file, generated_businesses),
        (users_file, generated_users),
        (reviews_file, generated_reviews),
        (attacker_users_file, attacker_users),
        (attack_reviews_file, attack_reviews),
    ]

    for filepath, data in files_written:
        count = write_ndjson(data, filepath, dry_run=dry_run)
        if dry_run:
            echo_verbose(f"Would write {count} records to {filepath}", verbose)
        else:
            echo_success(f"Wrote {count} records to {filepath}")

    # Summary
    click.echo()
    echo_success("Sample data generation complete!")
    click.echo()
    click.echo("Generated files:")
    click.echo(f"  - {businesses_file} ({len(generated_businesses)} businesses)")
    click.echo(f"  - {users_file} ({len(generated_users)} users)")
    click.echo(f"  - {reviews_file} ({len(generated_reviews)} reviews)")
    click.echo(f"  - {attacker_users_file} ({len(attacker_users)} attacker users)")
    click.echo(f"  - {attack_reviews_file} ({len(attack_reviews)} attack reviews)")
    click.echo()
    click.echo("Target businesses for attack simulation:")
    for bid in target_business_ids:
        biz = next(b for b in generated_businesses if b["business_id"] == bid)
        click.echo(f"  - {biz['name']} ({bid[:8]}...)")


if __name__ == "__main__":
    main()
