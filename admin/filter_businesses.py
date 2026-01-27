#!/usr/bin/env python3
"""
Filter Yelp business data for the Review Campaign Detection Workshop.

Reads the raw Yelp business dataset and filters to businesses
in specific cities and categories, adding workshop-specific fields.
"""

import json
import sys
from pathlib import Path
from typing import Optional, Set

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
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "yelp_academic_dataset_business.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "businesses.ndjson"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"

# Default filter settings (used if config not provided)
DEFAULT_CITIES = ["Las Vegas", "Phoenix", "Toronto"]
DEFAULT_CATEGORIES = ["Restaurants", "Food", "Bars", "Cafes"]


def matches_categories(business_categories: Optional[str], target_categories: Set[str]) -> bool:
    """
    Check if a business matches any of the target categories.

    Args:
        business_categories: Comma-separated category string from Yelp data
        target_categories: Set of category names to match

    Returns:
        bool: True if business has at least one matching category
    """
    if not business_categories:
        return False

    # Yelp categories are comma-separated
    categories = {c.strip() for c in business_categories.split(",")}
    return bool(categories & target_categories)


def transform_business(business: dict) -> dict:
    """
    Transform a Yelp business record for the workshop.

    Adds workshop-specific fields:
    - current_rating: Current rating (same as stars initially)
    - rating_protected: Whether business is under protection

    Args:
        business: Raw Yelp business record

    Returns:
        dict: Transformed business record
    """
    # Copy original fields
    transformed = {
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
        "categories": business.get("categories", "").split(", ") if business.get("categories") else [],
        "hours": business.get("hours"),
        "attributes": business.get("attributes"),
    }

    # Add workshop-specific fields
    transformed["current_rating"] = business.get("stars")
    transformed["rating_protected"] = False

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
    help="Path to raw Yelp business dataset (NDJSON)."
)
@click.option(
    "--output", "-o", "output_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT,
    help="Path for filtered output file (NDJSON)."
)
@click.option(
    "--limit", "-l",
    type=int,
    default=None,
    help="Maximum number of businesses to output."
)
@click.option(
    "--city",
    multiple=True,
    help="City to include (can be specified multiple times). "
         "Overrides config file settings."
)
@click.option(
    "--category",
    multiple=True,
    help="Category to include (can be specified multiple times). "
         "Overrides config file settings."
)
@common_options
@env_option
def main(
    input_path: Path,
    output_path: Path,
    limit: Optional[int],
    city: tuple,
    category: tuple,
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Filter Yelp business data for the workshop.

    Reads the raw Yelp business dataset and outputs businesses that:
    - Are located in specified cities
    - Have at least one matching category

    Adds workshop-specific fields like current_rating and rating_protected.

    Examples:

        # Filter with default settings from config
        python -m admin.filter_businesses

        # Filter specific cities
        python -m admin.filter_businesses --city "Las Vegas" --city "Phoenix"

        # Limit output for testing
        python -m admin.filter_businesses --limit 1000

        # Preview without writing
        python -m admin.filter_businesses --dry-run
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

    # Determine cities to filter
    if city:
        cities = set(city)
    else:
        cities = set(config_data.get("data", {}).get("cities", DEFAULT_CITIES))

    # Determine categories to filter
    if category:
        categories = set(category)
    else:
        categories = set(config_data.get("data", {}).get("categories", DEFAULT_CATEGORIES))

    # Get limit from config if not specified
    if limit is None:
        limit = config_data.get("data", {}).get("max_businesses")

    echo_info(f"Filtering businesses from: {input_path}")
    echo_info(f"Cities: {', '.join(sorted(cities))}")
    echo_info(f"Categories: {', '.join(sorted(categories))}")
    if limit:
        echo_info(f"Limit: {limit}")

    # Validate input file
    if not input_path.exists():
        echo_error(f"Input file not found: {input_path}")
        raise SystemExit(1)

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Count total lines for progress bar
    echo_info("Counting records...")
    total_lines = count_lines(input_path)
    echo_verbose(f"Total records in input: {total_lines}", verbose)

    # Process the file
    matched_count = 0
    processed_count = 0
    city_stats = {}
    category_stats = {}

    output_file = None
    if not dry_run:
        output_file = open(output_path, "w")

    try:
        with open(input_path, "r") as f:
            for line in tqdm(f, total=total_lines, desc="Filtering", unit="rec"):
                processed_count += 1

                try:
                    business = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                # Check city filter
                business_city = business.get("city")
                if business_city not in cities:
                    continue

                # Check category filter
                if not matches_categories(business.get("categories"), categories):
                    continue

                # Transform and output
                transformed = transform_business(business)

                if not dry_run:
                    output_file.write(json.dumps(transformed) + "\n")

                matched_count += 1

                # Track statistics
                city_stats[business_city] = city_stats.get(business_city, 0) + 1

                # Track category stats
                for cat in transformed.get("categories", []):
                    if cat in categories:
                        category_stats[cat] = category_stats.get(cat, 0) + 1

                # Check limit
                if limit and matched_count >= limit:
                    echo_info(f"Reached limit of {limit} businesses")
                    break

    finally:
        if output_file:
            output_file.close()

    # Print summary
    echo_info(f"\nProcessed {processed_count:,} records")
    echo_info(f"Matched {matched_count:,} businesses")

    if verbose:
        echo_info("\nBusinesses by city:")
        for city_name, count in sorted(city_stats.items(), key=lambda x: -x[1]):
            echo_info(f"  {city_name}: {count:,}")

        echo_info("\nBusinesses by category (top categories):")
        for cat, count in sorted(category_stats.items(), key=lambda x: -x[1])[:10]:
            echo_info(f"  {cat}: {count:,}")

    if dry_run:
        echo_info("\n[DRY RUN] No files were written")
    else:
        echo_success(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
