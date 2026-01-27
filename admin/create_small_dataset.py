#!/usr/bin/env python3
"""
Create a small subset of the processed dataset for faster workshop setup.

Selects N businesses (fewest reviews + must-include challenge businesses),
then filters reviews and users to match. This dramatically reduces ELSER
inference time during data ingestion.
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

# Allow running as script or module
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from admin.utils.cli import (
    common_options,
    echo_success,
    echo_error,
    echo_info,
    echo_verbose,
)


# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "small"

# Challenge-required businesses
DEFAULT_MUST_INCLUDE = [
    "ytynqOUb3hjKeJfRj5Tshw",  # Reading Terminal Market
    "ctHjyadbDQAtUFfkcAFEHw",  # Zahav
]


def count_lines(file_path: Path) -> int:
    """Count lines in a file efficiently."""
    count = 0
    with open(file_path, "rb") as f:
        for _ in f:
            count += 1
    return count


def select_businesses(
    businesses_path: Path,
    count: int,
    must_include: list[str],
    verbose: bool,
) -> list[dict]:
    """
    Select businesses: must-includes + fewest-review businesses to fill count.

    Returns the selected business dicts sorted by review_count ascending.
    """
    all_businesses = []
    with open(businesses_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                biz = json.loads(line)
                all_businesses.append(biz)
            except json.JSONDecodeError:
                continue

    must_include_set = set(must_include)

    # Separate must-includes from the rest
    must_have = [b for b in all_businesses if b["business_id"] in must_include_set]
    rest = [b for b in all_businesses if b["business_id"] not in must_include_set]

    # Sort rest by review_count ascending, take enough to fill count
    rest.sort(key=lambda b: b.get("review_count", 0))
    slots = count - len(must_have)
    if slots < 0:
        slots = 0
    selected_rest = rest[:slots]

    selected = must_have + selected_rest
    selected.sort(key=lambda b: b.get("review_count", 0))

    # Report must-include status
    found_ids = {b["business_id"] for b in must_have}
    for bid in must_include:
        if bid in found_ids:
            name = next(b["name"] for b in must_have if b["business_id"] == bid)
            echo_verbose(f"Must-include found: {name} ({bid})", verbose)
        else:
            echo_error(f"Must-include business NOT found: {bid}")

    return selected


def cap_reviews(
    reviews: list[dict],
    max_reviews: int,
    verbose: bool,
) -> list[dict]:
    """
    Proportionally sample reviews per business to stay within max_reviews.

    Each business gets a share proportional to its original review count,
    with a minimum of 1 review per business.
    """
    if len(reviews) <= max_reviews:
        return reviews

    # Group by business
    by_biz: dict[str, list[dict]] = defaultdict(list)
    for r in reviews:
        by_biz[r["business_id"]].append(r)

    n_biz = len(by_biz)
    total = len(reviews)
    ratio = max_reviews / total

    # Allocate proportionally, minimum 1 per business
    allocations: dict[str, int] = {}
    for bid, revs in by_biz.items():
        allocations[bid] = max(1, int(len(revs) * ratio))

    # Adjust to hit the target exactly
    allocated = sum(allocations.values())
    diff = max_reviews - allocated
    # Sort businesses by allocation size (descending) for adjustment
    sorted_bids = sorted(allocations, key=lambda b: allocations[b], reverse=True)
    i = 0
    while diff != 0:
        bid = sorted_bids[i % n_biz]
        if diff > 0:
            allocations[bid] += 1
            diff -= 1
        elif diff < 0 and allocations[bid] > 1:
            allocations[bid] -= 1
            diff += 1
        i += 1
        if i > n_biz * 2 and diff < 0:
            break  # can't reduce further without going below 1

    # Sample within each business
    rng = random.Random(42)  # deterministic
    sampled: list[dict] = []
    for bid, revs in by_biz.items():
        n = min(allocations[bid], len(revs))
        sampled.extend(rng.sample(revs, n))

    echo_verbose(
        f"Capped reviews: {total:,} → {len(sampled):,} (target {max_reviews:,})",
        verbose,
    )
    return sampled


@click.command()
@click.option(
    "--input-dir", "-i",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_INPUT_DIR,
    help="Directory with processed NDJSON files.",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help="Directory to write small dataset files.",
)
@click.option(
    "--count", "-n",
    type=int,
    default=20,
    show_default=True,
    help="Number of businesses to include.",
)
@click.option(
    "--must-include", "-m",
    multiple=True,
    default=DEFAULT_MUST_INCLUDE,
    help="Business ID that must be included (repeatable).",
)
@click.option(
    "--max-reviews",
    type=int,
    default=None,
    help="Cap total reviews (proportionally sampled per business).",
)
@common_options
def main(
    input_dir: Path,
    output_dir: Path,
    count: int,
    must_include: tuple,
    max_reviews: int | None,
    dry_run: bool,
    verbose: bool,
    config: str,
):
    """
    Create a small dataset subset for faster workshop ingestion.

    Picks the N businesses with the fewest reviews (plus any must-include
    challenge businesses), then keeps only matching reviews and users.

    Examples:

        # Create default 20-business dataset
        python -m admin.create_small_dataset

        # Custom size with review cap
        python -m admin.create_small_dataset --count 30 --max-reviews 5000

        # Preview without writing
        python -m admin.create_small_dataset --dry-run --verbose
    """
    businesses_path = input_dir / "businesses.ndjson"
    reviews_path = input_dir / "reviews.ndjson"
    users_path = input_dir / "users.ndjson"

    # Validate inputs
    for p in [businesses_path, reviews_path, users_path]:
        if not p.exists():
            echo_error(f"Input file not found: {p}")
            raise SystemExit(1)

    echo_info(f"Input directory:  {input_dir}")
    echo_info(f"Output directory: {output_dir}")
    echo_info(f"Business count:   {count}")
    echo_info(f"Max reviews:      {max_reviews or 'unlimited'}")
    echo_info(f"Must-include IDs: {len(must_include)}")

    # ── Step 1: Select businesses ──────────────────────────────────────
    echo_info("\nStep 1: Selecting businesses...")
    selected = select_businesses(businesses_path, count, list(must_include), verbose)
    selected_biz_ids = {b["business_id"] for b in selected}
    echo_info(f"  Selected {len(selected)} businesses")

    if verbose:
        echo_info("  Review counts:")
        for b in selected:
            echo_verbose(
                f"    {b['name'][:40]:<40s}  reviews={b.get('review_count', '?')}",
                verbose,
            )

    # ── Step 2: Filter reviews ─────────────────────────────────────────
    echo_info("\nStep 2: Filtering reviews...")
    total_reviews = count_lines(reviews_path)
    kept_reviews = []

    with open(reviews_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rev.get("business_id") in selected_biz_ids:
                kept_reviews.append(rev)

    echo_info(f"  Kept {len(kept_reviews):,} of {total_reviews:,} reviews")

    # ── Step 2b: Cap reviews if needed ─────────────────────────────────
    if max_reviews and len(kept_reviews) > max_reviews:
        echo_info(f"\nStep 2b: Capping reviews to {max_reviews:,}...")
        kept_reviews = cap_reviews(kept_reviews, max_reviews, verbose)
        echo_info(f"  Reviews after cap: {len(kept_reviews):,}")

    # Collect user IDs from (possibly capped) reviews
    user_ids_seen: set[str] = set()
    for rev in kept_reviews:
        uid = rev.get("user_id")
        if uid:
            user_ids_seen.add(uid)
    echo_info(f"  Unique user IDs referenced: {len(user_ids_seen):,}")

    # ── Step 3: Filter users ───────────────────────────────────────────
    echo_info("\nStep 3: Filtering users...")
    total_users = count_lines(users_path)
    kept_users = []

    with open(users_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                user = json.loads(line)
            except json.JSONDecodeError:
                continue
            if user.get("user_id") in user_ids_seen:
                kept_users.append(user)

    echo_info(f"  Kept {len(kept_users):,} of {total_users:,} users")

    # ── Orphan check ───────────────────────────────────────────────────
    echo_info("\nOrphan check:")
    user_ids_in_file = {u["user_id"] for u in kept_users}
    orphan_reviews_no_user = sum(
        1 for r in kept_reviews if r.get("user_id") not in user_ids_in_file
    )
    orphan_reviews_no_biz = sum(
        1 for r in kept_reviews if r.get("business_id") not in selected_biz_ids
    )
    echo_info(f"  Reviews missing user:     {orphan_reviews_no_user}")
    echo_info(f"  Reviews missing business: {orphan_reviews_no_biz}")

    if orphan_reviews_no_user or orphan_reviews_no_biz:
        echo_error("Orphans detected — dataset may have integrity issues")
    else:
        echo_success("Zero orphans — dataset is consistent")

    # ── Write output ───────────────────────────────────────────────────
    if dry_run:
        echo_info("\n[DRY RUN] No files written.")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_biz = output_dir / "businesses.ndjson"
        out_rev = output_dir / "reviews.ndjson"
        out_usr = output_dir / "users.ndjson"

        with open(out_biz, "w") as f:
            for b in selected:
                f.write(json.dumps(b) + "\n")

        with open(out_rev, "w") as f:
            for r in kept_reviews:
                f.write(json.dumps(r) + "\n")

        with open(out_usr, "w") as f:
            for u in kept_users:
                f.write(json.dumps(u) + "\n")

        echo_success(f"Written to {output_dir}/")
        echo_info(f"  businesses.ndjson  {len(selected):>8,} records")
        echo_info(f"  reviews.ndjson     {len(kept_reviews):>8,} records")
        echo_info(f"  users.ndjson       {len(kept_users):>8,} records")

    # ── Summary ────────────────────────────────────────────────────────
    echo_info("\nSummary:")
    echo_info(f"  Businesses: {len(selected):,}")
    echo_info(f"  Reviews:    {len(kept_reviews):,}")
    echo_info(f"  Users:      {len(kept_users):,}")


if __name__ == "__main__":
    main()
