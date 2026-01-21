#!/usr/bin/env python3
"""
Verify the workshop environment is properly set up.

Checks:
- Elasticsearch connection
- Index existence and document counts
- Required data files
- ELSER availability (optional)
"""

import sys
from pathlib import Path

import click

from admin.utils.cli import (
    elasticsearch_options,
    env_option,
    load_config_file,
    echo_success,
    echo_error,
    echo_info,
    echo_warning,
    echo_verbose,
)
from admin.utils.elasticsearch import (
    get_es_client,
    test_connection,
    check_elser_available,
    get_index_info,
)


# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"

# Required data files
REQUIRED_FILES = {
    "Raw Yelp business data": PROJECT_ROOT / "data" / "raw" / "yelp_academic_dataset_business.json",
    "Raw Yelp review data": PROJECT_ROOT / "data" / "raw" / "yelp_academic_dataset_review.json",
    "Raw Yelp user data": PROJECT_ROOT / "data" / "raw" / "yelp_academic_dataset_user.json",
}

PROCESSED_FILES = {
    "Processed businesses": PROJECT_ROOT / "data" / "processed" / "businesses.ndjson",
    "Processed users": PROJECT_ROOT / "data" / "processed" / "users.ndjson",
    "Historical reviews": PROJECT_ROOT / "data" / "historical" / "reviews.ndjson",
    "Streaming reviews": PROJECT_ROOT / "data" / "streaming" / "reviews.ndjson",
}

# Default minimum document counts
MIN_COUNTS = {
    "businesses": 1000,
    "users": 1000,
    "reviews": 10000,
}


class VerificationResult:
    """Tracks verification results."""

    def __init__(self):
        self.checks = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def add_pass(self, name: str, message: str = ""):
        """Record a passed check."""
        self.checks.append(("PASS", name, message))
        self.passed += 1
        echo_success(f"{name}: {message}" if message else name)

    def add_fail(self, name: str, message: str = ""):
        """Record a failed check."""
        self.checks.append(("FAIL", name, message))
        self.failed += 1
        echo_error(f"{name}: {message}" if message else name)

    def add_warning(self, name: str, message: str = ""):
        """Record a warning."""
        self.checks.append(("WARN", name, message))
        self.warnings += 1
        echo_warning(f"{name}: {message}" if message else name)

    def is_success(self) -> bool:
        """Return True if no critical failures."""
        return self.failed == 0


def check_elasticsearch_connection(result: VerificationResult, verbose: bool) -> bool:
    """
    Check Elasticsearch connection.

    Returns:
        bool: True if connected, False otherwise
    """
    echo_info("\nChecking Elasticsearch connection...")

    try:
        es = get_es_client()
        info = es.info()

        result.add_pass(
            "Elasticsearch connection",
            f"Connected to {info['cluster_name']} v{info['version']['number']}"
        )

        # Check cluster health
        health = es.cluster.health()
        status = health["status"]

        if status == "green":
            result.add_pass("Cluster health", "green")
        elif status == "yellow":
            result.add_warning("Cluster health", "yellow (some replicas unavailable)")
        else:
            result.add_fail("Cluster health", f"{status}")

        return True

    except Exception as e:
        result.add_fail("Elasticsearch connection", str(e))
        return False


def check_indices(result: VerificationResult, config_data: dict, verbose: bool):
    """Check that required indices exist and have documents."""
    echo_info("\nChecking Elasticsearch indices...")

    # Get index names from config
    index_config = config_data.get("elasticsearch", {}).get("indices", {})
    indices = {
        "businesses": index_config.get("businesses", "businesses"),
        "users": index_config.get("users", "users"),
        "reviews": index_config.get("reviews", "reviews"),
        "incidents": index_config.get("incidents", "incidents"),
        "notifications": index_config.get("notifications", "notifications"),
    }

    for name, index_name in indices.items():
        info = get_index_info(index_name)

        if info is None:
            result.add_fail(f"Index '{index_name}'", "does not exist")
            continue

        doc_count = info.get("doc_count", 0)
        min_count = MIN_COUNTS.get(name, 0)

        if doc_count >= min_count:
            result.add_pass(f"Index '{index_name}'", f"{doc_count:,} documents")
        elif doc_count > 0:
            result.add_warning(
                f"Index '{index_name}'",
                f"{doc_count:,} documents (expected >= {min_count:,})"
            )
        else:
            result.add_warning(f"Index '{index_name}'", "empty (0 documents)")


def check_raw_files(result: VerificationResult, verbose: bool):
    """Check that raw data files exist."""
    echo_info("\nChecking raw data files...")

    for name, path in REQUIRED_FILES.items():
        if path.exists():
            # Get file size
            size_mb = path.stat().st_size / (1024 * 1024)
            result.add_pass(name, f"{size_mb:.1f} MB")
        else:
            result.add_fail(name, f"not found at {path}")


