"""Attacker profile generator for simulating review bomb attacks."""

import random
import uuid
from datetime import datetime, timedelta
from typing import List

from app.models.user import AttackerProfile


class AttackerGenerator:
    """Generator for fake attacker profiles."""

    # Name components for generating fake names
    FIRST_NAMES = [
        "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery",
        "Blake", "Cameron", "Dakota", "Emery", "Finley", "Harper", "Jamie", "Kelly",
        "Logan", "Madison", "Parker", "Reagan", "Sage", "Sydney", "Tyler", "Whitney",
        "Anonymous", "User", "Customer", "Reviewer", "Guest", "Member"
    ]

    LAST_INITIALS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M",
                    "N", "P", "R", "S", "T", "W", "X", "Y", "Z"]

    # Username patterns
    USERNAME_PATTERNS = [
        "{name}{number}",
        "{name}_{number}",
        "{name}{year}",
        "real_{name}",
        "{name}_reviews",
        "honest_{name}",
        "{name}_consumer",
        "the_real_{name}",
        "{name}{random}",
    ]

    # Attack styles
    ATTACK_STYLES = [
        "aggressive",      # Very negative, uses caps and exclamation
        "disappointed",    # Sad tone, "expected better"
        "angry",          # Hostile, threatening to report
        "sarcastic",      # Mocking tone
        "brief",          # Short, curt reviews
    ]

    def __init__(self):
        self._generated_count = 0

    def _generate_username(self, first_name: str) -> str:
        """Generate a fake username."""
        pattern = random.choice(self.USERNAME_PATTERNS)
        name = first_name.lower()

        return pattern.format(
            name=name,
            number=random.randint(1, 9999),
            year=random.randint(1980, 2005),
            random=uuid.uuid4().hex[:4]
        )

    def generate_attacker(self) -> AttackerProfile:
        """
        Generate a single fake attacker profile.

        Returns:
            Generated AttackerProfile
        """
        self._generated_count += 1

        # Generate name
        first_name = random.choice(self.FIRST_NAMES)
        last_initial = random.choice(self.LAST_INITIALS)
        display_name = f"{first_name} {last_initial}."

        # Generate IDs
        attacker_id = f"attacker_{uuid.uuid4().hex[:8]}"
        user_id = f"fake_user_{uuid.uuid4().hex[:10]}"

        # Generate username for name field
        username = self._generate_username(first_name)

        # Random attack characteristics
        attack_style = random.choice(self.ATTACK_STYLES)
        typical_rating = random.uniform(1.0, 2.0)

        # Account age (new accounts are suspicious)
        account_age = random.choices(
            [1, 2, 3, 7, 14, 30, 90],
            weights=[30, 20, 15, 15, 10, 5, 5]  # Heavily weighted toward new accounts
        )[0]

        # Posting frequency
        posting_frequency = random.uniform(0.5, 5.0)  # Reviews per minute

        # Text similarity (coordinated attacks use similar text)
        uses_similar_text = random.random() > 0.4  # 60% chance

        return AttackerProfile(
            attacker_id=attacker_id,
            name=username,
            user_id=user_id,
            attack_style=attack_style,
            typical_rating=round(typical_rating, 1),
            review_templates=[],
            reviews_posted=0,
            targets=[],
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow(),
            posting_frequency=round(posting_frequency, 2),
            uses_similar_text=uses_similar_text,
            account_age_days=account_age
        )

    def generate_attacker_batch(self, count: int = 10) -> List[AttackerProfile]:
        """
        Generate a batch of attacker profiles.

        For coordinated attacks, some attackers may share characteristics.

        Args:
            count: Number of attackers to generate

        Returns:
            List of AttackerProfile objects
        """
        attackers = []

        # Determine if this is a coordinated group
        is_coordinated = random.random() > 0.5

        if is_coordinated:
            # Coordinated group - share some characteristics
            group_style = random.choice(self.ATTACK_STYLES)
            group_rating = random.uniform(1.0, 1.5)

            for _ in range(count):
                attacker = self.generate_attacker()

                # Override with group characteristics
                if random.random() > 0.3:  # 70% follow group pattern
                    attacker.attack_style = group_style
                    attacker.typical_rating = round(group_rating + random.uniform(-0.2, 0.2), 1)
                    attacker.uses_similar_text = True

                attackers.append(attacker)
        else:
            # Random individual attackers
            for _ in range(count):
                attackers.append(self.generate_attacker())

        return attackers

    def generate_attacker_with_history(
        self,
        previous_targets: List[str],
        reviews_posted: int = 0
    ) -> AttackerProfile:
        """
        Generate an attacker with existing attack history.

        Useful for simulating repeat offenders.

        Args:
            previous_targets: List of previously targeted business IDs
            reviews_posted: Number of reviews already posted

        Returns:
            AttackerProfile with history
        """
        attacker = self.generate_attacker()
        attacker.targets = previous_targets.copy()
        attacker.reviews_posted = reviews_posted
        attacker.last_active = datetime.utcnow() - timedelta(
            hours=random.randint(1, 48)
        )

        return attacker

    @property
    def total_generated(self) -> int:
        """Get total number of attackers generated."""
        return self._generated_count
