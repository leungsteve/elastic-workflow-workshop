"""Dependency injection for Review Campaign Detection Workshop."""

from typing import AsyncGenerator, Optional

from elasticsearch import AsyncElasticsearch

from app.config import Settings, get_settings

# Global ES client instance
_es_client: Optional[AsyncElasticsearch] = None


async def init_es_client() -> AsyncElasticsearch:
    """Initialize the Elasticsearch async client."""
    global _es_client

    if _es_client is not None:
        return _es_client

    settings = get_settings()

    # Build connection kwargs
    kwargs = {}

    if settings.es_cloud_id:
        # Cloud connection
        kwargs["cloud_id"] = settings.es_cloud_id
    elif settings.elasticsearch_url:
        # Full URL provided (e.g., from ELASTICSEARCH_URL env var)
        kwargs["hosts"] = [settings.elasticsearch_url]
    else:
        # Build from parts
        kwargs["hosts"] = [settings.es_url]

    # Authentication
    if settings.es_api_key:
        kwargs["api_key"] = settings.es_api_key
    elif settings.es_username and settings.es_password:
        kwargs["basic_auth"] = (settings.es_username, settings.es_password)

    # SSL verification
    kwargs["verify_certs"] = settings.es_verify_certs

    _es_client = AsyncElasticsearch(**kwargs)

    return _es_client


async def close_es_client() -> None:
    """Close the Elasticsearch client connection."""
    global _es_client

    if _es_client is not None:
        await _es_client.close()
        _es_client = None


async def get_es_client() -> AsyncGenerator[AsyncElasticsearch, None]:
    """Dependency to get the ES client."""
    global _es_client

    if _es_client is None:
        await init_es_client()

    yield _es_client


def get_app_settings() -> Settings:
    """Dependency to get application settings."""
    return get_settings()
