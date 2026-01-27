"""Elasticsearch service helpers for Review Campaign Detection Workshop."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from elasticsearch import AsyncElasticsearch


class ElasticsearchService:
    """Helper service for common Elasticsearch operations."""

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def search_with_aggregations(
        self,
        index: str,
        query: Dict[str, Any],
        aggregations: Dict[str, Any],
        size: int = 0
    ) -> Dict[str, Any]:
        """
        Execute a search with aggregations.

        Args:
            index: Index name to search
            query: Elasticsearch query DSL
            aggregations: Aggregation definitions
            size: Number of hits to return (0 for aggs only)

        Returns:
            Search response with aggregations
        """
        response = await self.client.search(
            index=index,
            query=query,
            aggs=aggregations,
            size=size
        )
        return response

    async def get_review_velocity(
        self,
        index: str,
        business_id: str,
        hours: int = 24,
        interval: str = "1h"
    ) -> List[Dict[str, Any]]:
        """
        Get review velocity over time for a business.

        Args:
            index: Reviews index name
            business_id: Business ID to analyze
            hours: Number of hours to look back
            interval: Histogram interval

        Returns:
            List of time buckets with review counts
        """
        response = await self.client.search(
            index=index,
            query={
                "bool": {
                    "must": [
                        {"term": {"business_id": business_id}},
                        {"range": {"date": {"gte": f"now-{hours}h"}}}
                    ]
                }
            },
            aggs={
                "reviews_over_time": {
                    "date_histogram": {
                        "field": "date",
                        "fixed_interval": interval
                    },
                    "aggs": {
                        "avg_rating": {"avg": {"field": "stars"}}
                    }
                }
            },
            size=0
        )

        buckets = response.get("aggregations", {}).get("reviews_over_time", {}).get("buckets", [])
        return buckets

    async def get_suspicious_patterns(
        self,
        index: str,
        business_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze review patterns for suspicious activity.

        Args:
            index: Reviews index name
            business_id: Business ID to analyze
            hours: Number of hours to look back

        Returns:
            Analysis of suspicious patterns
        """
        response = await self.client.search(
            index=index,
            query={
                "bool": {
                    "must": [
                        {"term": {"business_id": business_id}},
                        {"range": {"date": {"gte": f"now-{hours}h"}}}
                    ]
                }
            },
            aggs={
                "unique_users": {"cardinality": {"field": "user_id"}},
                "avg_rating": {"avg": {"field": "stars"}},
                "rating_distribution": {
                    "terms": {"field": "stars"}
                },
                "simulated_reviews": {
                    "filter": {"term": {"is_simulated": True}}
                },
                "new_accounts": {
                    "filter": {
                        "range": {"yelping_since": {"gte": f"now-7d"}}
                    }
                }
            },
            size=0
        )

        aggs = response.get("aggregations", {})
        total_reviews = response["hits"]["total"]["value"]

        return {
            "total_reviews": total_reviews,
            "unique_users": aggs.get("unique_users", {}).get("value", 0),
            "average_rating": aggs.get("avg_rating", {}).get("value", 0),
            "rating_distribution": {
                bucket["key"]: bucket["doc_count"]
                for bucket in aggs.get("rating_distribution", {}).get("buckets", [])
            },
            "simulated_count": aggs.get("simulated_reviews", {}).get("doc_count", 0),
            "new_account_count": aggs.get("new_accounts", {}).get("doc_count", 0)
        }

    async def bulk_index(
        self,
        index: str,
        documents: List[Dict[str, Any]],
        id_field: str = "id"
    ) -> Dict[str, Any]:
        """
        Bulk index documents.

        Args:
            index: Target index name
            documents: List of documents to index
            id_field: Field name to use as document ID

        Returns:
            Bulk response
        """
        operations = []
        for doc in documents:
            doc_id = doc.get(id_field)
            operations.append({"index": {"_index": index, "_id": doc_id}})
            operations.append(doc)

        if not operations:
            return {"items": [], "errors": False}

        return await self.client.bulk(operations=operations)

    async def create_index_if_not_exists(
        self,
        index: str,
        mappings: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create an index if it doesn't exist.

        Args:
            index: Index name to create
            mappings: Index mappings
            settings: Index settings

        Returns:
            True if index was created, False if it already existed
        """
        exists = await self.client.indices.exists(index=index)

        if not exists:
            body = {}
            if mappings:
                body["mappings"] = mappings
            if settings:
                body["settings"] = settings

            await self.client.indices.create(index=index, body=body)
            return True

        return False

    async def get_index_stats(self, index: str) -> Dict[str, Any]:
        """
        Get statistics for an index.

        Args:
            index: Index name

        Returns:
            Index statistics
        """
        try:
            stats = await self.client.indices.stats(index=index)
            return stats["indices"].get(index, {})
        except Exception:
            return {}
