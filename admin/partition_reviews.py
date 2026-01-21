#!/usr/bin/env python3
"""
Partition reviews into historical and streaming sets for the Review Bomb Workshop.

Splits reviews that match our filtered businesses into:
- Historical reviews (80%): Pre-loaded into Elasticsearch
- Streaming reviews (20%): Used for live replay during the workshop
"""

import json
import random
from pathlib import Path
from typing import Set

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
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "yelp_academic_dataset_review.json"
DEFAULT_BUSINESSES = PROJECT_ROOT / "data" / "processed" / "businesses.ndjson"
DEFAULT_HISTORICAL_OUTPUT = PROJECT_ROOT / "data" / "historical" / "reviews.ndjson"
DEFAULT_STREAMING_OUTPUT = PROJECT_ROOT / "data" / "streaming" / "reviews.ndjson"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"

# Default historical ratio
DEFAULT_HISTORICAL_RATIO = 0.8


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


def transform_review(review: dict, partition: str) -> dict:
    """
    Transform a review record for the workshop.

    Args:
        review: Raw Yelp review record
        partition: Either "historical" or "streaming"

    Returns:
        dict: Transformed review record
    """
    transformed = {
        "review_id": review.get("review_id"),
        "user_id": review.get("user_id"),
        "business_id": review.get("business_id"),
        "stars": review.get("stars"),
        "date": review.get("date"),
        "text": review.get("text"),
        "useful": review.get("useful", 0),
        "funny": review.get("funny", 0),
        "cool": review.get("cool", 0),
        "partition": partition,
        "synthetic": False,
    }

    # Historical reviews are pre-published
    if partition == "historical":
        transformed["status"] = "published"

    return transformed


