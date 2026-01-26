#!/usr/bin/env python3
"""
Extract users who reviewed filtered businesses for the Review Fraud Workshop.

Reads the filtered businesses file and the raw review/user datasets to
extract only users who have reviewed the businesses we're using.
"""

import json
import sys
from pathlib import Path
from typing import Set

# Allow running as script or module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))

import click
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


# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_BUSINESSES = PROJECT_ROOT / "data" / "processed" / "businesses.ndjson"
DEFAULT_REVIEWS = PROJECT_ROOT / "data" / "raw" / "yelp_academic_dataset_review.json"
DEFAULT_USERS = PROJECT_ROOT / "data" / "raw" / "yelp_academic_dataset_user.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "users-raw.ndjson"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"


def count_lines(file_path: Path) -> int:
    """Count lines in a file efficiently."""
    count = 0
    with open(file_path, "rb") as f:
        for _ in f:
            count += 1
    return count


def load_business_ids(businesses_path: Path) -> Set[str]:
    """
    Load business IDs from the filtered businesses file.

    Args:
        businesses_path: Path to businesses.ndjson

    Returns:
        Set[str]: Set of business IDs
    """
    business_ids = set()
    with open(businesses_path, "r") as f:
        for line in f:
            try:
                business = json.loads(line.strip())
                business_ids.add(business["business_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return business_ids


def find_user_ids_from_reviews(
    reviews_path: Path,
    business_ids: Set[str],
    verbose: bool = False
) -> Set[str]:
    """
    Find user IDs of users who reviewed the given businesses.

    Args:
        reviews_path: Path to raw reviews dataset
        business_ids: Set of business IDs to match
        verbose: Whether to print verbose output

    Returns:
        Set[str]: Set of user IDs
    """
    user_ids = set()
    total_lines = count_lines(reviews_path)

    with open(reviews_path, "r") as f:
        for line in tqdm(f, total=total_lines, desc="Scanning reviews", unit="rec"):
            try:
                review = json.loads(line.strip())
                if review.get("business_id") in business_ids:
                    user_ids.add(review["user_id"])
            except (json.JSONDecodeError, KeyError):
                continue

    return user_ids


@click.command()
@click.option(
    "--businesses", "-b",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_BUSINESSES,
    help="Path to filtered businesses file (NDJSON)."
)
@click.option(
    "--reviews", "-r",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_REVIEWS,
    help="Path to raw Yelp reviews dataset (NDJSON)."
)
@click.option(
    "--users", "-u",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_USERS,
    help="Path to raw Yelp users dataset (NDJSON)."
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    help="Path for filtered output file (NDJSON)."
)
@click.option(
    "--limit", "-l",
    type=int,
    default=None,
    help="Maximum number of users to output."
)
@common_options
@env_option
def main(
    businesses: Path,
    reviews: Path,
    users: Path,
    output: Path,
    limit: int,
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Extract users who reviewed filtered businesses.

    This is a two-pass process:
    1. Scan reviews to find user IDs who reviewed our businesses
    2. Extract those users from the users dataset

    Prerequisites:
    - filter_businesses.py must have been run first

    Examples:

        # Extract users with default settings
        python -m admin.filter_users

        # Limit number of users
        python -m admin.filter_users --limit 50000

        # Preview without writing
        python -m admin.filter_users --dry-run
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

    # Get limit from config if not specified
    if limit is None:
        limit = config_data.get("data", {}).get("max_users")

    echo_info(f"Businesses file: {businesses}")
    echo_info(f"Reviews file: {reviews}")
    echo_info(f"Users file: {users}")
    echo_info(f"Output file: {output}")
    if limit:
        echo_info(f"User limit: {limit}")

    # Validate input files
    if not businesses.exists():
        echo_error(f"Businesses file not found: {businesses}")
        echo_error("Run filter_businesses.py first.")
        raise SystemExit(1)

    if not reviews.exists():
        echo_error(f"Reviews file not found: {reviews}")
        raise SystemExit(1)

    if not users.exists():
        echo_error(f"Users file not found: {users}")
        raise SystemExit(1)

    # Create output directory if needed
    output.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Load business IDs
    echo_info("\nStep 1: Loading business IDs...")
    business_ids = load_business_ids(businesses)
    echo_info(f"Loaded {len(business_ids):,} business IDs")

    # Step 2: Find user IDs from reviews
    echo_info("\nStep 2: Finding users who reviewed these businesses...")
    target_user_ids = find_user_ids_from_reviews(reviews, business_ids, verbose)
    echo_info(f"Found {len(target_user_ids):,} unique users")

    # Step 3: Extract user records
    echo_info("\nStep 3: Extracting user records...")
    total_users = count_lines(users)

    output_file = None
    if not dry_run:
        output_file = open(output, "w")

    matched_count = 0
    processed_count = 0

    try:
        with open(users, "r") as f:
            for line in tqdm(f, total=total_users, desc="Extracting users", unit="rec"):
                processed_count += 1

                try:
                    user = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                user_id = user.get("user_id")
                if user_id not in target_user_ids:
                    continue

                # Write matching user
                if not dry_run:
                    output_file.write(json.dumps(user) + "\n")

                matched_count += 1

                # Check limit
                if limit and matched_count >= limit:
                    echo_info(f"Reached limit of {limit} users")
                    break

    finally:
        if output_file:
            output_file.close()

    # Print summary
    echo_info(f"\nProcessed {processed_count:,} user records")
    echo_info(f"Matched {matched_count:,} users")

    if dry_run:
        echo_info("\n[DRY RUN] No files were written")
    else:
        echo_success(f"Output written to: {output}")


if __name__ == "__main__":
    main()
