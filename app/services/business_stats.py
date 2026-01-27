"""Business stats update service for Review Campaign Detection Workshop."""

from elasticsearch import AsyncElasticsearch

from app.config import Settings


async def update_business_stats(
    es: AsyncElasticsearch,
    settings: Settings,
    business_id: str
) -> dict:
    """
    Recalculate and update business stats (stars and review_count) from reviews.

    This function queries all reviews for the business, calculates the average
    star rating and total review count, then updates the business document.

    Args:
        es: Elasticsearch async client
        settings: Application settings
        business_id: The business ID to update

    Returns:
        Dictionary with updated stats or error information
    """
    try:
        # Query reviews to get aggregate stats
        response = await es.search(
            index=settings.reviews_index,
            query={"term": {"business_id": business_id}},
            aggs={
                "avg_stars": {"avg": {"field": "stars"}},
                "review_count": {"value_count": {"field": "review_id"}}
            },
            size=0
        )

        aggs = response.get("aggregations", {})
        avg_stars = aggs.get("avg_stars", {}).get("value")
        review_count = int(aggs.get("review_count", {}).get("value", 0))

        # Handle case where there are no reviews
        if avg_stars is None:
            avg_stars = 0.0

        # Round stars to 1 decimal place (like Yelp)
        avg_stars = round(avg_stars, 1)

        # Update the business document
        # Use update with doc to partially update only these fields
        await es.update(
            index=settings.businesses_index,
            id=business_id,
            doc={
                "stars": avg_stars,
                "review_count": review_count
            },
            refresh=True
        )

        return {
            "success": True,
            "business_id": business_id,
            "stars": avg_stars,
            "review_count": review_count
        }

    except Exception as e:
        # Log the error but don't raise - this is a background task
        # In production, you'd want proper logging here
        return {
            "success": False,
            "business_id": business_id,
            "error": str(e)
        }


async def update_business_stats_for_multiple(
    es: AsyncElasticsearch,
    settings: Settings,
    business_ids: list[str]
) -> list[dict]:
    """
    Update stats for multiple businesses.

    Useful after bulk operations that affect multiple businesses.

    Args:
        es: Elasticsearch async client
        settings: Application settings
        business_ids: List of business IDs to update

    Returns:
        List of update results for each business
    """
    results = []
    # Deduplicate business IDs
    unique_ids = list(set(business_ids))

    for business_id in unique_ids:
        result = await update_business_stats(es, settings, business_id)
        results.append(result)

    return results
