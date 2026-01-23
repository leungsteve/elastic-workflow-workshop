#!/usr/bin/env python3
"""
Setup Agent Builder tools and agent for the Review Fraud Workshop.

This script creates:
- 3 investigation tools (incident_summary, reviewer_analysis, similar_reviews)
- 1 custom agent (Review Fraud Investigator) with all tools assigned

Usage:
    python admin/setup_agent_builder.py

Environment variables required:
    KIBANA_URL - Kibana endpoint URL
    ELASTICSEARCH_API_KEY - API key for authentication

Optional:
    --delete    Delete existing tools and agent before creating
    --dry-run   Show what would be created without making API calls
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

# Tool definitions
TOOLS = [
    {
        "id": "incident_summary",
        "type": "esql",
        "description": "Retrieves a summary of a review fraud incident including the targeted business, attack severity, and current status. Use this tool when asked about incident details, incident status, or what happened to a specific business.",
        "configuration": {
            "query": """FROM incidents
| WHERE incident_id == "{{incident_id}}" OR business_name LIKE "*{{incident_id}}*"
| SORT detected_at DESC
| LIMIT 1
| LOOKUP JOIN businesses ON business_id
| EVAL
    impact_assessment = CASE(
      severity == "critical", "SEVERE - Business reputation at immediate risk. Urgent action required.",
      severity == "high", "SIGNIFICANT - Notable impact on business rating. Prompt investigation needed.",
      TRUE, "MODERATE - Limited impact so far. Standard investigation protocol."
    ),
    time_since_detection = DATE_DIFF("minute", detected_at, NOW()),
    business_original_rating = stars
| KEEP incident_id, incident_type, status, severity, business_name, city,
       review_count, avg_rating, avg_trust_score,
       unique_reviewers, detected_at, time_since_detection,
       impact_assessment, business_original_rating""",
            "params": {
                "incident_id": {
                    "type": "text",
                    "description": "The incident ID to look up (e.g., INC-biz123-2024). Can also accept a business name to find the latest incident."
                }
            }
        }
    },
    {
        "id": "reviewer_analysis",
        "type": "esql",
        "description": "Analyzes the reviewers/attackers involved in a review fraud incident. Shows their trust scores, account ages, review patterns, and risk levels. Use this to understand who is behind an attack and identify coordination patterns.",
        "configuration": {
            "query": """FROM reviews
| WHERE business_id == "{{business_id}}"
| WHERE date > NOW() - 24 hours
| WHERE stars <= 2
| LOOKUP JOIN users ON user_id
| WHERE trust_score < 0.5
| STATS
    reviews_submitted = COUNT(*),
    avg_rating_given = AVG(stars),
    first_review = MIN(date),
    last_review = MAX(date)
  BY user_id, trust_score, account_age_days
| EVAL
    risk_level = CASE(
      trust_score < 0.2 AND account_age_days < 7, "CRITICAL",
      trust_score < 0.3 AND account_age_days < 14, "HIGH",
      trust_score < 0.4 AND account_age_days < 30, "MEDIUM",
      TRUE, "LOW"
    ),
    account_type = CASE(
      account_age_days < 7, "Brand New",
      account_age_days < 30, "New",
      account_age_days < 90, "Recent",
      TRUE, "Established"
    )
| SORT trust_score ASC, reviews_submitted DESC
| LIMIT 20""",
            "params": {
                "business_id": {
                    "type": "text",
                    "description": "The business ID that was attacked. Can be found in incident details."
                }
            }
        }
    },
    {
        "id": "similar_reviews",
        "type": "esql",
        "description": "Finds reviews that are semantically similar to a given text using ELSER. Use this to understand attack narratives, find common themes in malicious reviews, or discover patterns in what attackers are claiming. Works by meaning, not just keywords - 'food poisoning' will find reviews about illness even if they don't use those exact words.",
        "configuration": {
            "query": """FROM reviews METADATA _score
| WHERE text_semantic: "{{search_text}}"
| SORT _score DESC
| KEEP review_id, user_id, business_id, stars, text, date, _score
| LIMIT 10""",
            "params": {
                "search_text": {
                    "type": "text",
                    "description": "The text to search for semantically similar reviews. Describe the content you're looking for."
                }
            }
        }
    }
]

# Agent definition
# Note: 'type' field is auto-assigned by the API, do not include it in the request
AGENT = {
    "id": "review_fraud_investigator",
    "name": "Review Fraud Investigator",
    "description": "Investigates review fraud attacks on businesses. Can summarize incidents, analyze attacker patterns, and find similar malicious reviews.",
    "configuration": {
        "instructions": """You are a Trust & Safety analyst investigating review fraud attacks on the FreshEats platform.

When investigating incidents:
1. Start by getting the incident summary to understand the scope
2. Analyze the attackers to identify patterns and risk levels
3. Use semantic search to understand what narratives attackers are using

Always provide actionable insights:
- Highlight the most suspicious accounts (lowest trust scores, newest accounts)
- Note any coordination patterns (similar timing, similar text)
- Recommend next steps for the investigation

