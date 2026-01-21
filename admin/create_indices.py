#!/usr/bin/env python3
"""
Create Elasticsearch indices for the Review Bomb Workshop.

Reads mapping definitions from the mappings/ directory and creates
indices with the specified settings and mappings.
"""

import json
from pathlib import Path

import click

from admin.utils.cli import (
    common_options,
    elasticsearch_options,
    env_option,
    echo_success,
    echo_error,
    echo_info,
    echo_warning,
    echo_verbose,
    confirm_action,
)
from admin.utils.elasticsearch import get_es_client


# Default mappings directory relative to project root
DEFAULT_MAPPINGS_DIR = Path(__file__).parent.parent / "mappings"


def load_mapping(mapping_path: Path) -> dict:
    """
    Load a mapping definition from a JSON file.

    Args:
        mapping_path: Path to the mapping JSON file

    Returns:
        dict: The mapping definition including settings and mappings
    """
    with open(mapping_path, "r") as f:
        return json.load(f)


def get_index_name_from_path(mapping_path: Path) -> str:
    """
    Extract index name from mapping file path.

    Args:
        mapping_path: Path to mapping file (e.g., mappings/businesses.json)

    Returns:
        str: Index name (e.g., "businesses")
    """
    return mapping_path.stem


def create_index(
    es,
    index_name: str,
    mapping: dict,
    dry_run: bool = False,
    verbose: bool = False
) -> bool:
    """
    Create an Elasticsearch index with the given mapping.

    Args:
        es: Elasticsearch client
        index_name: Name of the index to create
        mapping: Index mapping definition
        dry_run: If True, only simulate the action
        verbose: If True, print detailed output

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if dry_run:
            echo_info(f"[DRY RUN] Would create index: {index_name}")
            if verbose:
                echo_verbose(f"Mapping: {json.dumps(mapping, indent=2)}", verbose)
            return True

        # Extract settings and mappings from the definition
        settings = mapping.get("settings", {})
        mappings = mapping.get("mappings", {})

        # Create the index
        es.indices.create(
            index=index_name,
            settings=settings,
            mappings=mappings
        )

        echo_success(f"Created index: {index_name}")
        return True

    except Exception as e:
        echo_error(f"Failed to create index {index_name}: {e}")
        return False


def delete_index(
    es,
    index_name: str,
    dry_run: bool = False,
    verbose: bool = False
) -> bool:
    """
    Delete an Elasticsearch index.

    Args:
        es: Elasticsearch client
        index_name: Name of the index to delete
        dry_run: If True, only simulate the action
        verbose: If True, print detailed output

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if dry_run:
            echo_info(f"[DRY RUN] Would delete index: {index_name}")
            return True

        es.indices.delete(index=index_name)
        echo_success(f"Deleted index: {index_name}")
        return True

    except Exception as e:
        echo_error(f"Failed to delete index {index_name}: {e}")
        return False


@click.command()
@click.option(
    "--mappings-dir", "-m",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_MAPPINGS_DIR,
    help="Directory containing mapping JSON files."
)
@click.option(
    "--index", "-i",
    multiple=True,
    help="Specific index to create (can be specified multiple times). "
         "If not provided, creates all indices found in mappings directory."
)
@click.option(
    "--delete-existing",
    is_flag=True,
    default=False,
    help="Delete existing indices before creating new ones."
)
@click.option(
    "--force", "-f",
    is_flag=True,
    default=False,
    help="Skip confirmation prompts."
)
@common_options
@elasticsearch_options
@env_option
def main(
    mappings_dir: Path,
    index: tuple,
    delete_existing: bool,
    force: bool,
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Create Elasticsearch indices from mapping definitions.

    Reads mapping JSON files from the mappings directory and creates
    the corresponding Elasticsearch indices. Each JSON file should contain
    both 'settings' and 'mappings' keys.

    Examples:

        # Create all indices
        python -m admin.create_indices

        # Create specific indices
        python -m admin.create_indices -i businesses -i users

        # Delete existing indices first
        python -m admin.create_indices --delete-existing

        # Preview what would be created
        python -m admin.create_indices --dry-run
    """
    # Find all mapping files
    mapping_files = list(mappings_dir.glob("*.json"))

    if not mapping_files:
        echo_error(f"No mapping files found in {mappings_dir}")
        raise SystemExit(1)

    # Filter to specific indices if requested
    if index:
        mapping_files = [
            f for f in mapping_files
            if get_index_name_from_path(f) in index
        ]
        if not mapping_files:
            echo_error(f"No mapping files found for indices: {', '.join(index)}")
            raise SystemExit(1)

    echo_info(f"Found {len(mapping_files)} mapping file(s)")

    # Get Elasticsearch client
    try:
        es = get_es_client()
        # Test connection
        es.info()
        echo_verbose("Connected to Elasticsearch", verbose)
    except Exception as e:
        echo_error(f"Failed to connect to Elasticsearch: {e}")
        raise SystemExit(1)

    # Check which indices already exist
    existing_indices = []
    for mapping_file in mapping_files:
        index_name = get_index_name_from_path(mapping_file)
        if es.indices.exists(index=index_name):
            existing_indices.append(index_name)

    if existing_indices and not delete_existing:
        echo_warning(f"The following indices already exist: {', '.join(existing_indices)}")
        echo_info("Use --delete-existing to recreate them, or they will be skipped.")

    # Handle deletion of existing indices
    if delete_existing and existing_indices:
        if not dry_run and not force:
            if not confirm_action(
                f"Delete {len(existing_indices)} existing indices? This cannot be undone.",
                default=False,
                abort=False
            ):
                echo_info("Aborted.")
                raise SystemExit(0)

        for index_name in existing_indices:
            delete_index(es, index_name, dry_run=dry_run, verbose=verbose)

    # Create indices
    success_count = 0
    skip_count = 0
    fail_count = 0

    for mapping_file in mapping_files:
        index_name = get_index_name_from_path(mapping_file)

        # Skip if exists and not deleting
        if index_name in existing_indices and not delete_existing:
            echo_info(f"Skipping existing index: {index_name}")
            skip_count += 1
            continue

        # Load mapping
        try:
            mapping = load_mapping(mapping_file)
            echo_verbose(f"Loaded mapping from {mapping_file}", verbose)
        except Exception as e:
            echo_error(f"Failed to load mapping from {mapping_file}: {e}")
            fail_count += 1
            continue

        # Create index
        if create_index(es, index_name, mapping, dry_run=dry_run, verbose=verbose):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    echo_info(f"\nSummary: {success_count} created, {skip_count} skipped, {fail_count} failed")

    if fail_count > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
