#!/usr/bin/env python3
"""
Reset the workshop environment by removing attack data.

This script cleans up after attack simulations by:
1. Removing simulated/attack reviews
2. Removing attacker user accounts
3. Resetting business protection flags
4. Clearing incidents
5. Clearing notifications

Use this to reset the environment for a fresh workshop run.
"""

import json
from pathlib import Path
from typing import Optional

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


def delete_attack_reviews(es, index: str, dry_run: bool = False) -> int:
    """
    Delete all simulated/attack reviews.

    Returns count of deleted reviews.
    """
    query = {
        "bool": {
            "should": [
                {"term": {"is_simulated": True}},
                {"prefix": {"user_id": "attacker_"}},
            ],
            "minimum_should_match": 1
        }
    }

    # First count
    count_response = es.count(index=index, query=query)
    count = count_response.get("count", 0)

    if count == 0:
        return 0

    if dry_run:
        return count

    # Delete by query
    response = es.delete_by_query(
        index=index,
        query=query,
        refresh=True,
        conflicts="proceed"
    )

    return response.get("deleted", 0)


def delete_attacker_users(es, index: str, dry_run: bool = False) -> int:
    """
    Delete all attacker user accounts.

    Returns count of deleted users.
    """
    query = {
        "bool": {
            "should": [
                {"term": {"is_attacker": True}},
                {"prefix": {"user_id": "attacker_"}},
            ],
            "minimum_should_match": 1
        }
    }

    # First count
    count_response = es.count(index=index, query=query)
    count = count_response.get("count", 0)

    if count == 0:
        return 0

    if dry_run:
        return count

    # Delete by query
    response = es.delete_by_query(
        index=index,
        query=query,
        refresh=True,
        conflicts="proceed"
    )

    return response.get("deleted", 0)


def reset_business_protection(es, index: str, dry_run: bool = False) -> int:
    """
    Reset protection flags on all businesses.

    Returns count of updated businesses.
    """
    query = {"term": {"rating_protected": True}}

    # First count
    count_response = es.count(index=index, query=query)
    count = count_response.get("count", 0)

    if count == 0:
        return 0

    if dry_run:
        return count

    # Update by query
    response = es.update_by_query(
        index=index,
        query=query,
        script={
            "source": """
                ctx._source.rating_protected = false;
                ctx._source.remove('protection_reason');
                ctx._source.remove('protected_since');
            """,
            "lang": "painless"
        },
        refresh=True,
        conflicts="proceed"
    )

    return response.get("updated", 0)


def delete_all_incidents(es, index: str, dry_run: bool = False) -> int:
    """
    Delete all incidents.

    Returns count of deleted incidents.
    """
    # Check if index exists
    if not es.indices.exists(index=index):
        return 0

    # Count all documents
    count_response = es.count(index=index, query={"match_all": {}})
    count = count_response.get("count", 0)

    if count == 0:
        return 0

    if dry_run:
        return count

    # Delete all
    response = es.delete_by_query(
        index=index,
        query={"match_all": {}},
        refresh=True,
        conflicts="proceed"
    )

    return response.get("deleted", 0)


def delete_all_notifications(es, index: str, dry_run: bool = False) -> int:
    """
    Delete all notifications.

    Returns count of deleted notifications.
    """
    # Check if index exists
    if not es.indices.exists(index=index):
        return 0

    # Count all documents
    count_response = es.count(index=index, query={"match_all": {}})
    count = count_response.get("count", 0)

    if count == 0:
        return 0

    if dry_run:
        return count

    # Delete all
    response = es.delete_by_query(
        index=index,
        query={"match_all": {}},
        refresh=True,
        conflicts="proceed"
    )

    return response.get("deleted", 0)


def reset_held_reviews(es, index: str, dry_run: bool = False) -> int:
    """
    Reset any held reviews back to published status.
    (Only for legitimate reviews that were accidentally held)

    Returns count of updated reviews.
    """
    # Only reset non-simulated held reviews
    query = {
        "bool": {
            "must": [
                {"term": {"status": "held"}},
            ],
            "must_not": [
                {"term": {"is_simulated": True}},
                {"prefix": {"user_id": "attacker_"}},
            ]
        }
    }

    # First count
    count_response = es.count(index=index, query=query)
    count = count_response.get("count", 0)

    if count == 0:
        return 0

    if dry_run:
        return count

    # Update by query
    response = es.update_by_query(
        index=index,
        query=query,
        script={
            "source": "ctx._source.status = 'published'",
            "lang": "painless"
        },
        refresh=True,
        conflicts="proceed"
    )

    return response.get("updated", 0)


