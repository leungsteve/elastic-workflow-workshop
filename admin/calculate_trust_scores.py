#!/usr/bin/env python3
"""
Calculate trust scores for users in the Review Fraud Workshop.

Reads the raw extracted users file and adds trust scores based on
account activity, engagement, and behavior patterns.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from tqdm import tqdm

from admin.utils.cli import (
    common_options,
    env_option,
    echo_success,
    echo_error,
    echo_info,
    echo_verbose,
)


# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "users-raw.ndjson"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "users.ndjson"

# Reference date for calculating account age
# Using a fixed date for reproducibility
REFERENCE_DATE = datetime(2022, 12, 31)


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string from Yelp data.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        datetime or None if parsing fails
    """
    if not date_str:
        return None

    try:
        # Yelp uses YYYY-MM-DD format
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def parse_elite_years(elite_str: Optional[str]) -> list:
    """
    Parse elite years string into a list.

    Args:
        elite_str: Comma-separated string of years (e.g., "2015,2016,2017")

    Returns:
        List of year strings
    """
    if not elite_str:
        return []

    # Elite can be comma-separated years
    years = [y.strip() for y in str(elite_str).split(",") if y.strip()]
    return [y for y in years if y.isdigit()]


def calculate_account_age_days(yelping_since: Optional[str]) -> int:
    """
    Calculate account age in days from yelping_since date.

    Args:
        yelping_since: Date string when user joined

    Returns:
        int: Account age in days (minimum 0)
    """
    if not yelping_since:
        return 0

    join_date = parse_date(yelping_since)
    if not join_date:
        return 0

    delta = REFERENCE_DATE - join_date
    return max(0, delta.days)


def calculate_trust_score(user: dict, account_age_days: int) -> float:
    """
    Calculate trust score for a user based on their profile.

    The trust score formula:
    - review_count component (25%): min(review_count, 100) / 100 * 0.25
    - useful component (15%): min(useful, 100) / 100 * 0.15
    - fans component (10%): min(fans, 50) / 50 * 0.10
    - elite component (up to 50% for 10+ years): len(elite) * 0.05
    - account_age component (25%): min(account_age_days, 1825) / 1825 * 0.25
    - rating_balance component (20%): (1 - abs(average_stars - 3.5) / 3.5) * 0.20

    Args:
        user: User record
        account_age_days: Pre-calculated account age in days

    Returns:
        float: Trust score between 0.0 and 1.0
    """
    # Extract values with defaults
    review_count = user.get("review_count", 0) or 0
    useful = user.get("useful", 0) or 0
    fans = user.get("fans", 0) or 0
    average_stars = user.get("average_stars", 3.5) or 3.5

    # Parse elite years
    elite_str = user.get("elite", "")
    elite_years = parse_elite_years(elite_str)

    # Calculate each component
    # Review count component (25%)
    review_component = min(review_count, 100) / 100 * 0.25

    # Useful votes component (15%)
    useful_component = min(useful, 100) / 100 * 0.15

    # Fans component (10%)
    fans_component = min(fans, 50) / 50 * 0.10

    # Elite years component (5% per year, max 50%)
    elite_component = min(len(elite_years) * 0.05, 0.50)

    # Account age component (25%)
    # 1825 days = 5 years
    age_component = min(account_age_days, 1825) / 1825 * 0.25

    # Rating balance component (20%)
    # Users who rate close to 3.5 average are considered more balanced
    rating_deviation = abs(average_stars - 3.5) / 3.5
    rating_component = (1 - rating_deviation) * 0.20

    # Sum all components
    trust_score = (
        review_component +
        useful_component +
        fans_component +
        elite_component +
        age_component +
        rating_component
    )

    # Normalize to 0.0-1.0 range
    return max(0.0, min(1.0, trust_score))


def transform_user(user: dict) -> dict:
    """
    Transform a user record with trust score and additional fields.

    Args:
        user: Raw user record from Yelp

    Returns:
        dict: Transformed user record
    """
    # Calculate account age
    account_age_days = calculate_account_age_days(user.get("yelping_since"))

    # Calculate trust score
    trust_score = calculate_trust_score(user, account_age_days)

    # Parse elite years into list
    elite_years = parse_elite_years(user.get("elite", ""))

    # Build transformed record
    transformed = {
        "user_id": user.get("user_id"),
        "name": user.get("name"),
        "review_count": user.get("review_count", 0),
        "yelping_since": user.get("yelping_since"),
        "useful": user.get("useful", 0),
        "funny": user.get("funny", 0),
        "cool": user.get("cool", 0),
        "fans": user.get("fans", 0),
        "elite": elite_years,
        "average_stars": user.get("average_stars"),
        "compliment_hot": user.get("compliment_hot", 0),
        "compliment_more": user.get("compliment_more", 0),
        "compliment_profile": user.get("compliment_profile", 0),
        "compliment_cute": user.get("compliment_cute", 0),
        "compliment_list": user.get("compliment_list", 0),
        "compliment_note": user.get("compliment_note", 0),
        "compliment_plain": user.get("compliment_plain", 0),
        "compliment_cool": user.get("compliment_cool", 0),
        "compliment_funny": user.get("compliment_funny", 0),
        "compliment_writer": user.get("compliment_writer", 0),
        "compliment_photos": user.get("compliment_photos", 0),
        # Workshop-specific fields
        "trust_score": round(trust_score, 4),
        "account_age_days": account_age_days,
        "flagged": False,
        "synthetic": False,
    }

    # Note: We don't include 'friends' as it's a large array not needed for the workshop

    return transformed