def check_processed_files(result: VerificationResult, verbose: bool):
    """Check that processed data files exist."""
    echo_info("\nChecking processed data files...")

    for name, path in PROCESSED_FILES.items():
        if path.exists():
            # Count lines and get size
            size_mb = path.stat().st_size / (1024 * 1024)

            # Quick line count
            with open(path, "rb") as f:
                line_count = sum(1 for _ in f)

            result.add_pass(name, f"{line_count:,} records ({size_mb:.1f} MB)")
        else:
            result.add_warning(name, f"not found (run data preparation scripts)")


def check_elser(result: VerificationResult, config_data: dict, verbose: bool):
    """Check ELSER availability (optional)."""
    echo_info("\nChecking ELSER (optional)...")

    elser_config = config_data.get("elser", {})
    inference_id = elser_config.get("inference_id", "elser")

    if check_elser_available(inference_id):
        result.add_pass("ELSER", f"inference endpoint '{inference_id}' available")
    else:
        fallback_enabled = elser_config.get("fallback_enabled", True)
        if fallback_enabled:
            result.add_warning(
                "ELSER",
                "not available (workshop will use fallback methods)"
            )
        else:
            result.add_fail("ELSER", "not available and fallback disabled")


def check_config(result: VerificationResult, config_path: Path, verbose: bool) -> dict:
    """Check configuration file."""
    echo_info("\nChecking configuration...")

    if not config_path.exists():
        result.add_fail("Config file", f"not found at {config_path}")
        return {}

    try:
        config_data = load_config_file(str(config_path))
        result.add_pass("Config file", f"loaded from {config_path}")
        return config_data
    except Exception as e:
        result.add_fail("Config file", f"error loading: {e}")
        return {}


@click.command()
@click.option(
    "--check", "-c",
    type=click.Choice([
        "all", "connection", "indices", "raw-files",
        "processed-files", "elser", "config"
    ]),
    multiple=True,
    default=["all"],
    help="Specific checks to run."
)
@click.option(
    "--fail-on-warning", "-w",
    is_flag=True,
    default=False,
    help="Treat warnings as failures."
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output."
)
@elasticsearch_options
@env_option
def main(
    check: tuple,
    fail_on_warning: bool,
    verbose: bool
):
    """
    Verify the workshop environment is ready.

    Runs a series of checks to ensure:
    - Elasticsearch is accessible
    - Required indices exist and have data
    - Data files are present
    - ELSER is available (optional)

    Examples:

        # Run all checks
        python -m admin.verify_environment

        # Check only Elasticsearch connection
        python -m admin.verify_environment -c connection

        # Multiple specific checks
        python -m admin.verify_environment -c indices -c elser

        # Fail on warnings (useful for CI)
        python -m admin.verify_environment --fail-on-warning
    """
    echo_info("=" * 60)
    echo_info("Review Bomb Workshop - Environment Verification")
    echo_info("=" * 60)

    result = VerificationResult()

    # Determine which checks to run
    checks_to_run = set(check)
    run_all = "all" in checks_to_run

    # Load config first (needed by other checks)
    config_data = {}
    if run_all or "config" in checks_to_run:
        config_data = check_config(result, DEFAULT_CONFIG, verbose)
    else:
        # Still try to load config for other checks
        if DEFAULT_CONFIG.exists():
            try:
                config_data = load_config_file(str(DEFAULT_CONFIG))
            except Exception:
                pass

    # Run requested checks
    es_connected = False

    if run_all or "connection" in checks_to_run:
        es_connected = check_elasticsearch_connection(result, verbose)

    if run_all or "indices" in checks_to_run:
        if es_connected or check_elasticsearch_connection(VerificationResult(), False):
            check_indices(result, config_data, verbose)
        else:
            result.add_fail("Indices check", "skipped (no ES connection)")

    if run_all or "raw-files" in checks_to_run:
        check_raw_files(result, verbose)

    if run_all or "processed-files" in checks_to_run:
        check_processed_files(result, verbose)

    if run_all or "elser" in checks_to_run:
        if es_connected or check_elasticsearch_connection(VerificationResult(), False):
            check_elser(result, config_data, verbose)
        else:
            result.add_warning("ELSER check", "skipped (no ES connection)")

    # Print summary
    echo_info("\n" + "=" * 60)
    echo_info("Summary")
    echo_info("=" * 60)

    echo_info(f"Passed:   {result.passed}")
    if result.warnings > 0:
        echo_warning(f"Warnings: {result.warnings}")
    if result.failed > 0:
        echo_error(f"Failed:   {result.failed}")

    # Determine exit status
    if result.failed > 0:
        echo_error("\nEnvironment verification FAILED")
        sys.exit(1)
    elif result.warnings > 0 and fail_on_warning:
        echo_warning("\nEnvironment verification FAILED (warnings treated as errors)")
        sys.exit(1)
    elif result.warnings > 0:
        echo_warning("\nEnvironment verification PASSED with warnings")
        sys.exit(0)
    else:
        echo_success("\nEnvironment verification PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
