"""Business models for Review Fraud Workshop."""

from datetime import datetime
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class BusinessLocation(BaseModel):
    """Business location information."""

    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class BusinessHours(BaseModel):
    """Business operating hours."""

    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None


class Business(BaseModel):
    """Business model representing a Yelp business."""

    business_id: str = Field(..., description="Unique business identifier")
    name: str = Field(..., description="Business name")
    # Categories can be a string (comma-separated) or list
    categories: Optional[Union[str, List[str]]] = Field(default=None, description="Business categories")

    @field_validator("categories", mode="before")
    @classmethod
    def convert_categories(cls, v):
        """Convert categories list to comma-separated string."""
        if isinstance(v, list):
            return ", ".join(v)
        return v
    # Flat location fields (matching our data format)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Hours as dict (matching our data format)
    hours: Optional[Dict] = None
    stars: Optional[float] = Field(default=None, description="Average star rating")
    review_count: Optional[int] = Field(default=0, ge=0, description="Total review count")
    is_open: Optional[bool] = Field(default=True, description="Whether business is currently open")
    attributes: Optional[Dict] = Field(default=None, description="Business attributes")
    # Protection fields
    current_rating: Optional[float] = None
    rating_protected: Optional[bool] = Field(default=False)
    protection_reason: Optional[str] = None
    protected_since: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "business_id": "abc123",
                "name": "Joe's Coffee Shop",
                "categories": ["Coffee & Tea", "Breakfast & Brunch"],
                "stars": 4.5,
                "review_count": 150,
                "is_open": True
            }
        }


class BusinessStats(BaseModel):
    """Statistics for a business, used in review fraud detection."""

    business_id: str
    name: str
    total_reviews: int = 0
    average_rating: float = 0.0
    recent_review_count: int = Field(default=0, description="Reviews in last 24 hours")
    recent_average_rating: float = Field(default=0.0, description="Average rating in last 24 hours")
    rating_trend: float = Field(default=0.0, description="Rating change trend")
    review_velocity: float = Field(default=0.0, description="Reviews per hour")
    suspicious_review_count: int = Field(default=0, description="Count of potentially suspicious reviews")
    is_under_attack: bool = Field(default=False, description="Whether business appears to be under review fraud attack")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "business_id": "abc123",
                "name": "Joe's Coffee Shop",
                "total_reviews": 150,
                "average_rating": 4.5,
                "recent_review_count": 25,
                "recent_average_rating": 1.8,
                "rating_trend": -2.7,
                "review_velocity": 5.2,
                "suspicious_review_count": 20,
                "is_under_attack": True
            }
        }


class BusinessSearchResult(BaseModel):
    """Search result for businesses."""

    businesses: List[Business]
    total: int
    page: int = 1
    page_size: int = 10
