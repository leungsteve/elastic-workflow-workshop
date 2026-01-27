"""Review models for Review Campaign Detection Workshop."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Review(BaseModel):
    """Review model representing a Yelp review."""

    review_id: str = Field(..., description="Unique review identifier")
    business_id: str = Field(..., description="Business being reviewed")
    user_id: str = Field(..., description="User who wrote the review")
    stars: float = Field(..., ge=1.0, le=5.0, description="Star rating")
    text: str = Field(..., description="Review text content")
    date: datetime = Field(..., description="Review date")
    useful: int = Field(default=0, ge=0, description="Useful votes")
    funny: int = Field(default=0, ge=0, description="Funny votes")
    cool: int = Field(default=0, ge=0, description="Cool votes")

    # Fields for attack detection
    is_simulated: bool = Field(default=False, description="Whether this is a simulated review")
    attacker_id: Optional[str] = Field(default=None, description="Attacker profile ID if simulated")
    sentiment_score: Optional[float] = Field(default=None, description="Computed sentiment score")

    class Config:
        json_schema_extra = {
            "example": {
                "review_id": "rev123",
                "business_id": "abc123",
                "user_id": "user456",
                "stars": 1.0,
                "text": "Terrible experience! Would not recommend.",
                "date": "2024-01-15T10:30:00Z",
                "useful": 0,
                "funny": 0,
                "cool": 0,
                "is_simulated": True,
                "attacker_id": "attacker_001"
            }
        }


class ReviewCreate(BaseModel):
    """Model for creating a new review."""

    business_id: str = Field(..., description="Business to review")
    user_id: Optional[str] = Field(default=None, description="User ID (auto-generated if not provided)")
    stars: float = Field(..., ge=1.0, le=5.0, description="Star rating")
    text: str = Field(..., min_length=1, description="Review text")
    is_simulated: bool = Field(default=False, description="Whether this is a simulated attack review")
    attacker_id: Optional[str] = Field(default=None, description="Attacker profile ID")

    class Config:
        json_schema_extra = {
            "example": {
                "business_id": "abc123",
                "stars": 1.0,
                "text": "Worst place ever!",
                "is_simulated": True
            }
        }


class ReviewResponse(BaseModel):
    """Response model for review operations."""

    success: bool
    review: Optional[Review] = None
    message: str = ""

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "review": {
                    "review_id": "rev123",
                    "business_id": "abc123",
                    "stars": 1.0
                },
                "message": "Review created successfully"
            }
        }


class ReviewBatch(BaseModel):
    """Batch of reviews for bulk operations."""

    reviews: list[Review]
    total: int
    business_id: Optional[str] = None


class ReviewGenerateRequest(BaseModel):
    """Request model for generating simulated reviews."""

    business_id: str = Field(..., description="Target business ID")
    count: int = Field(default=10, ge=1, le=100, description="Number of reviews to generate")
    min_stars: float = Field(default=1.0, ge=1.0, le=5.0, description="Minimum star rating")
    max_stars: float = Field(default=2.0, ge=1.0, le=5.0, description="Maximum star rating")
    attack_type: str = Field(default="random", description="Type of attack pattern")

    class Config:
        json_schema_extra = {
            "example": {
                "business_id": "abc123",
                "count": 20,
                "min_stars": 1.0,
                "max_stars": 1.5,
                "attack_type": "coordinated"
            }
        }
