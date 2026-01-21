"""Review generator service for simulating review bomb attacks."""

import random
import uuid
from datetime import datetime, timedelta
from typing import List

from app.models.review import Review
from app.services.attacker_generator import AttackerGenerator


class ReviewGenerator:
    """Generator for simulated attack reviews."""

    # Negative review templates
    NEGATIVE_TEMPLATES = [
        "Terrible experience! Would not recommend to anyone.",
        "Worst {business_type} I've ever been to. Complete waste of money.",
        "Absolutely horrible service. Never coming back!",
        "Do NOT go here! They don't care about customers at all.",
        "One star is too generous. This place is awful.",
        "Rude staff, terrible quality. Save your money and go elsewhere.",
        "I can't believe this place is still in business. Horrible!",
        "Total disappointment. Nothing like what they advertise.",
        "Waited forever and got terrible service. Avoid at all costs!",
        "This place is a scam. Don't waste your time or money.",
        "Disgusting! I will be reporting them to the health department.",
        "The worst experience of my life. Completely unacceptable.",
        "Zero stars if I could. Management doesn't care about quality.",
        "Overpriced garbage. There are much better options nearby.",
        "I've had better experiences at a DMV. Pathetic service.",
        "Stay away! This place will ruin your day.",
        "Unprofessional and incompetent staff. Very disappointing.",
        "How is this place still open? Terrible in every way.",
        "Not worth a single penny. Complete rip-off!",
        "Awful, just awful. Don't believe the good reviews.",
    ]

    # Slightly varied negative phrases to mix in
    NEGATIVE_PHRASES = [
        "Never again!",
        "What a joke!",
        "Unbelievable!",
        "Total disaster!",
        "Complete failure!",
        "Absolutely terrible!",
        "So disappointed!",
        "Worst ever!",
        "Horrible experience!",
        "Stay away!",
    ]

    # Business type words for template variation
    BUSINESS_TYPES = [
        "place", "restaurant", "shop", "store", "business",
        "establishment", "location", "spot", "venue", "joint"
    ]

    def __init__(self):
        self.attacker_generator = AttackerGenerator()

    def _generate_review_text(self, attack_type: str = "random") -> str:
        """
        Generate attack review text based on attack type.

        Args:
            attack_type: Type of attack pattern
                - "random": Random negative reviews
                - "coordinated": Similar text patterns
                - "burst": Very short, repetitive reviews

        Returns:
            Generated review text
        """
        if attack_type == "burst":
            # Short, repetitive reviews
            return random.choice(self.NEGATIVE_PHRASES)

        elif attack_type == "coordinated":
            # Similar patterns with slight variations
            base_template = random.choice(self.NEGATIVE_TEMPLATES[:5])
            business_type = random.choice(self.BUSINESS_TYPES)
            text = base_template.replace("{business_type}", business_type)

            # Maybe add a phrase
            if random.random() > 0.5:
                text += " " + random.choice(self.NEGATIVE_PHRASES)

            return text

        else:  # random
            # Mix of templates and variations
            template = random.choice(self.NEGATIVE_TEMPLATES)
            business_type = random.choice(self.BUSINESS_TYPES)
            text = template.replace("{business_type}", business_type)

            # Add variation
            if random.random() > 0.7:
                text += " " + random.choice(self.NEGATIVE_PHRASES)

            return text

    async def generate_attack_reviews(
        self,
        business_id: str,
        count: int = 10,
        min_stars: float = 1.0,
        max_stars: float = 2.0,
        attack_type: str = "random"
    ) -> List[Review]:
        """
        Generate a batch of simulated attack reviews.

        Args:
            business_id: Target business ID
            count: Number of reviews to generate
            min_stars: Minimum star rating
            max_stars: Maximum star rating
            attack_type: Type of attack pattern

        Returns:
            List of generated Review objects
        """
        reviews = []

        # Generate attacker profiles for this batch
        attacker_count = max(1, count // 3)  # Roughly 3 reviews per attacker
        attackers = self.attacker_generator.generate_attacker_batch(attacker_count)

        # Time spread - reviews over the last few minutes
        base_time = datetime.utcnow()
        time_spread_seconds = min(count * 10, 300)  # Up to 5 minutes spread

        for i in range(count):
            # Select an attacker
            attacker = random.choice(attackers)

            # Generate star rating
            stars = round(random.uniform(min_stars, max_stars), 1)
            stars = max(1.0, min(5.0, stars))  # Clamp to valid range

            # Generate review text
            text = self._generate_review_text(attack_type)

            # Generate timestamp (slight spread over time)
            time_offset = random.randint(0, time_spread_seconds)
            review_time = base_time - timedelta(seconds=time_offset)

            # Create review
            review = Review(
                review_id=f"attack_{uuid.uuid4().hex[:12]}",
                business_id=business_id,
                user_id=attacker.user_id,
                stars=stars,
                text=text,
                date=review_time,
                useful=0,
                funny=0,
                cool=0,
                is_simulated=True,
                attacker_id=attacker.attacker_id
            )

            reviews.append(review)

            # Update attacker stats
            attacker.reviews_posted += 1
            if business_id not in attacker.targets:
                attacker.targets.append(business_id)

        return reviews

    def generate_single_review(
        self,
        business_id: str,
        stars: float = 1.0,
        attack_type: str = "random"
    ) -> Review:
        """
        Generate a single attack review synchronously.

        Args:
            business_id: Target business ID
            stars: Star rating
            attack_type: Type of attack pattern

        Returns:
            Generated Review object
        """
        attacker = self.attacker_generator.generate_attacker()
        text = self._generate_review_text(attack_type)

        return Review(
            review_id=f"attack_{uuid.uuid4().hex[:12]}",
            business_id=business_id,
            user_id=attacker.user_id,
            stars=stars,
            text=text,
            date=datetime.utcnow(),
            useful=0,
            funny=0,
            cool=0,
            is_simulated=True,
            attacker_id=attacker.attacker_id
        )
