"""Reviews API router for Review Fraud Workshop."""

from datetime import datetime
from typing import List, Optional
import uuid

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_es_client, get_app_settings
from app.config import Settings
from app.models.review import Review, ReviewCreate, ReviewResponse, ReviewBatch, ReviewGenerateRequest
from app.services.review_generator import ReviewGenerator

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/generate")
async def generate_review_text():
    """
    Generate random attack review text.

    This is a simple endpoint used by the attack simulation UI
    to get sample negative review text.
    """
    generator = ReviewGenerator()
    text = generator._generate_review_text("random")
    return {"text": text}


@router.post("/bulk-attack")
async def bulk_attack(
    business_id: str,
    count: int = 15,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
):
    """
    Submit multiple attack reviews at once (server-side).

    This allows the attack to complete even if user navigates away.
    """
    from datetime import datetime
    import uuid
    import random

    attack_templates = [
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
    ]

    # Build bulk operations for reviews AND users
    operations = []
    reviews_created = []
    users_created = set()

    for i in range(count):
        review_id = f"attack_{uuid.uuid4().hex[:12]}"
        user_id = f"attacker_{uuid.uuid4().hex[:8]}"
        text = random.choice(attack_templates)
        stars = 1 if random.random() > 0.3 else 2

        # Create attacker user with low trust score
        if user_id not in users_created:
            user_doc = {
                "user_id": user_id,
                "name": f"Attacker {user_id[-6:]}",
                "review_count": random.randint(1, 5),
                "trust_score": round(random.uniform(0.05, 0.25), 2),  # Low trust score
                "account_age_days": random.randint(1, 14),  # New account
                "yelping_since": datetime.utcnow().isoformat() + "Z",
                "friends": 0,
                "fans": 0,
                "elite": [],
                "average_stars": float(stars),
                "is_attacker": True
            }
            operations.append({"index": {"_index": settings.users_index, "_id": user_id}})
            operations.append(user_doc)
            users_created.add(user_id)

        review_doc = {
            "review_id": review_id,
            "business_id": business_id,
            "user_id": user_id,
            "stars": float(stars),
            "text": text,
            "date": datetime.utcnow().isoformat() + "Z",
            "useful": 0,
            "funny": 0,
            "cool": 0,
            "is_simulated": True,
            "attacker_id": f"turbo_{uuid.uuid4().hex[:6]}"
        }

        operations.append({"index": {"_index": settings.reviews_index, "_id": review_id}})
        operations.append(review_doc)
        reviews_created.append({"review_id": review_id, "stars": stars, "text": text[:50]})

    # Bulk index both users and reviews
    if operations:
        await es.bulk(operations=operations, refresh=True)

    return {
        "success": True,
        "count": count,
        "reviews": reviews_created,
        "message": f"Successfully created {count} attack reviews"
    }