@click.command()
@click.option(
    "--reviews/--no-reviews",
    default=True,
    help="Delete attack reviews (default: yes)."
)
@click.option(
    "--users/--no-users",
    default=True,
    help="Delete attacker users (default: yes)."
)
@click.option(
    "--protection/--no-protection",
    default=True,
    help="Reset business protection flags (default: yes)."
)
@click.option(
    "--incidents/--no-incidents",
    default=True,
    help="Delete all incidents (default: yes)."
)
@click.option(
    "--notifications/--no-notifications",
    default=True,
    help="Delete all notifications (default: yes)."
)
@click.option(
    "--held-reviews/--no-held-reviews",
    default=True,
    help="Reset held reviews to published (default: yes)."
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt."
)
@common_options
@elasticsearch_options
@env_option
def main(
    reviews: bool,
    users: bool,
    protection: bool,
    incidents: bool,
    notifications: bool,
    held_reviews: bool,
    yes: bool,
    dry_run: bool,
    verbose: bool,
    config: str
):
    """
    Reset the workshop environment.

    Removes attack data and resets the environment for a fresh run.
    This is useful when workshop attendees want to re-run the attack
    simulation from scratch.

    Examples:

        # Full reset (with confirmation)
        python -m admin.reset_environment

        # Full reset (skip confirmation)
        python -m admin.reset_environment -y

        # Preview what would be reset
        python -m admin.reset_environment --dry-run

        # Only reset reviews and users (keep incidents for review)
        python -m admin.reset_environment --no-incidents --no-notifications

        # Only clear incidents
        python -m admin.reset_environment --no-reviews --no-users --no-protection
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

    # Get index names from config
    index_config = config_data.get("elasticsearch", {}).get("indices", {})
    indices = {
        "businesses": index_config.get("businesses", "businesses"),
        "users": index_config.get("users", "users"),
        "reviews": index_config.get("reviews", "reviews"),
        "incidents": index_config.get("incidents", "incidents"),
        "notifications": index_config.get("notifications", "notifications"),
    }

    echo_info("=" * 50)
    echo_info("WORKSHOP ENVIRONMENT RESET")
    echo_info("=" * 50)

    if dry_run:
        echo_info("[DRY RUN] Preview mode - no changes will be made\n")

    # Connect to Elasticsearch
    try:
        es = get_es_client()
        es.info()
        echo_verbose("Connected to Elasticsearch", verbose)
    except Exception as e:
        echo_error(f"Failed to connect to Elasticsearch: {e}")
        raise SystemExit(1)

    # Preview what will be reset
    echo_info("\nActions to perform:")
    actions = []

    if reviews:
        count = delete_attack_reviews(es, indices["reviews"], dry_run=True)
        actions.append(("Delete attack reviews", count, indices["reviews"]))
        echo_info(f"  - Delete {count:,} attack reviews")

    if users:
        count = delete_attacker_users(es, indices["users"], dry_run=True)
        actions.append(("Delete attacker users", count, indices["users"]))
        echo_info(f"  - Delete {count:,} attacker users")

    if protection:
        count = reset_business_protection(es, indices["businesses"], dry_run=True)
        actions.append(("Reset business protection", count, indices["businesses"]))
        echo_info(f"  - Reset protection on {count:,} businesses")

    if incidents:
        count = delete_all_incidents(es, indices["incidents"], dry_run=True)
        actions.append(("Delete incidents", count, indices["incidents"]))
        echo_info(f"  - Delete {count:,} incidents")

    if notifications:
        count = delete_all_notifications(es, indices["notifications"], dry_run=True)
        actions.append(("Delete notifications", count, indices["notifications"]))
        echo_info(f"  - Delete {count:,} notifications")

    if held_reviews:
        count = reset_held_reviews(es, indices["reviews"], dry_run=True)
        actions.append(("Reset held reviews", count, indices["reviews"]))
        echo_info(f"  - Reset {count:,} held reviews to published")

    # Check if there's anything to do
    total_changes = sum(a[1] for a in actions)
    if total_changes == 0:
        echo_info("\nNo attack data found. Environment is already clean.")
        return

    if dry_run:
        echo_info(f"\n[DRY RUN] Would affect {total_changes:,} documents total")
        echo_info("Run without --dry-run to apply changes")
        return

    # Confirm
    if not yes:
        echo_warning(f"\nThis will modify {total_changes:,} documents.")
        if not click.confirm("Continue?"):
            echo_info("Cancelled.")
            return

    # Execute reset
    echo_info("\nResetting environment...")
    results = {}

    if reviews:
        deleted = delete_attack_reviews(es, indices["reviews"])
        results["Attack reviews deleted"] = deleted
        echo_info(f"  Deleted {deleted:,} attack reviews")

    if users:
        deleted = delete_attacker_users(es, indices["users"])
        results["Attacker users deleted"] = deleted
        echo_info(f"  Deleted {deleted:,} attacker users")

    if protection:
        updated = reset_business_protection(es, indices["businesses"])
        results["Businesses reset"] = updated
        echo_info(f"  Reset protection on {updated:,} businesses")

    if incidents:
        deleted = delete_all_incidents(es, indices["incidents"])
        results["Incidents deleted"] = deleted
        echo_info(f"  Deleted {deleted:,} incidents")

    if notifications:
        deleted = delete_all_notifications(es, indices["notifications"])
        results["Notifications deleted"] = deleted
        echo_info(f"  Deleted {deleted:,} notifications")

    if held_reviews:
        updated = reset_held_reviews(es, indices["reviews"])
        results["Held reviews reset"] = updated
        echo_info(f"  Reset {updated:,} held reviews")

    # Summary
    echo_info("\n" + "=" * 50)
    echo_info("RESET COMPLETE")
    echo_info("=" * 50)

    for action, count in results.items():
        echo_info(f"  {action}: {count:,}")

    echo_success("\nEnvironment is ready for a fresh attack simulation!")


if __name__ == "__main__":
    main()
