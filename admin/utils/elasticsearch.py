"""
Elasticsearch client utilities for the Review Bomb Workshop.

Provides sync and async Elasticsearch clients with support for both
API key and username/password authentication.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from elasticsearch import Elasticsearch, AsyncElasticsearch
from elasticsearch.exceptions import ConnectionError, AuthenticationException


# Load environment variables from .env file
load_dotenv()


def _get_auth_config() -> dict:
    """
    Build authentication configuration from environment variables.

    Supports two authentication methods:
    1. API Key: Set ELASTICSEARCH_API_KEY
    2. Basic Auth: Set ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD

    Returns:
        dict: Authentication configuration for Elasticsearch client
    """
    config = {}

    # Get Elasticsearch URL
    es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    config["hosts"] = [es_url]

    # Check for API key authentication first
    api_key = os.getenv("ELASTICSEARCH_API_KEY")
    if api_key:
        config["api_key"] = api_key
        return config

    # Fall back to username/password authentication
    username = os.getenv("ELASTICSEARCH_USERNAME")
    password = os.getenv("ELASTICSEARCH_PASSWORD")

    if username and password:
        config["basic_auth"] = (username, password)

    # Optional: Disable SSL verification for development
    if os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "false":
        config["verify_certs"] = False
        config["ssl_show_warn"] = False

    # Optional: CA certificate path
    ca_certs = os.getenv("ELASTICSEARCH_CA_CERTS")
    if ca_certs:
        config["ca_certs"] = ca_certs

    return config


def get_es_client() -> Elasticsearch:
    """
    Get a synchronous Elasticsearch client.

    Reads configuration from environment variables:
    - ELASTICSEARCH_URL: Elasticsearch endpoint (default: http://localhost:9200)
    - ELASTICSEARCH_API_KEY: API key for authentication
    - ELASTICSEARCH_USERNAME: Username for basic auth
    - ELASTICSEARCH_PASSWORD: Password for basic auth
    - ELASTICSEARCH_VERIFY_CERTS: Whether to verify SSL certs (default: true)
    - ELASTICSEARCH_CA_CERTS: Path to CA certificate file

    Returns:
        Elasticsearch: Configured Elasticsearch client

    Example:
        >>> es = get_es_client()
        >>> es.info()
    """
    config = _get_auth_config()
    return Elasticsearch(**config)


def get_async_es_client() -> AsyncElasticsearch:
    """
    Get an asynchronous Elasticsearch client for use with FastAPI.

    Reads configuration from environment variables (same as get_es_client).

    Returns:
        AsyncElasticsearch: Configured async Elasticsearch client

    Example:
        >>> async def search():
        ...     es = get_async_es_client()
        ...     try:
        ...         result = await es.search(index="reviews", query={"match_all": {}})
        ...     finally:
        ...         await es.close()
    """
    config = _get_auth_config()
    return AsyncElasticsearch(**config)


def test_connection(verbose: bool = True) -> bool:
    """
    Test the Elasticsearch connection and optionally print cluster info.

    Args:
        verbose: If True, print connection details and cluster info

    Returns:
        bool: True if connection successful, False otherwise

    Example:
        >>> if test_connection():
        ...     print("Connected!")
    """
    try:
        es = get_es_client()
        info = es.info()

        if verbose:
            print("Successfully connected to Elasticsearch!")
            print(f"  Cluster name: {info['cluster_name']}")
            print(f"  Version: {info['version']['number']}")
            print(f"  Cluster UUID: {info['cluster_uuid']}")

            # Get cluster health
            health = es.cluster.health()
            print(f"  Cluster status: {health['status']}")
            print(f"  Number of nodes: {health['number_of_nodes']}")
            print(f"  Active shards: {health['active_shards']}")

        return True

    except ConnectionError as e:
        if verbose:
            print(f"Failed to connect to Elasticsearch: {e}")
            print("\nPlease check:")
            print("  1. Elasticsearch is running")
            print("  2. ELASTICSEARCH_URL is correct")
            print("  3. Network connectivity")
        return False

    except AuthenticationException as e:
        if verbose:
            print(f"Authentication failed: {e}")
            print("\nPlease check:")
            print("  1. ELASTICSEARCH_API_KEY is valid, or")
            print("  2. ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD are correct")
        return False

    except Exception as e:
        if verbose:
            print(f"Unexpected error connecting to Elasticsearch: {e}")
        return False


def check_elser_available(inference_id: str = ".elser-2-elasticsearch") -> bool:
    """
    Check if the ELSER inference endpoint is available.

    ELSER (Elastic Learned Sparse EncodeR) is used for semantic search.
    This function checks if the inference endpoint is configured and ready.

    Args:
        inference_id: The inference endpoint ID to check
                     (default: .elser-2-elasticsearch)

    Returns:
        bool: True if ELSER endpoint exists and is ready, False otherwise

    Example:
        >>> if check_elser_available():
        ...     print("ELSER is ready for semantic search!")
    """
    try:
        es = get_es_client()

        # Try to get the inference endpoint
        response = es.inference.get(inference_id=inference_id)

        if response and "endpoints" in response:
            endpoints = response["endpoints"]
            if endpoints:
                endpoint = endpoints[0]
                print(f"ELSER inference endpoint found: {inference_id}")
                print(f"  Task type: {endpoint.get('task_type', 'unknown')}")
                print(f"  Service: {endpoint.get('service', 'unknown')}")
                return True

        print(f"ELSER endpoint '{inference_id}' not found or not configured.")
        return False

    except Exception as e:
        error_str = str(e)

        # Check for specific "not found" error
        if "resource_not_found_exception" in error_str.lower() or "404" in error_str:
            print(f"ELSER inference endpoint '{inference_id}' does not exist.")
            print("\nTo create the ELSER endpoint, run:")
            print(f"""
PUT _inference/sparse_embedding/{inference_id}
{{
  "service": "elser",
  "service_settings": {{
    "num_allocations": 1,
    "num_threads": 1
  }}
}}
""")
        else:
            print(f"Error checking ELSER availability: {e}")

        return False


def get_index_info(index_name: str) -> Optional[dict]:
    """
    Get information about an Elasticsearch index.

    Args:
        index_name: Name of the index to check

    Returns:
        dict: Index information including mappings and settings,
              or None if index doesn't exist
    """
    try:
        es = get_es_client()

        if not es.indices.exists(index=index_name):
            return None

        # Get index info
        info = es.indices.get(index=index_name)

        # Get document count
        count = es.count(index=index_name)

        return {
            "name": index_name,
            "mappings": info[index_name].get("mappings", {}),
            "settings": info[index_name].get("settings", {}),
            "doc_count": count["count"]
        }

    except Exception as e:
        print(f"Error getting index info: {e}")
        return None
