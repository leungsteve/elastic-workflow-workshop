"""User models for Negative Review Campaign Detection Workshop."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """User model representing a Yelp user."""

    user_id: str = Field(..., description="Unique user identifier")
    name: str = Field(..., description="User display name")
    review_count: int = Field(default=0, ge=0, description="Total reviews by user")
    yelping_since: Optional[datetime] = Field(default=None, description="Account creation date")
    friends: Optional[List[str]] = Field(default=None, description="Friend user IDs")
    useful: int = Field(default=0, ge=0, description="Useful votes received")
    funny: int = Field(default=0, ge=0, description="Funny votes received")
    cool: int = Field(default=0, ge=0, description="Cool votes received")
    fans: int = Field(default=0, ge=0, description="Number of fans")
    average_stars: Optional[float] = Field(default=None, ge=1.0, le=5.0, description="Average star rating given")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user456",
                "name": "John D.",
                "review_count": 42,
                "yelping_since": "2020-03-15T00:00:00Z",
                "useful": 100,
                "funny": 25,
                "cool": 50,
                "fans": 10,
                "average_stars": 3.8
            }
        }


class AttackerProfile(BaseModel):
    """Profile for a simulated attacker in negative review campaign scenarios."""

    attacker_id: str = Field(..., description="Unique attacker identifier")
    name: str = Field(..., description="Generated fake name")
    user_id: str = Field(..., description="Associated fake user ID")

    # Attack characteristics
    attack_style: str = Field(default="aggressive", description="Style of attack reviews")
    typical_rating: float = Field(default=1.0, ge=1.0, le=5.0, description="Typical rating given")
    review_templates: List[str] = Field(default_factory=list, description="Review text templates")

    # Activity tracking
    reviews_posted: int = Field(default=0, ge=0, description="Number of attack reviews posted")
    targets: List[str] = Field(default_factory=list, description="Business IDs targeted")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)

    # Behavioral patterns
    posting_frequency: float = Field(default=1.0, description="Reviews per minute during attack")
    uses_similar_text: bool = Field(default=True, description="Whether attacker reuses similar text")
    account_age_days: int = Field(default=1, description="Simulated account age in days")

    class Config:
        json_schema_extra = {
            "example": {
                "attacker_id": "attacker_001",
                "name": "FakeReviewer123",
                "user_id": "fake_user_001",
                "attack_style": "aggressive",
                "typical_rating": 1.0,
                "reviews_posted": 15,
                "targets": ["abc123", "def456"],
                "posting_frequency": 2.5,
                "uses_similar_text": True,
                "account_age_days": 3
            }
        }


class AttackerGroup(BaseModel):
    """Group of coordinated attackers."""

    group_id: str = Field(..., description="Unique group identifier")
    name: str = Field(default="Anonymous Group", description="Group name")
    attackers: List[AttackerProfile] = Field(default_factory=list)
    target_business_id: str = Field(..., description="Primary target business")
    coordination_score: float = Field(default=0.0, description="How coordinated the attack is")
    created_at: datetime = Field(default_factory=datetime.utcnow)
