#!/usr/bin/env python3
"""
Review Streamer for Review Bomb Workshop.

Streams reviews to Elasticsearch in three modes:
- replay: Stream legitimate reviews from data files at configured rate
- inject: Inject attack reviews targeting a specific business
- mixed: Run normal traffic, then automatically inject an attack

Usage:
    python streaming/review_streamer.py --mode replay
    python streaming/review_streamer.py --mode inject --business-id <id>
    python streaming/review_streamer.py --mode mixed --business-id <id> --normal-duration 60
"""

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class ReviewStreamer:
    """Streams reviews to Elasticsearch with rate limiting and attack injection."""

    # Attack review templates
    ATTACK_TEMPLATES = [
        "Terrible experience! Would not recommend to anyone.",
        "Worst restaurant I've ever been to. Complete waste of money.",
        "Absolutely horrible service. Never coming back!",
        "Do NOT go here! They don't care about customers at all.",
        "One star is too generous. This place is awful.",
        "Rude staff, terrible quality. Save your money and go elsewhere.",
        "Total disappointment. Nothing like what they advertise.",
        "Waited forever and got terrible service. Avoid at all costs!",
        "This place is a scam. Don't waste your time or money.",
        "The worst experience of my life. Completely unacceptable.",
        "Zero stars if I could. Management doesn't care about quality.",
        "Overpriced garbage. There are much better options nearby.",
        "Stay away! This place will ruin your day.",
        "How is this place still open? Terrible in every way.",
        "Awful, just awful. Don't believe the good reviews.",
        "Rude staff, bad food, dirty restaurant.",
        "Never coming back. Complete waste of money.",
        "Absolutely awful. Food made me sick.",
        "The worst meal I've ever had. Disgusting.",
        "Save your money and go somewhere else.",
        "Horrible service and terrible food. 0 stars if I could.",
        "Do not eat here! You will regret it.",
        "This place is a scam. Stay away!",
    ]

    def __init__(
        self,
        es_client: AsyncElasticsearch,
        config: Dict[str, Any],
        reviews_index: str = "reviews",
        users_index: str = "users",
    ):
        """
        Initialize the review streamer.

        Args:
            es_client: Elasticsearch async client
            config: Configuration dictionary
            reviews_index: Name of the reviews index
            users_index: Name of the users index
        """
        self.es_client = es_client
        self.config = config
        self.reviews_index = reviews_index
        self.users_index = users_index
        self._shutdown = False
        self._created_attacker_ids: set = set()  # Track created attacker users
        self._stats = {
            "reviews_sent": 0,
            "attack_reviews_sent": 0,
            "attacker_users_created": 0,
            "errors": 0,
            "start_time": None,
        }

    def _setup_signal_handlers(self):
        """Set up graceful shutdown signal handlers."""
        def signal_handler(sig, frame):
            logger.info("\nReceived shutdown signal. Finishing current batch...")
            self._shutdown = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _send_bulk(self, reviews: List[Dict[str, Any]], refresh: bool = False) -> int:
        """
        Send reviews via bulk API.

        Args:
            reviews: List of review documents
            refresh: Whether to refresh the index after bulk

        Returns:
            Number of successfully indexed documents
        """
        if not reviews:
            return 0

        operations = []
        for review in reviews:
            review_id = review.get("review_id", str(uuid.uuid4()))
            operations.append({"index": {"_index": self.reviews_index, "_id": review_id}})
            operations.append(review)

        try:
            response = await self.es_client.bulk(
                operations=operations,
                refresh="wait_for" if refresh else False
            )

            if response.get("errors"):
                error_count = sum(
                    1 for item in response.get("items", [])
                    if "error" in item.get("index", {})
                )
                self._stats["errors"] += error_count
                logger.warning(f"Bulk indexing had {error_count} errors")
                return len(reviews) - error_count

            return len(reviews)
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            self._stats["errors"] += len(reviews)
            return 0

    async def _create_attacker_users(self, users: List[Dict[str, Any]]) -> int:
        """
        Create attacker user records in the users index.

        Args:
            users: List of user documents to create

        Returns:
            Number of successfully created users
        """
        if not users:
            return 0

        operations = []
        for user in users:
            user_id = user.get("user_id")
            operations.append({"index": {"_index": self.users_index, "_id": user_id}})
            operations.append(user)

        try:
            response = await self.es_client.bulk(
                operations=operations,
                refresh=False  # Don't wait for refresh on users
            )

            if response.get("errors"):
                error_count = sum(
                    1 for item in response.get("items", [])
                    if "error" in item.get("index", {})
                )
                return len(users) - error_count

            return len(users)
        except Exception as e:
            logger.error(f"Failed to create attacker users: {e}")
            return 0

    def _generate_attacker_user(
        self,
        user_id: str,
        trust_score: float,
        account_age_days: int,
    ) -> Dict[str, Any]:
        """
        Generate an attacker user document.

        Args:
            user_id: The attacker user ID
            trust_score: Trust score (low for attackers)
            account_age_days: Account age in days (usually low)

        Returns:
            Attacker user document
        """
        # Generate a fake name for the attacker
        fake_names = [
            "Alex Smith", "Jordan Lee", "Casey Brown", "Morgan Davis",
            "Taylor Wilson", "Riley Johnson", "Quinn Miller", "Avery Moore",
            "Cameron White", "Dakota Jones", "Skyler Martin", "Finley Clark",
        ]

        return {
            "user_id": user_id,
            "name": random.choice(fake_names),
            "review_count": random.randint(1, 5),
            "yelping_since": (datetime.now(timezone.utc)).isoformat(),
            "useful": 0,
            "funny": 0,
            "cool": 0,
            "fans": 0,
            "average_stars": random.uniform(1.0, 2.5),
            "trust_score": trust_score,
            "account_age_days": account_age_days,
            "flagged": False,
            "synthetic": True,
        }

    def _load_reviews_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Load reviews from an NDJSON file.

        Args:
            file_path: Path to the NDJSON file

        Returns:
            List of review documents
        """
        reviews = []
        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        reviews.append(json.loads(line))
            logger.info(f"Loaded {len(reviews)} reviews from {file_path}")
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {file_path}: {e}")
        return reviews

    def _generate_attack_review(
        self,
        business_id: str,
        attacker_id: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Generate a single attack review and optionally a new attacker user.

        Args:
            business_id: Target business ID
            attacker_id: Optional attacker identifier

        Returns:
            Tuple of (review document, user document or None if user already exists)
        """
        attack_config = self.config.get("attack", {})
        trust_range = attack_config.get("reviewer_trust_range", [0.05, 0.25])
        account_age_range = attack_config.get("reviewer_account_age_range", [1, 14])

        review_id = f"attack_{uuid.uuid4().hex[:12]}"
        user_id = f"attacker_{uuid.uuid4().hex[:8]}"

        # Generate trust score and account age for this attacker
        trust_score = random.uniform(*trust_range)
        account_age_days = random.randint(*account_age_range)

        # Mostly 1-star, occasionally 2-star
        stars = 1 if random.random() > 0.2 else 2

        review = {
            "review_id": review_id,
            "user_id": user_id,
            "business_id": business_id,
            "stars": float(stars),
            "text": random.choice(self.ATTACK_TEMPLATES),
            "date": datetime.now(timezone.utc).isoformat(),
            "useful": 0,
            "funny": 0,
            "cool": 0,
            "is_simulated": True,
            "is_attack": True,
            "attacker_id": attacker_id or f"streamer_{uuid.uuid4().hex[:6]}",
            "partition": "streaming",
            "status": "published",
            # Low trust indicators (stored on review for quick access)
            "reviewer_trust_score": trust_score,
            "reviewer_account_age_days": account_age_days,
        }

        # Create user document if this is a new attacker
        user = None
        if user_id not in self._created_attacker_ids:
            user = self._generate_attacker_user(user_id, trust_score, account_age_days)
            self._created_attacker_ids.add(user_id)

        return review, user

    def _update_review_timestamp(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update review timestamp to current time.

        Args:
            review: Original review document

        Returns:
            Review with updated timestamp
        """
        updated = review.copy()
        updated["date"] = datetime.now(timezone.utc).isoformat()
        updated["partition"] = "streaming"
        # Generate new review_id to avoid conflicts
        updated["review_id"] = f"stream_{uuid.uuid4().hex[:12]}"
        return updated

    async def replay(
        self,
        source_file: Optional[Path] = None,
        reviews_per_second: float = 3.0,
        limit: Optional[int] = None,
    ):
        """
        Replay legitimate reviews from data files.

        Args:
            source_file: Path to NDJSON file (uses config default if None)
            reviews_per_second: Rate of review submission
            limit: Maximum number of reviews to stream (None for unlimited)
        """
        self._setup_signal_handlers()
        self._stats["start_time"] = datetime.now()

        # Determine source file
        if source_file is None:
            streaming_config = self.config.get("streaming", {}).get("replay", {})
            source_path = streaming_config.get("source", "data/sample/reviews.ndjson")
            source_file = PROJECT_ROOT / source_path

        # Load reviews
        reviews = self._load_reviews_from_file(source_file)
        if not reviews:
            logger.error("No reviews to stream")
            return

        # Apply limit
        if limit:
            reviews = reviews[:limit]

        logger.info(f"Starting REPLAY mode: {len(reviews)} reviews at {reviews_per_second}/sec")
        logger.info(f"Target index: {self.reviews_index}")
        logger.info("Press Ctrl+C to stop")
        print("-" * 60)

        delay = 1.0 / reviews_per_second
        batch_size = max(1, int(reviews_per_second))  # Batch for efficiency

        index = 0
        while index < len(reviews) and not self._shutdown:
            batch = []
            for _ in range(batch_size):
                if index >= len(reviews):
                    break
                review = self._update_review_timestamp(reviews[index])
                batch.append(review)
                index += 1

            sent = await self._send_bulk(batch)
            self._stats["reviews_sent"] += sent

            # Log progress
            if sent > 0:
                sample = batch[0]
                logger.info(
                    f"[{self._stats['reviews_sent']:>5}] "
                    f"Sent {sent} reviews | "
                    f"Last: {sample.get('stars', '?')} stars for {sample.get('business_id', '?')[:12]}..."
                )

            # Rate limiting
            await asyncio.sleep(delay * batch_size)

        self._print_summary()

    async def inject(
        self,
        business_id: str,
        count: int = 50,
        reviews_per_second: float = 15.0,
        attacker_id: Optional[str] = None,
    ):
        """
        Inject attack reviews targeting a specific business.

        Args:
            business_id: Target business ID
            count: Number of attack reviews to inject
            reviews_per_second: Rate of attack review submission
            attacker_id: Optional identifier for this attack wave
        """
        self._setup_signal_handlers()
        self._stats["start_time"] = datetime.now()

        logger.info(f"Starting INJECT mode: {count} attack reviews at {reviews_per_second}/sec")
        logger.info(f"Target business: {business_id}")
        logger.info(f"Target index: {self.reviews_index}")
        logger.info("Press Ctrl+C to stop")
        print("-" * 60)

        delay = 1.0 / reviews_per_second
        batch_size = max(1, min(15, int(reviews_per_second)))  # Cap batch size

        sent_count = 0
        while sent_count < count and not self._shutdown:
            reviews_batch = []
            users_batch = []
            remaining = count - sent_count
            batch_count = min(batch_size, remaining)

            for _ in range(batch_count):
                review, user = self._generate_attack_review(business_id, attacker_id)
                reviews_batch.append(review)
                if user:
                    users_batch.append(user)

            # Create attacker users first (if any new ones)
            if users_batch:
                users_created = await self._create_attacker_users(users_batch)
                self._stats["attacker_users_created"] += users_created

            # Send attack reviews
            sent = await self._send_bulk(reviews_batch, refresh=True)
            sent_count += sent
            self._stats["attack_reviews_sent"] += sent
            self._stats["reviews_sent"] += sent

            if sent > 0:
                logger.info(
                    f"[{sent_count:>4}/{count}] "
                    f"ATTACK: Injected {sent} 1-star reviews | "
                    f"Business: {business_id[:20]}..."
                )

            await asyncio.sleep(delay * batch_count)

        print("-" * 60)
        logger.info(f"Attack injection complete: {sent_count} reviews sent to {business_id}")
        logger.info(f"Attacker users created: {self._stats['attacker_users_created']}")
        self._print_summary()

    async def mixed(
        self,
        business_id: str,
        normal_duration: int = 60,
        attack_count: int = 50,
        source_file: Optional[Path] = None,
        normal_rate: float = 3.0,
        attack_rate: float = 15.0,
    ):
        """
        Run mixed mode: normal traffic followed by attack injection.

        Args:
            business_id: Target business for the attack phase
            normal_duration: Seconds of normal traffic before attack
            attack_count: Number of attack reviews to inject
            source_file: Source file for normal reviews
            normal_rate: Reviews per second during normal phase
            attack_rate: Reviews per second during attack phase
        """
        self._setup_signal_handlers()
        self._stats["start_time"] = datetime.now()

        # Determine source file
        if source_file is None:
            streaming_config = self.config.get("streaming", {}).get("replay", {})
            source_path = streaming_config.get("source", "data/sample/reviews.ndjson")
            source_file = PROJECT_ROOT / source_path

        # Load reviews
        reviews = self._load_reviews_from_file(source_file)
        if not reviews:
            logger.error("No reviews to stream")
            return

        logger.info("Starting MIXED mode")
        logger.info(f"  Phase 1: Normal traffic for {normal_duration}s at {normal_rate}/sec")
        logger.info(f"  Phase 2: Attack injection of {attack_count} reviews at {attack_rate}/sec")
        logger.info(f"Target business for attack: {business_id}")
        logger.info("Press Ctrl+C to stop")
        print("-" * 60)

        # Phase 1: Normal traffic
        logger.info("=== PHASE 1: Normal Traffic ===")
        start_time = datetime.now()
        delay = 1.0 / normal_rate
        batch_size = max(1, int(normal_rate))
        index = 0

        while not self._shutdown:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed >= normal_duration:
                break

            batch = []
            for _ in range(batch_size):
                if index >= len(reviews):
                    index = 0  # Loop reviews
                review = self._update_review_timestamp(reviews[index])
                batch.append(review)
                index += 1

            sent = await self._send_bulk(batch)
            self._stats["reviews_sent"] += sent

            remaining = normal_duration - elapsed
            logger.info(
                f"[NORMAL] Sent {sent} reviews | "
                f"Total: {self._stats['reviews_sent']} | "
                f"Time remaining: {remaining:.0f}s"
            )

            await asyncio.sleep(delay * batch_size)

        if self._shutdown:
            self._print_summary()
            return

        # Phase 2: Attack injection
        print("-" * 60)
        logger.info("=== PHASE 2: Attack Injection ===")
        logger.warning(f"Initiating attack on business: {business_id}")

        attack_delay = 1.0 / attack_rate
        attack_batch_size = max(1, min(15, int(attack_rate)))
        attacker_id = f"mixed_attack_{uuid.uuid4().hex[:8]}"

        sent_count = 0
        while sent_count < attack_count and not self._shutdown:
            reviews_batch = []
            users_batch = []
            remaining = attack_count - sent_count
            batch_count = min(attack_batch_size, remaining)

            for _ in range(batch_count):
                review, user = self._generate_attack_review(business_id, attacker_id)
                reviews_batch.append(review)
                if user:
                    users_batch.append(user)

            # Create attacker users first (if any new ones)
            if users_batch:
                users_created = await self._create_attacker_users(users_batch)
                self._stats["attacker_users_created"] += users_created

            # Send attack reviews
            sent = await self._send_bulk(reviews_batch, refresh=True)
            sent_count += sent
            self._stats["attack_reviews_sent"] += sent
            self._stats["reviews_sent"] += sent

            logger.warning(
                f"[ATTACK {sent_count:>3}/{attack_count}] "
                f"Injecting 1-star reviews..."
            )

            await asyncio.sleep(attack_delay * batch_count)

        print("-" * 60)
        logger.info("Mixed mode complete")
        logger.info(f"Attacker users created: {self._stats['attacker_users_created']}")
        self._print_summary()

    def _print_summary(self):
        """Print streaming session summary."""
        duration = (datetime.now() - self._stats["start_time"]).total_seconds()
        rate = self._stats["reviews_sent"] / duration if duration > 0 else 0

        print("\n" + "=" * 60)
        print("SESSION SUMMARY")
        print("=" * 60)
        print(f"  Duration:          {duration:.1f} seconds")
        print(f"  Total reviews:     {self._stats['reviews_sent']}")
        print(f"  Attack reviews:    {self._stats['attack_reviews_sent']}")
        print(f"  Attacker users:    {self._stats['attacker_users_created']}")
        print(f"  Errors:            {self._stats['errors']}")
        print(f"  Average rate:      {rate:.1f} reviews/sec")
        print("=" * 60)


async def create_es_client() -> AsyncElasticsearch:
    """Create Elasticsearch client from environment variables."""
    es_url = os.getenv("ELASTICSEARCH_URL")
    es_api_key = os.getenv("ELASTICSEARCH_API_KEY")
    es_username = os.getenv("ELASTICSEARCH_USERNAME")
    es_password = os.getenv("ELASTICSEARCH_PASSWORD")
    es_cloud_id = os.getenv("ELASTICSEARCH_CLOUD_ID")

    kwargs = {}

    if es_cloud_id:
        kwargs["cloud_id"] = es_cloud_id
    elif es_url:
        kwargs["hosts"] = [es_url]
    else:
        kwargs["hosts"] = ["http://localhost:9200"]

    if es_api_key:
        kwargs["api_key"] = es_api_key
    elif es_username and es_password:
        kwargs["basic_auth"] = (es_username, es_password)

    # Don't verify certs by default for local dev
    kwargs["verify_certs"] = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"

    return AsyncElasticsearch(**kwargs)


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Review Streamer for Review Bomb Workshop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Replay legitimate reviews
  python streaming/review_streamer.py --mode replay

  # Inject attack reviews
  python streaming/review_streamer.py --mode inject --business-id abc123 --count 50

  # Mixed mode: normal traffic then attack
  python streaming/review_streamer.py --mode mixed --business-id abc123 --normal-duration 60
        """
    )

    parser.add_argument(
        "--mode",
        choices=["replay", "inject", "mixed"],
        required=True,
        help="Streaming mode"
    )
    parser.add_argument(
        "--business-id",
        help="Target business ID (required for inject and mixed modes)"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Source NDJSON file for reviews (optional)"
    )
    parser.add_argument(
        "--rate",
        type=float,
        help="Reviews per second (overrides config)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of attack reviews for inject mode (default: 50)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum reviews to stream in replay mode"
    )
    parser.add_argument(
        "--normal-duration",
        type=int,
        default=60,
        help="Seconds of normal traffic in mixed mode (default: 60)"
    )
    parser.add_argument(
        "--index",
        default="reviews",
        help="Elasticsearch index name (default: reviews)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.mode in ["inject", "mixed"] and not args.business_id:
        parser.error(f"--business-id is required for {args.mode} mode")

    # Load configuration
    config = load_config()
    streaming_config = config.get("streaming", {})

    # Create ES client
    logger.info("Connecting to Elasticsearch...")
    es_client = await create_es_client()

    try:
        # Test connection
        info = await es_client.info()
        logger.info(f"Connected to Elasticsearch {info['version']['number']}")
    except Exception as e:
        logger.error(f"Failed to connect to Elasticsearch: {e}")
        logger.error("Check ELASTICSEARCH_URL and ELASTICSEARCH_API_KEY environment variables")
        await es_client.close()
        sys.exit(1)

    # Create streamer
    streamer = ReviewStreamer(
        es_client=es_client,
        config=config,
        reviews_index=args.index,
    )

    try:
        if args.mode == "replay":
            rate = args.rate or streaming_config.get("replay", {}).get("reviews_per_second", 3.0)
            await streamer.replay(
                source_file=args.source,
                reviews_per_second=rate,
                limit=args.limit,
            )

        elif args.mode == "inject":
            rate = args.rate or streaming_config.get("inject", {}).get("reviews_per_second", 15.0)
            await streamer.inject(
                business_id=args.business_id,
                count=args.count,
                reviews_per_second=rate,
            )

        elif args.mode == "mixed":
            normal_rate = args.rate or streaming_config.get("replay", {}).get("reviews_per_second", 3.0)
            attack_rate = streaming_config.get("inject", {}).get("reviews_per_second", 15.0)
            await streamer.mixed(
                business_id=args.business_id,
                normal_duration=args.normal_duration,
                attack_count=args.count,
                source_file=args.source,
                normal_rate=normal_rate,
                attack_rate=attack_rate,
            )

    finally:
        await es_client.close()
        logger.info("Elasticsearch connection closed")


if __name__ == "__main__":
    asyncio.run(main())
