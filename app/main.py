"""FastAPI application entry point for Review Fraud Workshop."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.dependencies import init_es_client, close_es_client, get_es_client
from app.routers import (
    businesses_router,
    reviews_router,
    incidents_router,
    notifications_router,
    streaming_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown events."""
    # Startup
    print("Starting Review Fraud Workshop...")
    try:
        await init_es_client()
        print("Elasticsearch client initialized")
    except Exception as e:
        print(f"Warning: Could not connect to Elasticsearch: {e}")

    yield

    # Shutdown
    print("Shutting down Review Fraud Workshop...")
    await close_es_client()
    print("Elasticsearch client closed")


# Create FastAPI application
app = FastAPI(
    title="Review Fraud Workshop",
    description="A workshop application for detecting and analyzing review fraud attacks using Elasticsearch",
    version="1.0.0",
    lifespan=lifespan,
)

# Get paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ensure directories exist
TEMPLATES_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include routers
app.include_router(businesses_router)
app.include_router(reviews_router)
app.include_router(incidents_router)
app.include_router(notifications_router)
app.include_router(streaming_router)


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns the status of the application and its dependencies.
    """
    settings = get_settings()
    es_status = "disconnected"

    try:
        async for es in get_es_client():
            info = await es.info()
            es_status = "connected"
            break
    except Exception as e:
        es_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "elasticsearch": es_status,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Serve the main UI dashboard.
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "dashboard",
        }
    )


@app.get("/businesses", response_class=HTMLResponse)
async def businesses_page(request: Request):
    """
    Serve the businesses page.
    """
    return templates.TemplateResponse(
        "businesses.html",
        {
            "request": request,
            "active_page": "businesses",
        }
    )


@app.get("/incidents", response_class=HTMLResponse)
async def incidents_page(request: Request):
    """
    Serve the incidents page.
    """
    return templates.TemplateResponse(
        "incidents.html",
        {
            "request": request,
            "active_page": "incidents",
        }
    )


@app.get("/attack", response_class=HTMLResponse)
async def attack_page(request: Request):
    """
    Serve the attack simulation page.
    """
    return templates.TemplateResponse(
        "attack.html",
        {
            "request": request,
            "active_page": "attack",
        }
    )


@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """
    Serve the notifications page.
    """
    return templates.TemplateResponse(
        "notifications.html",
        {
            "request": request,
            "active_page": "notifications",
        }
    )


# ============================================================
# FreshEats Consumer UI (Yelp-like interface)
# ============================================================

@app.get("/fresheats", response_class=HTMLResponse)
async def fresheats_home(
    request: Request,
    q: str = None,
    category: str = None,
    city: str = None,
    page: int = 1,
):
    """
    Serve the FreshEats home/search page (Yelp-like interface).
    """
    from app.dependencies import get_es_client, get_app_settings

    businesses = []
    total = 0
    page_size = 10

    # Only search if there's a query or filter
    if q or category or city:
        try:
            settings = get_app_settings()
            async for es in get_es_client():
                # Build query
                must_clauses = []

                if q:
                    must_clauses.append({
                        "multi_match": {
                            "query": q,
                            "fields": ["name^3", "categories^2", "city"],
                            "fuzziness": "AUTO"
                        }
                    })

                if category:
                    must_clauses.append({
                        "match": {"categories": category}
                    })

                if city:
                    must_clauses.append({
                        "match": {"city": city}
                    })

                query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}
                from_offset = (page - 1) * page_size

                response = await es.search(
                    index=settings.businesses_index,
                    query=query,
                    from_=from_offset,
                    size=page_size,
                    sort=[{"review_count": "desc"}]
                )

                for hit in response["hits"]["hits"]:
                    source = hit["_source"]
                    source["business_id"] = source.get("business_id", hit["_id"])
                    businesses.append(source)

                total = response["hits"]["total"]["value"]
                break
        except Exception as e:
            print(f"Search error: {e}")

    return templates.TemplateResponse(
        "fresheats/home.html",
        {
            "request": request,
            "query": q,
            "category": category,
            "city": city,
            "businesses": businesses,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@app.get("/fresheats/biz/{business_id}", response_class=HTMLResponse)
async def fresheats_business(
    request: Request,
    business_id: str,
    filter: str = None,
):
    """
    Serve the FreshEats business detail page with reviews.
    """
    from app.dependencies import get_es_client, get_app_settings

    business = None
    reviews = []
    incident = None
    has_more_reviews = False

    try:
        settings = get_app_settings()
        async for es in get_es_client():
            # Get business
            try:
                biz_response = await es.get(index=settings.businesses_index, id=business_id)
                business = biz_response["_source"]
                business["business_id"] = business.get("business_id", business_id)
            except:
                # Try searching by business_id field
                biz_search = await es.search(
                    index=settings.businesses_index,
                    query={"term": {"business_id": business_id}},
                    size=1
                )
                if biz_search["hits"]["hits"]:
                    business = biz_search["hits"]["hits"][0]["_source"]
                    business["business_id"] = business.get("business_id", business_id)

            if not business:
                return templates.TemplateResponse(
                    "fresheats/home.html",
                    {"request": request, "error": f"Business {business_id} not found"},
                    status_code=404
                )

            # Get reviews
            review_query = {"term": {"business_id": business_id}}

            # Apply filters
            if filter == "recent":
                review_query = {
                    "bool": {
                        "must": [
                            {"term": {"business_id": business_id}},
                            {"range": {"date": {"gte": "now-24h"}}}
                        ]
                    }
                }
            elif filter == "held":
                review_query = {
                    "bool": {
                        "must": [
                            {"term": {"business_id": business_id}},
                            {"term": {"status": "held"}}
                        ]
                    }
                }
            elif filter == "suspicious":
                review_query = {
                    "bool": {
                        "must": [
                            {"term": {"business_id": business_id}},
                            {"term": {"is_simulated": True}}
                        ]
                    }
                }

            review_response = await es.search(
                index=settings.reviews_index,
                query=review_query,
                size=20,
                sort=[{"date": "desc"}]
            )

            # Collect reviews and user_ids
            raw_reviews = []
            user_ids = set()
            for hit in review_response["hits"]["hits"]:
                review = hit["_source"]
                review["review_id"] = review.get("review_id", hit["_id"])
                raw_reviews.append(review)
                if review.get("user_id"):
                    user_ids.add(review["user_id"])

            # Fetch user data for all reviewers
            users_map = {}
            if user_ids:
                try:
                    users_response = await es.search(
                        index=settings.users_index,
                        query={"terms": {"user_id": list(user_ids)}},
                        size=len(user_ids)
                    )
                    for hit in users_response["hits"]["hits"]:
                        user = hit["_source"]
                        uid = user.get("user_id", hit["_id"])
                        users_map[uid] = user
                except Exception as e:
                    print(f"Error fetching users: {e}")

            # Enrich reviews with user data
            for review in raw_reviews:
                user_id = review.get("user_id")
                if user_id and user_id in users_map:
                    user = users_map[user_id]
                    review["user_name"] = user.get("name", user_id[:12])
                    review["trust_score"] = user.get("trust_score")
                    review["account_age_days"] = user.get("account_age_days")
                else:
                    review["user_name"] = user_id[:12] if user_id else "Anonymous"
                reviews.append(review)

            total_reviews = review_response["hits"]["total"]["value"]
            has_more_reviews = total_reviews > 20

            # Check for active incident
            try:
                incident_response = await es.search(
                    index=settings.incidents_index,
                    query={
                        "bool": {
                            "must": [
                                {"term": {"business_id": business_id}},
                                {"term": {"status": "detected"}}
                            ]
                        }
                    },
                    size=1,
                    sort=[{"detected_at": "desc"}]
                )
                if incident_response["hits"]["hits"]:
                    incident = incident_response["hits"]["hits"][0]["_source"]
            except:
                pass  # Incidents index might not exist yet

            break
    except Exception as e:
        print(f"Business page error: {e}")
        return templates.TemplateResponse(
            "fresheats/home.html",
            {"request": request, "error": str(e)},
            status_code=500
        )

    return templates.TemplateResponse(
        "fresheats/business.html",
        {
            "request": request,
            "business": business,
            "reviews": reviews,
            "incident": incident,
            "has_more_reviews": has_more_reviews,
            "filter": filter,
        }
    )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
