#!/usr/bin/env python3
"""
Create Elasticsearch indices for the Review Campaign Detection Workshop.

Reads mapping definitions from the mappings/ directory and creates
indices with the specified settings and mappings.
"""

import json
import sys
from pathlib import Path
from copy import deepcopy

# Allow running as script or module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))

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

# ELSER inference endpoint ID
ELSER_INFERENCE_ID = ".elser-2-elasticsearch"


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


def check_elser_available(es, verbose: bool = False) -> bool:
    """
    Check if the ELSER inference endpoint is available.

    Args:
        es: Elasticsearch client
        verbose: If True, print detailed output

    Returns:
        bool: True if ELSER is available, False otherwise
    """
    try:
        # Try to get the inference endpoint
        response = es.inference.get(inference_id=ELSER_INFERENCE_ID)
        echo_verbose(f"ELSER inference endpoint '{ELSER_INFERENCE_ID}' is available", verbose)
        return True
    except Exception as e:
        error_str = str(e)
        # Check for 404 or "resource not found" type errors
        if "404" in error_str or "resource_not_found" in error_str.lower() or "not found" in error_str.lower():
            echo_verbose(f"ELSER inference endpoint '{ELSER_INFERENCE_ID}' not found", verbose)
        else:
            echo_verbose(f"Error checking ELSER endpoint: {e}", verbose)
        return False


def has_semantic_text_field(mapping: dict) -> bool:
    """
    Check if a mapping contains any semantic_text fields.

    Args:
        mapping: The index mapping definition

    Returns:
        bool: True if mapping contains semantic_text fields
    """
    properties = mapping.get("mappings", {}).get("properties", {})
    for field_name, field_def in properties.items():
        if field_def.get("type") == "semantic_text":
            return True
    return False


def get_semantic_text_fields(mapping: dict) -> list[tuple[str, str]]:
    """
    Get all semantic_text fields and their inference IDs from a mapping.

    Args:
        mapping: The index mapping definition

    Returns:
        list: List of tuples (field_name, inference_id)
    """
    fields = []
    properties = mapping.get("mappings", {}).get("properties", {})
    for field_name, field_def in properties.items():
        if field_def.get("type") == "semantic_text":
            inference_id = field_def.get("inference_id", "unknown")
            fields.append((field_name, inference_id))
    return fields


def remove_semantic_text_fields(mapping: dict) -> dict:
    """
    Remove semantic_text fields and their copy_to references from a mapping.

    Args:
        mapping: The original index mapping definition

    Returns:
        dict: Modified mapping without semantic_text fields
    """
    modified = deepcopy(mapping)
    properties = modified.get("mappings", {}).get("properties", {})

    # Find semantic_text field names
    semantic_fields = set()
    for field_name, field_def in list(properties.items()):
        if field_def.get("type") == "semantic_text":
            semantic_fields.add(field_name)
            del properties[field_name]

    # Remove copy_to references to semantic_text fields
    for field_name, field_def in properties.items():
        if "copy_to" in field_def:
            copy_to = field_def["copy_to"]
            if isinstance(copy_to, str) and copy_to in semantic_fields:
                del field_def["copy_to"]
            elif isinstance(copy_to, list):
                field_def["copy_to"] = [f for f in copy_to if f not in semantic_fields]
                if not field_def["copy_to"]:
                    del field_def["copy_to"]

    return modified


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
@click.option(
    "--skip-semantic",
    is_flag=True,
    default=False,
    help="Skip semantic_text fields (for environments without ELSER). "
         "Indices will be created without semantic search capabilities."
)
@common_options
@elasticsearch_options
@env_option
def main(
    mappings_dir: Path,
    index: tuple,
    delete_existing: bool,
    force: bool,
    skip_semantic: bool,
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Create Elasticsearch indices from mapping definitions.

    Reads mapping JSON files from the mappings directory and creates
    the corresponding Elasticsearch indices. Each JSON file should contain
    both 'settings' and 'mappings' keys.

    For indices with semantic_text fields (like reviews), the ELSER inference
    endpoint must be available. Use --skip-semantic to create indices without
    semantic search capabilities if ELSER is not available.

    Examples:

        # Create all indices
        python -m admin.create_indices

        # Create specific indices
        python -m admin.create_indices -i businesses -i users

        # Delete existing indices first
        python -m admin.create_indices --delete-existing

        # Preview what would be created
        python -m admin.create_indices --dry-run

        # Create without semantic_text fields (no ELSER required)
        python -m admin.create_indices --skip-semantic
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

    # Check for semantic_text fields and ELSER availability
    indices_with_semantic = []
    for mapping_file in mapping_files:
        try:
            mapping = load_mapping(mapping_file)
            if has_semantic_text_field(mapping):
                index_name = get_index_name_from_path(mapping_file)
                semantic_fields = get_semantic_text_fields(mapping)
                indices_with_semantic.append((index_name, semantic_fields))
        except Exception:
            pass  # Will be handled during index creation

    elser_available = False
    if indices_with_semantic and not skip_semantic:
        echo_info("Checking ELSER inference endpoint availability...")
        elser_available = check_elser_available(es, verbose)

        if elser_available:
            echo_success(f"ELSER inference endpoint '{ELSER_INFERENCE_ID}' is available")
            echo_info("Semantic search will be enabled for applicable indices")
        else:
            echo_warning(f"ELSER inference endpoint '{ELSER_INFERENCE_ID}' is NOT available")
            echo_info("")
            echo_info("Indices with semantic_text fields:")
            for idx_name, fields in indices_with_semantic:
                field_info = ", ".join([f"{f[0]} (inference: {f[1]})" for f in fields])
                echo_info(f"  - {idx_name}: {field_info}")
            echo_info("")
            echo_error("Cannot create indices with semantic_text fields without ELSER.")
            echo_info("")
            echo_info("Options:")
            echo_info("  1. Deploy ELSER: Go to Kibana > Machine Learning > Trained Models")
            echo_info("     and deploy the '.elser_model_2' or '.elser_model_2_linux-x86_64' model")
            echo_info("  2. Use --skip-semantic flag to create indices without semantic search")
            echo_info("")
            echo_info("Example with --skip-semantic:")
            echo_info("  python -m admin.create_indices --skip-semantic")
            raise SystemExit(1)

    if skip_semantic and indices_with_semantic:
        echo_warning("--skip-semantic flag set: semantic_text fields will be removed")
        for idx_name, fields in indices_with_semantic:
            field_names = ", ".join([f[0] for f in fields])
            echo_info(f"  - {idx_name}: removing fields [{field_names}]")
        echo_info("Semantic search will NOT be available for these indices")

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
    semantic_enabled_count = 0

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

        # Check for semantic_text fields and handle accordingly
        has_semantic = has_semantic_text_field(mapping)
        if has_semantic and skip_semantic:
            echo_info(f"Removing semantic_text fields from {index_name} mapping")
            mapping = remove_semantic_text_fields(mapping)
        elif has_semantic and elser_available:
            semantic_enabled_count += 1

        # Create index
        if create_index(es, index_name, mapping, dry_run=dry_run, verbose=verbose):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    echo_info(f"\nSummary: {success_count} created, {skip_count} skipped, {fail_count} failed")

    if semantic_enabled_count > 0:
        echo_success(f"Semantic search enabled for {semantic_enabled_count} index(es)")

    if skip_semantic and indices_with_semantic:
        echo_warning("Note: Semantic search is disabled. Re-run without --skip-semantic after deploying ELSER.")

    if fail_count > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