Be concise but thorough. Format your responses with clear sections when presenting multiple pieces of information.""",
        "tools": [{"tool_ids": ["incident_summary", "reviewer_analysis", "similar_reviews"]}]
    },
    "avatar_color": "#BD271E",  # Red for security/trust
    "avatar_symbol": "shield"
}


def get_kibana_url():
    """Get Kibana URL from environment or derive from ES URL."""
    kibana_url = os.environ.get("KIBANA_URL")
    if kibana_url:
        return kibana_url.rstrip("/")

    # Try to derive from ELASTICSEARCH_URL
    es_url = os.environ.get("ELASTICSEARCH_URL", "")
    if ".es." in es_url:
        # Cloud serverless: https://xxx.es.region.gcp.elastic.cloud -> https://xxx.kb.region.gcp.elastic.cloud
        kibana_url = es_url.replace(".es.", ".kb.")
        print(f"Derived KIBANA_URL from ELASTICSEARCH_URL: {kibana_url}")
        return kibana_url.rstrip("/")

    print("ERROR: KIBANA_URL environment variable not set")
    print("Please set KIBANA_URL to your Kibana endpoint")
    sys.exit(1)


def get_api_key():
    """Get API key from environment."""
    api_key = os.environ.get("ELASTICSEARCH_API_KEY")
    if not api_key:
        print("ERROR: ELASTICSEARCH_API_KEY environment variable not set")
        sys.exit(1)
    return api_key


def make_request(method, url, data=None, api_key=None):
    """Make HTTP request to Kibana API."""
    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true"
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


def create_tool(kibana_url, api_key, tool, dry_run=False):
    """Create a single tool."""
    tool_id = tool["id"]
    url = f"{kibana_url}/api/agent_builder/tools"

    if dry_run:
        print(f"  [DRY RUN] Would create tool: {tool_id}")
        return True

    status, response = make_request("POST", url, tool, api_key)

    if status in [200, 201]:
        print(f"  ✓ Created tool: {tool_id}")
        return True
    elif status == 409 or "already exists" in str(response).lower():
        print(f"  • Tool already exists: {tool_id}")
        return True
    else:
        print(f"  ✗ Failed to create tool {tool_id}: {status} - {response}")
        return False


def delete_tool(kibana_url, api_key, tool_id, dry_run=False):
    """Delete a single tool."""
    url = f"{kibana_url}/api/agent_builder/tools/{tool_id}"

    if dry_run:
        print(f"  [DRY RUN] Would delete tool: {tool_id}")
        return True

    status, response = make_request("DELETE", url, api_key=api_key)

    if status in [200, 204]:
        print(f"  ✓ Deleted tool: {tool_id}")
        return True
    elif status == 404:
        print(f"  • Tool not found (already deleted): {tool_id}")
        return True
    else:
        print(f"  ✗ Failed to delete tool {tool_id}: {status} - {response}")
        return False


def create_agent(kibana_url, api_key, agent, dry_run=False):
    """Create the agent."""
    agent_id = agent["id"]
    url = f"{kibana_url}/api/agent_builder/agents"

    if dry_run:
        print(f"  [DRY RUN] Would create agent: {agent_id}")
        return True

    status, response = make_request("POST", url, agent, api_key)

    if status in [200, 201]:
        print(f"  ✓ Created agent: {agent_id}")
        return True
    elif status == 409 or "already exists" in str(response).lower():
        print(f"  • Agent already exists: {agent_id}")
        return True
    else:
        print(f"  ✗ Failed to create agent {agent_id}: {status} - {response}")
        return False


def delete_agent(kibana_url, api_key, agent_id, dry_run=False):
    """Delete the agent."""
    url = f"{kibana_url}/api/agent_builder/agents/{agent_id}"

    if dry_run:
        print(f"  [DRY RUN] Would delete agent: {agent_id}")
        return True

    status, response = make_request("DELETE", url, api_key=api_key)

    if status in [200, 204]:
        print(f"  ✓ Deleted agent: {agent_id}")
        return True
    elif status == 404:
        print(f"  • Agent not found (already deleted): {agent_id}")
        return True
    else:
        print(f"  ✗ Failed to delete agent {agent_id}: {status} - {response}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Setup Agent Builder tools and agent for Review Fraud Workshop"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete existing tools and agent before creating"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making API calls"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Agent Builder Setup for Review Fraud Workshop")
    print("=" * 60)

    kibana_url = get_kibana_url()
    api_key = get_api_key()

    print(f"\nKibana URL: {kibana_url}")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print()

    # Delete existing resources if requested
    if args.delete:
        print("Deleting existing resources...")
        delete_agent(kibana_url, api_key, AGENT["id"], args.dry_run)
        for tool in TOOLS:
            delete_tool(kibana_url, api_key, tool["id"], args.dry_run)
        print()

    # Create tools
    print("Creating tools...")
    tools_success = True
    for tool in TOOLS:
        if not create_tool(kibana_url, api_key, tool, args.dry_run):
            tools_success = False
    print()

    # Create agent
    print("Creating agent...")
    agent_success = create_agent(kibana_url, api_key, AGENT, args.dry_run)
    print()

    # Summary
    print("=" * 60)
    if tools_success and agent_success:
        print("SUCCESS: All tools and agent created!")
        print()
        print("Next steps:")
        print("1. Open Kibana and navigate to Agent Builder")
        print("2. Find the 'Review Fraud Investigator' agent")
        print("3. Click 'Chat' to start investigating")
        print()
        print("Try asking:")
        print('  "What can you tell me about the most recent incident?"')
        print('  "Find reviews similar to food poisoning made me sick"')
    else:
        print("WARNING: Some resources failed to create")
        print("Check the error messages above and try again")
    print("=" * 60)

    return 0 if (tools_success and agent_success) else 1


if __name__ == "__main__":
    sys.exit(main())