def count_lines(file_path: Path) -> int:
    """Count lines in a file efficiently."""
    count = 0
    with open(file_path, "rb") as f:
        for _ in f:
            count += 1
    return count


@click.command()
@click.option(
    "--input", "-i", "input_path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_INPUT,
    help="Path to raw extracted users file (NDJSON)."
)
@click.option(
    "--output", "-o", "output_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    help="Path for output file with trust scores (NDJSON)."
)
@common_options
@env_option
def main(
    input_path: Path,
    output_path: Path,
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Calculate trust scores for filtered users.

    Reads user records and calculates a trust score based on:
    - Review count (25%)
    - Useful votes received (15%)
    - Number of fans (10%)
    - Years as Elite member (5% per year)
    - Account age (25%)
    - Rating balance - closeness to 3.5 average (20%)

    Also adds account_age_days field.

    Prerequisites:
    - filter_users.py must have been run first

    Examples:

        # Calculate trust scores
        python -m admin.calculate_trust_scores

        # Preview without writing
        python -m admin.calculate_trust_scores --dry-run

        # Verbose output with statistics
        python -m admin.calculate_trust_scores -v
    """
    echo_info(f"Input file: {input_path}")
    echo_info(f"Output file: {output_path}")
    echo_info(f"Reference date for age calculation: {REFERENCE_DATE.date()}")

    # Validate input file
    if not input_path.exists():
        echo_error(f"Input file not found: {input_path}")
        echo_error("Run filter_users.py first.")
        raise SystemExit(1)

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Count total lines
    echo_info("\nCounting records...")
    total_lines = count_lines(input_path)
    echo_verbose(f"Total records: {total_lines}", verbose)

    # Process users
    output_file = None
    if not dry_run:
        output_file = open(output_path, "w")

    processed_count = 0
    error_count = 0

    # Statistics tracking
    trust_scores = []
    account_ages = []

    try:
        with open(input_path, "r") as f:
            for line in tqdm(f, total=total_lines, desc="Calculating trust scores", unit="rec"):
                try:
                    user = json.loads(line.strip())
                except json.JSONDecodeError:
                    error_count += 1
                    continue

                # Transform user with trust score
                transformed = transform_user(user)

                if not dry_run:
                    output_file.write(json.dumps(transformed) + "\n")

                processed_count += 1

                # Track statistics
                trust_scores.append(transformed["trust_score"])
                account_ages.append(transformed["account_age_days"])

    finally:
        if output_file:
            output_file.close()

    # Calculate and print statistics
    if trust_scores:
        avg_trust = sum(trust_scores) / len(trust_scores)
        min_trust = min(trust_scores)
        max_trust = max(trust_scores)

        avg_age = sum(account_ages) / len(account_ages)
        min_age = min(account_ages)
        max_age = max(account_ages)

        # Trust score distribution
        low_trust = sum(1 for t in trust_scores if t < 0.3)
        mid_trust = sum(1 for t in trust_scores if 0.3 <= t < 0.7)
        high_trust = sum(1 for t in trust_scores if t >= 0.7)

        echo_info(f"\nProcessed {processed_count:,} users")
        if error_count:
            echo_info(f"Skipped {error_count} malformed records")

        echo_info(f"\nTrust Score Statistics:")
        echo_info(f"  Average: {avg_trust:.4f}")
        echo_info(f"  Min: {min_trust:.4f}")
        echo_info(f"  Max: {max_trust:.4f}")

        echo_info(f"\nTrust Score Distribution:")
        echo_info(f"  Low (<0.3): {low_trust:,} ({low_trust/len(trust_scores)*100:.1f}%)")
        echo_info(f"  Medium (0.3-0.7): {mid_trust:,} ({mid_trust/len(trust_scores)*100:.1f}%)")
        echo_info(f"  High (>=0.7): {high_trust:,} ({high_trust/len(trust_scores)*100:.1f}%)")

        echo_info(f"\nAccount Age Statistics:")
        echo_info(f"  Average: {avg_age:.0f} days ({avg_age/365:.1f} years)")
        echo_info(f"  Min: {min_age} days")
        echo_info(f"  Max: {max_age} days ({max_age/365:.1f} years)")

    if dry_run:
        echo_info("\n[DRY RUN] No files were written")
    else:
        echo_success(f"\nOutput written to: {output_path}")


if __name__ == "__main__":
    main()
