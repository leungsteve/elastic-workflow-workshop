#!/usr/bin/env python3
"""
Setup target business for Challenge 4 end-to-end scenario.

This script creates "The Golden Spoon" restaurant as the attack target.
In Instruqt, this runs automatically via setup.sh. For local testing,
run this script manually.

Usage:
    python admin/setup_target_business.py

Environment variables required:
    ELASTICSEARCH_URL - Elasticsearch endpoint URL
    ELASTICSEARCH_API_KEY - API key for authentication
"""

import json
import os
import sys
import urllib.request
import urllib.error

TARGET_BUSINESS = {
    "business_id": "target_biz_001",
    "name": "The Golden Spoon",
    "address": "123 Main Street",
    "city": "Philadelphia",
    "state": "PA",
    "postal_code": "19103",
    "latitude": 39.9526,
    "longitude": -75.1652,
    "stars": 4.7,
    "review_count": 5000,  # High count so it appears first in dropdown
    "is_open": True,
    "categories": "Restaurants, American (Traditional), Breakfast & Brunch",
    "rating_protected": False,
    "attributes": {
        "RestaurantsPriceRange2": "2",
        "WiFi": "free",
        "OutdoorSeating": "True",
        "RestaurantsDelivery": "True",
        "RestaurantsTakeOut": "True",
        "GoodForKids": "True"
    },
    "hours": {
        "Monday": "7:0-22:0",
        "Tuesday": "7:0-22:0",
        "Wednesday": "7:0-22:0",
        "Thursday": "7:0-22:0",
        "Friday": "7:0-23:0",
        "Saturday": "8:0-23:0",
        "Sunday": "8:0-21:0"
    }
}


def get_es_url():
    """Get Elasticsearch URL from environment."""
    es_url = os.environ.get("ELASTICSEARCH_URL")
    if not es_url:
        print("ERROR: ELASTICSEARCH_URL environment variable not set")
        sys.exit(1)
    return es_url.rstrip("/")


def get_api_key():
    """Get API key from environment."""
    api_key = os.environ.get("ELASTICSEARCH_API_KEY")
    if not api_key:
        print("ERROR: ELASTICSEARCH_API_KEY environment variable not set")
        sys.exit(1)
    return api_key


def make_request(method, url, data=None, api_key=None):
    """Make HTTP request to Elasticsearch."""
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"

    body = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        try:
            error_json = json.loads(error_body)
            return e.code, error_json
        except json.JSONDecodeError:
            return e.code, {"error": error_body}
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}


def main():
    print("=" * 60)
    print("Setting up Target Business for Challenge 4")
    print("=" * 60)

    es_url = get_es_url()
    api_key = get_api_key()

    print(f"\nElasticsearch URL: {es_url}")
    print(f"Target Business: {TARGET_BUSINESS['name']} ({TARGET_BUSINESS['business_id']})")
    print()

    # Check if business already exists
    check_url = f"{es_url}/businesses/_doc/{TARGET_BUSINESS['business_id']}"
    status, response = make_request("GET", check_url, api_key=api_key)

    if status == 200 and response.get("found"):
        print(f"✓ Target business already exists")
        existing = response.get("_source", {})
        print(f"  Name: {existing.get('name')}")
        print(f"  Stars: {existing.get('stars')}")
        print(f"  City: {existing.get('city')}")
        return 0

    # Create the business
    print("Creating target business...")
    create_url = f"{es_url}/businesses/_doc/{TARGET_BUSINESS['business_id']}?refresh=true"
    status, response = make_request("PUT", create_url, TARGET_BUSINESS, api_key)

    if status in [200, 201]:
        print(f"✓ Created target business: {TARGET_BUSINESS['name']}")
        print(f"  ID: {TARGET_BUSINESS['business_id']}")
        print(f"  Stars: {TARGET_BUSINESS['stars']}")
        print(f"  City: {TARGET_BUSINESS['city']}")
        print(f"  Categories: {TARGET_BUSINESS['categories']}")
    else:
        print(f"✗ Failed to create business: {status} - {response}")
        return 1

    print()
    print("=" * 60)
    print("SUCCESS: Target business ready for attack simulation")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Verify in Kibana with:")
    print('   FROM businesses | WHERE business_id == "target_biz_001"')
    print()
    print("2. Continue with Challenge 4 Task 1")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