@click.command()
@click.option(
    "--input", "-i", "input_path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_INPUT,
    help="Path to raw Yelp reviews dataset (NDJSON)."
)
@click.option(
    "--businesses", "-b",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_BUSINESSES,
    help="Path to filtered businesses file (NDJSON)."
)
@click.option(
    "--historical-output",
    type=click.Path(path_type=Path),
    default=DEFAULT_HISTORICAL_OUTPUT,
    help="Path for historical reviews output (NDJSON)."
)
@click.option(
    "--streaming-output",
    type=click.Path(path_type=Path),
    default=DEFAULT_STREAMING_OUTPUT,
    help="Path for streaming reviews output (NDJSON)."
)
@click.option(
    "--historical-ratio",
    type=float,
    default=None,
    help="Ratio of reviews to assign to historical set (0.0-1.0)."
)
@click.option(
    "--seed",
    type=int,
    default=42,
    help="Random seed for reproducible partitioning."
)
@common_options
@env_option
def main(
    input_path: Path,
    businesses: Path,
    historical_output: Path,
    streaming_output: Path,
    historical_ratio: float,
    seed: int,
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Partition reviews into historical and streaming sets.

    Filters reviews to those for our filtered businesses, then randomly
    assigns them to either:
    - Historical (default 80%): Loaded into ES at startup, status="published"
    - Streaming (default 20%): Replayed during the workshop

    Prerequisites:
    - filter_businesses.py must have been run first

    Examples:

        # Partition with default 80/20 split
        python -m admin.partition_reviews

        # Custom split ratio
        python -m admin.partition_reviews --historical-ratio 0.9

        # Preview without writing
        python -m admin.partition_reviews --dry-run
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

    # Get historical ratio from config if not specified
    if historical_ratio is None:
        historical_ratio = config_data.get("data", {}).get(
            "historical_ratio", DEFAULT_HISTORICAL_RATIO
        )

    # Validate ratio
    if not 0.0 <= historical_ratio <= 1.0:
        echo_error("Historical ratio must be between 0.0 and 1.0")
        raise SystemExit(1)

    streaming_ratio = 1.0 - historical_ratio

    echo_info(f"Reviews input: {input_path}")
    echo_info(f"Businesses file: {businesses}")
    echo_info(f"Historical output: {historical_output}")
    echo_info(f"Streaming output: {streaming_output}")
    echo_info(f"Historical ratio: {historical_ratio:.0%}")
    echo_info(f"Streaming ratio: {streaming_ratio:.0%}")
    echo_info(f"Random seed: {seed}")

    # Validate input files
    if not businesses.exists():
        echo_error(f"Businesses file not found: {businesses}")
        echo_error("Run filter_businesses.py first.")
        raise SystemExit(1)

    if not input_path.exists():
        echo_error(f"Reviews file not found: {input_path}")
        raise SystemExit(1)

    # Create output directories
    historical_output.parent.mkdir(parents=True, exist_ok=True)
    streaming_output.parent.mkdir(parents=True, exist_ok=True)

    # Set random seed for reproducibility
    random.seed(seed)

    # Load business IDs
    echo_info("\nLoading business IDs...")
    business_ids = load_business_ids(businesses)
    echo_info(f"Loaded {len(business_ids):,} business IDs")

    # Count total reviews
    echo_info("\nCounting reviews...")
    total_lines = count_lines(input_path)
    echo_verbose(f"Total reviews in input: {total_lines}", verbose)

    # Process reviews
    historical_file = None
    streaming_file = None

    if not dry_run:
        historical_file = open(historical_output, "w")
        streaming_file = open(streaming_output, "w")

    historical_count = 0
    streaming_count = 0
    skipped_count = 0

    # Track star distribution
    historical_stars = {}
    streaming_stars = {}

    try:
        with open(input_path, "r") as f:
            for line in tqdm(f, total=total_lines, desc="Partitioning", unit="rec"):
                try:
                    review = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                # Filter by business
                if review.get("business_id") not in business_ids:
                    skipped_count += 1
                    continue

                # Randomly assign to partition
                if random.random() < historical_ratio:
                    partition = "historical"
                    historical_count += 1
                    target_file = historical_file
                    star_stats = historical_stars
                else:
                    partition = "streaming"
                    streaming_count += 1
                    target_file = streaming_file
                    star_stats = streaming_stars

                # Track star distribution
                stars = review.get("stars", 0)
                star_stats[stars] = star_stats.get(stars, 0) + 1

                # Transform and write
                transformed = transform_review(review, partition)

                if not dry_run:
                    target_file.write(json.dumps(transformed) + "\n")

    finally:
        if historical_file:
            historical_file.close()
        if streaming_file:
            streaming_file.close()

    # Print summary
    total_matched = historical_count + streaming_count
    echo_info(f"\nProcessed {total_lines:,} reviews")
    echo_info(f"Matched {total_matched:,} reviews for filtered businesses")
    echo_info(f"Skipped {skipped_count:,} reviews (business not in filter)")

    echo_info(f"\nPartition Summary:")
    echo_info(f"  Historical: {historical_count:,} ({historical_count/total_matched*100:.1f}%)")
    echo_info(f"  Streaming: {streaming_count:,} ({streaming_count/total_matched*100:.1f}%)")

    if verbose and historical_stars:
        echo_info(f"\nStar Distribution (Historical):")
        for stars in sorted(historical_stars.keys()):
            count = historical_stars[stars]
            pct = count / historical_count * 100
            echo_info(f"  {stars} stars: {count:,} ({pct:.1f}%)")

        echo_info(f"\nStar Distribution (Streaming):")
        for stars in sorted(streaming_stars.keys()):
            count = streaming_stars[stars]
            pct = count / streaming_count * 100
            echo_info(f"  {stars} stars: {count:,} ({pct:.1f}%)")

    if dry_run:
        echo_info("\n[DRY RUN] No files were written")
    else:
        echo_success(f"\nHistorical reviews written to: {historical_output}")
        echo_success(f"Streaming reviews written to: {streaming_output}")


if __name__ == "__main__":
    main()
