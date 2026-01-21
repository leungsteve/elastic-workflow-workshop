#!/usr/bin/env python3
"""
Bulk load data into Elasticsearch for the Review Bomb Workshop.

Loads processed businesses, users, and historical reviews into their
respective Elasticsearch indices using the bulk API.
"""

import json
from pathlib import Path
from typing import Iterator, Optional

import click
from tqdm import tqdm

from admin.utils.cli import (
    common_options,
    elasticsearch_options,
    env_option,
    load_config_file,
    echo_success,
    echo_error,
    echo_info,
    echo_warning,
    echo_verbose,
)
from admin.utils.elasticsearch import get_es_client


# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"

# Default data paths
DEFAULT_PATHS = {
    "businesses": PROJECT_ROOT / "data" / "processed" / "businesses.ndjson",
    "users": PROJECT_ROOT / "data" / "processed" / "users.ndjson",
    "reviews": PROJECT_ROOT / "data" / "historical" / "reviews.ndjson",
}

# Default index names
DEFAULT_INDICES = {
    "businesses": "businesses",
    "users": "users",
    "reviews": "reviews",
}

# Default batch size
DEFAULT_BATCH_SIZE = 5000


def count_lines(file_path: Path) -> int:
    """Count lines in a file efficiently."""
    count = 0
    with open(file_path, "rb") as f:
        for _ in f:
            count += 1
    return count


def read_ndjson_batches(
    file_path: Path,
    batch_size: int,
    id_field: str
) -> Iterator[tuple[list[dict], int]]:
    """
    Read NDJSON file in batches, yielding bulk actions.

    Args:
        file_path: Path to NDJSON file
        batch_size: Number of documents per batch
        id_field: Field to use as document ID

    Yields:
        Tuple of (batch of documents, count of documents read)
    """
    batch = []
    count = 0

    with open(file_path, "r") as f:
        for line in f:
            try:
                doc = json.loads(line.strip())
                batch.append(doc)
                count += 1

                if len(batch) >= batch_size:
                    yield batch, count
                    batch = []
            except json.JSONDecodeError:
                continue

    # Yield remaining documents
    if batch:
        yield batch, count


def bulk_index(
    es,
    index_name: str,
    documents: list[dict],
    id_field: str,
    dry_run: bool = False,
    verbose: bool = False
) -> tuple[int, int]:
    """
    Bulk index documents into Elasticsearch.

    Args:
        es: Elasticsearch client
        index_name: Target index name
        documents: List of documents to index
        id_field: Field to use as document ID
        dry_run: If True, don't actually index
        verbose: If True, print detailed output

    Returns:
        Tuple of (success_count, error_count)
    """
    if dry_run:
        return len(documents), 0

    # Build bulk request body
    bulk_body = []
    for doc in documents:
        doc_id = doc.get(id_field)
        if not doc_id:
            continue

        # Add index action
        bulk_body.append({"index": {"_index": index_name, "_id": doc_id}})
        bulk_body.append(doc)

    if not bulk_body:
        return 0, 0

    # Execute bulk request
    try:
        response = es.bulk(body=bulk_body, refresh=False)

        # Count successes and errors
        success_count = 0
        error_count = 0

        for item in response.get("items", []):
            if "index" in item:
                if item["index"].get("error"):
                    error_count += 1
                    if verbose:
                        echo_warning(f"Index error: {item['index']['error']}")
                else:
                    success_count += 1

        return success_count, error_count

    except Exception as e:
        echo_error(f"Bulk indexing error: {e}")
        return 0, len(documents)


def load_data_file(
    es,
    file_path: Path,
    index_name: str,
    id_field: str,
    batch_size: int,
    dry_run: bool = False,
    verbose: bool = False
) -> tuple[int, int]:
    """
    Load a single data file into Elasticsearch.

    Args:
        es: Elasticsearch client
        file_path: Path to NDJSON file
        index_name: Target index name
        id_field: Field to use as document ID
        batch_size: Number of documents per bulk request
        dry_run: If True, don't actually index
        verbose: If True, print detailed output

    Returns:
        Tuple of (total_success, total_errors)
    """
    if not file_path.exists():
        echo_error(f"File not found: {file_path}")
        return 0, 0

    # Count total lines for progress bar
    total_lines = count_lines(file_path)

    total_success = 0
    total_errors = 0

    with tqdm(total=total_lines, desc=f"Loading {index_name}", unit="doc") as pbar:
        for batch, _ in read_ndjson_batches(file_path, batch_size, id_field):
            success, errors = bulk_index(
                es, index_name, batch, id_field,
                dry_run=dry_run, verbose=verbose
            )
            total_success += success
            total_errors += errors
            pbar.update(len(batch))

    return total_success, total_errors