@router.get("", response_model=ReviewBatch)
async def list_reviews(
    business_id: Optional[str] = Query(None, description="Filter by business ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    min_stars: Optional[float] = Query(None, ge=1.0, le=5.0, description="Minimum star rating"),
    max_stars: Optional[float] = Query(None, ge=1.0, le=5.0, description="Maximum star rating"),
    is_simulated: Optional[bool] = Query(None, description="Filter by simulated status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> ReviewBatch:
    """
    List reviews with optional filtering.

    - **business_id**: Filter reviews for a specific business
    - **user_id**: Filter reviews by a specific user
    - **min_stars**: Minimum star rating filter
    - **max_stars**: Maximum star rating filter
    - **is_simulated**: Filter simulated (attack) reviews
    """
    must_clauses = []

    if business_id:
        must_clauses.append({"term": {"business_id": business_id}})

    if user_id:
        must_clauses.append({"term": {"user_id": user_id}})

    if min_stars is not None or max_stars is not None:
        range_clause = {"range": {"stars": {}}}
        if min_stars is not None:
            range_clause["range"]["stars"]["gte"] = min_stars
        if max_stars is not None:
            range_clause["range"]["stars"]["lte"] = max_stars
        must_clauses.append(range_clause)

    if is_simulated is not None:
        must_clauses.append({"term": {"is_simulated": is_simulated}})

    query = {"match_all": {}} if not must_clauses else {"bool": {"must": must_clauses}}

    from_offset = (page - 1) * page_size

    try:
        response = await es.search(
            index=settings.reviews_index,
            query=query,
            from_=from_offset,
            size=page_size,
            sort=[{"date": "desc"}]
        )

        reviews = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            source["review_id"] = source.get("review_id", hit["_id"])
            reviews.append(Review(**source))

        total = response["hits"]["total"]["value"]

        return ReviewBatch(
            reviews=reviews,
            total=total,
            business_id=business_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reviews: {str(e)}")


@router.post("", response_model=ReviewResponse)
async def create_review(
    review_data: ReviewCreate,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> ReviewResponse:
    """
    Create a new review.

    This endpoint can be used to:
    - Create legitimate reviews
    - Create simulated attack reviews for testing
    """
    try:
        # Generate IDs if not provided
        review_id = f"rev_{uuid.uuid4().hex[:12]}"
        user_id = review_data.user_id or f"user_{uuid.uuid4().hex[:8]}"

        # Create review document
        review = Review(
            review_id=review_id,
            business_id=review_data.business_id,
            user_id=user_id,
            stars=review_data.stars,
            text=review_data.text,
            date=datetime.utcnow(),
            useful=0,
            funny=0,
            cool=0,
            is_simulated=review_data.is_simulated,
            attacker_id=review_data.attacker_id
        )

        # Index the review
        await es.index(
            index=settings.reviews_index,
            id=review_id,
            document=review.model_dump(mode="json")
        )

        return ReviewResponse(
            success=True,
            review=review,
            message="Review created successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating review: {str(e)}")


@router.post("/generate", response_model=ReviewBatch)
async def generate_reviews(
    request: ReviewGenerateRequest,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> ReviewBatch:
    """
    Generate simulated attack reviews for a business.

    This endpoint is used for workshop demonstrations to simulate
    review fraud attacks.

    - **business_id**: Target business for the attack
    - **count**: Number of reviews to generate (1-100)
    - **min_stars**: Minimum star rating for generated reviews
    - **max_stars**: Maximum star rating for generated reviews
    - **attack_type**: Type of attack pattern (random, coordinated, burst)
    """
    try:
        generator = ReviewGenerator()
        reviews = await generator.generate_attack_reviews(
            business_id=request.business_id,
            count=request.count,
            min_stars=request.min_stars,
            max_stars=request.max_stars,
            attack_type=request.attack_type
        )

        # Bulk index the reviews
        operations = []
        for review in reviews:
            operations.append({"index": {"_index": settings.reviews_index, "_id": review.review_id}})
            operations.append(review.model_dump(mode="json"))

        if operations:
            await es.bulk(operations=operations)

        return ReviewBatch(
            reviews=reviews,
            total=len(reviews),
            business_id=request.business_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating reviews: {str(e)}")


@router.get("/{review_id}", response_model=Review)
async def get_review(
    review_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> Review:
    """
    Get a specific review by ID.
    """
    try:
        try:
            response = await es.get(index=settings.reviews_index, id=review_id)
            source = response["_source"]
            source["review_id"] = source.get("review_id", review_id)
            return Review(**source)
        except:
            pass

        # Fall back to search
        response = await es.search(
            index=settings.reviews_index,
            query={"term": {"review_id": review_id}},
            size=1
        )

        if not response["hits"]["hits"]:
            raise HTTPException(status_code=404, detail=f"Review {review_id} not found")

        source = response["hits"]["hits"][0]["_source"]
        source["review_id"] = source.get("review_id", review_id)
        return Review(**source)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching review: {str(e)}")


@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """
    Delete a review by ID.
    """
    try:
        await es.delete(index=settings.reviews_index, id=review_id)
        return {"success": True, "message": f"Review {review_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting review: {str(e)}")