@click.command()
@click.option(
    "--data-type", "-t",
    type=click.Choice(["businesses", "users", "reviews", "all"]),
    default="all",
    help="Type of data to load."
)
@click.option(
    "--batch-size",
    type=int,
    default=None,
    help=f"Number of documents per bulk request (default: {DEFAULT_BATCH_SIZE})."
)
@click.option(
    "--businesses-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to businesses NDJSON file."
)
@click.option(
    "--users-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to users NDJSON file."
)
@click.option(
    "--reviews-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to reviews NDJSON file."
)
@common_options
@elasticsearch_options
@env_option
def main(
    data_type: str,
    batch_size: Optional[int],
    businesses_file: Optional[Path],
    users_file: Optional[Path],
    reviews_file: Optional[Path],
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Bulk load data into Elasticsearch.

    Loads processed data files into their respective indices:
    - businesses: Business profiles
    - users: User profiles with trust scores
    - reviews: Historical reviews (pre-published)

    Prerequisites:
    - create_indices.py must have been run first
    - Data processing scripts must have been run

    Examples:

        # Load all data
        python -m admin.load_data

        # Load only businesses
        python -m admin.load_data -t businesses

        # Custom batch size
        python -m admin.load_data --batch-size 10000

        # Preview without loading
        python -m admin.load_data --dry-run
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

    # Get batch size from config if not specified
    if batch_size is None:
        batch_size = config_data.get("elasticsearch", {}).get(
            "bulk_batch_size", DEFAULT_BATCH_SIZE
        )

    # Get index names from config
    index_config = config_data.get("elasticsearch", {}).get("indices", {})
    indices = {
        "businesses": index_config.get("businesses", DEFAULT_INDICES["businesses"]),
        "users": index_config.get("users", DEFAULT_INDICES["users"]),
        "reviews": index_config.get("reviews", DEFAULT_INDICES["reviews"]),
    }

    # Determine file paths
    paths = {
        "businesses": businesses_file or DEFAULT_PATHS["businesses"],
        "users": users_file or DEFAULT_PATHS["users"],
        "reviews": reviews_file or DEFAULT_PATHS["reviews"],
    }

    # ID fields for each data type
    id_fields = {
        "businesses": "business_id",
        "users": "user_id",
        "reviews": "review_id",
    }

    # Determine what to load
    if data_type == "all":
        data_types = ["businesses", "users", "reviews"]
    else:
        data_types = [data_type]

    echo_info(f"Data types to load: {', '.join(data_types)}")
    echo_info(f"Batch size: {batch_size}")

    if dry_run:
        echo_info("[DRY RUN] No data will be loaded")

    # Get Elasticsearch client
    try:
        es = get_es_client()
        es.info()
        echo_verbose("Connected to Elasticsearch", verbose)
    except Exception as e:
        echo_error(f"Failed to connect to Elasticsearch: {e}")
        raise SystemExit(1)

    # Check that indices exist
    for dt in data_types:
        index_name = indices[dt]
        if not es.indices.exists(index=index_name):
            echo_error(f"Index '{index_name}' does not exist.")
            echo_error("Run create_indices.py first.")
            raise SystemExit(1)

    # Load each data type
    results = {}

    for dt in data_types:
        echo_info(f"\nLoading {dt}...")

        file_path = paths[dt]
        index_name = indices[dt]
        id_field = id_fields[dt]

        if not file_path.exists():
            echo_warning(f"File not found: {file_path}")
            results[dt] = {"success": 0, "errors": 0, "skipped": True}
            continue

        success, errors = load_data_file(
            es, file_path, index_name, id_field, batch_size,
            dry_run=dry_run, verbose=verbose
        )

        results[dt] = {"success": success, "errors": errors, "skipped": False}

        if not dry_run:
            # Refresh index to make documents searchable
            es.indices.refresh(index=index_name)

    # Print summary
    echo_info("\n" + "=" * 50)
    echo_info("Load Summary")
    echo_info("=" * 50)

    total_success = 0
    total_errors = 0

    for dt in data_types:
        result = results[dt]
        if result.get("skipped"):
            echo_info(f"{dt}: SKIPPED (file not found)")
        else:
            echo_info(
                f"{dt}: {result['success']:,} loaded, "
                f"{result['errors']} errors"
            )
            total_success += result["success"]
            total_errors += result["errors"]

    echo_info("-" * 50)
    echo_info(f"Total: {total_success:,} documents loaded, {total_errors} errors")

    if dry_run:
        echo_info("\n[DRY RUN] No data was actually loaded")

    if total_errors > 0:
        echo_warning(f"\n{total_errors} documents failed to load")
        raise SystemExit(1)
    else:
        echo_success("\nData loading complete!")


if __name__ == "__main__":
    main()
