# Lessons Learned - Review Fraud Detection Workshop

Patterns, gotchas, and recommendations discovered during development. Use this to accelerate future projects.

---

## Elasticsearch

### Serverless Compatibility
**Problem:** Index creation failed with "Settings [index.number_of_shards, index.number_of_replicas] are not available when running in serverless mode"

**Solution:** Remove `settings` section from index mappings entirely when targeting Elastic Cloud Serverless. Only include `mappings`.

```json
// BAD - fails on serverless
{
  "settings": { "number_of_shards": 1 },
  "mappings": { ... }
}

// GOOD - works everywhere
{
  "mappings": { ... }
}
```

### Data Type Strictness
**Problem:** Bulk indexing failed with boolean/date parsing errors

**Solutions:**
- Booleans must be actual `true`/`false`, not `1`/`0` integers
- Dates must be ISO format with timezone: `2024-01-15T10:30:00Z`, not `2024-01-15 10:30:00`

```python
# BAD
"is_open": 1
"date": datetime.strftime("%Y-%m-%d %H:%M:%S")

# GOOD
"is_open": True
"date": datetime.isoformat() + "Z"
```

### Async Client Requirements
**Problem:** `AsyncElasticsearch` requires `aiohttp` package but it's not auto-installed

**Solution:** Explicitly install: `pip install elasticsearch[async]` or `pip install aiohttp`

### ES|QL LOOKUP JOIN Requires Index Mode
**Problem:** LOOKUP JOIN queries fail with "Lookup Join requires a single lookup mode index"

**Root Cause:** ES|QL LOOKUP JOIN only works against indices configured with `index.mode: lookup`

**Solution:** Add settings to index mappings for indices that will be used in LOOKUP JOIN:

```json
{
  "settings": {
    "index": {
      "mode": "lookup"
    }
  },
  "mappings": {
    "properties": { ... }
  }
}
```

**Note:** The `lookup` mode index cannot be used for regular indexing operations - it's optimized for JOIN lookups. Use it for reference data (users, businesses) that changes infrequently.

### ES|QL Semantic Search with semantic_text Fields

**Problem:** Wanted to do semantic search in ES|QL but `MATCH(text_semantic, "query")` didn't work correctly.

**Root Cause:** The `MATCH()` function in ES|QL is for full-text search on `text` fields. For `semantic_text` fields, you must use the **`:` (colon) operator**.

**Solution:** Use the `:` operator with `METADATA _score` and `SORT _score DESC`:

```esql
// CORRECT - Semantic search in ES|QL
FROM reviews METADATA _score
| WHERE text_semantic: "food poisoning made me ill"
| SORT _score DESC
| KEEP review_id, text, stars, _score
| LIMIT 10
```

```esql
// WRONG - MATCH doesn't work properly with semantic_text
FROM reviews
| WHERE MATCH(text_semantic, "food poisoning")  // Returns random results
| LIMIT 10
```

**Key Points:**
1. **Use `:` operator** - `field: "query"` for semantic search
2. **Always use `METADATA _score`** - Captures relevance scores
3. **Always `SORT _score DESC`** - Without sorting, results are random
4. **Works in Discover** - No need to go to Dev Tools for semantic search
5. **Requires inference endpoint** - The `semantic_text` field must reference a valid inference endpoint (e.g., `.elser-2-elastic`)

**Mapping Setup:**
```json
{
  "mappings": {
    "properties": {
      "text": {
        "type": "text",
        "copy_to": "text_semantic"
      },
      "text_semantic": {
        "type": "semantic_text",
        "inference_id": ".elser-2-elastic"
      }
    }
  }
}
```

**Workshop Best Practice:** Whenever possible, stay in Discover and use ES|QL for all queries including semantic search. Only use Dev Tools for Kibana API calls (e.g., creating workflows with `kbn://` prefix).

### Date Format Flexibility in Mappings

**Problem:** Bulk indexing failed because date fields had different formats (`2016-03-12 18:07:31` vs ISO format)

**Solution:** Add multiple date formats to the mapping:

```json
{
  "date": {
    "type": "date",
    "format": "yyyy-MM-dd HH:mm:ss||strict_date_optional_time||epoch_millis"
  }
}
```

This accepts:
- `2016-03-12 18:07:31` (space-separated)
- `2016-03-12T18:07:31Z` (ISO format)
- `1647100051000` (epoch milliseconds)

### Streaming App Attacker Users (FIXED)
**Problem:** Streaming app generates attack reviews with `attacker_*` user IDs, but LOOKUP JOIN finds no matching users

**Root Cause:** The review_streamer.py creates reviews with dynamically generated user IDs but doesn't create corresponding user records in the users index

**Solution (Implemented):** The streaming app now automatically creates attacker user records when generating attack reviews:
- Each attack review creates a corresponding user in the `users` index
- Users have low trust scores (0.05-0.25) and low account ages (1-14 days)
- Duplicate users within a session are tracked and avoided
- The summary shows "Attacker users: N" count

```
============================================================
SESSION SUMMARY
============================================================
  Duration:          3.1 seconds
  Total reviews:     10
  Attack reviews:    10
  Attacker users:    10    <-- New!
  Errors:            0
============================================================
```

---

## FastAPI + Jinja2 Web Apps

### Templates Must Fetch Data
**Problem:** Created route handlers that rendered templates, but pages were blank

**Root Cause:** Templates had placeholder content or JavaScript that didn't actually call APIs

**Solution:** Always verify:
1. Template has JavaScript that calls your API endpoints
2. API endpoints return data in the format the JavaScript expects
3. JavaScript actually renders the data to DOM elements

### Auto-Refresh for Real-Time Dashboards
**Pattern:** For monitoring dashboards, implement auto-refresh:

```javascript
let refreshInterval = null;

function startAutoRefresh() {
    refreshInterval = setInterval(loadAllData, 3000); // Every 3 seconds
}

function stopAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
}

document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
    startAutoRefresh();
});
```

### Version Badges for Cache Debugging
**Problem:** User had old cached JavaScript, changes weren't taking effect

**Solution:** Add visible version indicator to confirm new code is loaded:

```html
<h1>Page Title <span class="badge bg-secondary">v3-bulk</span></h1>
```

Then tell user to hard refresh (Ctrl+Shift+R) and verify badge changed.

---

## Browser JavaScript Gotchas

### Navigation Kills Async Operations
**Problem:** User started turbo attack (25 reviews in a loop), navigated to dashboard, only 6 reviews created

**Root Cause:** JavaScript execution stops when user navigates away from page

**Solution:** Move long-running operations to server-side:

```python
# Server-side bulk endpoint
@router.post("/bulk-attack")
async def bulk_attack(business_id: str, count: int = 15):
    # Create all reviews in one atomic operation
    operations = []
    for i in range(count):
        operations.append({"index": {...}})
        operations.append(review_doc)
    await es.bulk(operations=operations, refresh=True)
    return {"success": True, "count": count}
```

```javascript
// Client just makes one request
async function turboAttack() {
    const response = await fetch(`/api/bulk-attack?count=25`, {method: 'POST'});
    // Completes even if user navigates away
}
```

### API Wrapper Error Handling
**Pattern:** Create a simple API wrapper with consistent error handling:

```javascript
const api = {
    async get(url) {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    },
    async post(url, data = {}) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    }
};
```

---

## API Design Patterns

### Explicit Flags Over Implicit Behavior
**Problem:** Attack reviews weren't being flagged as simulated

**Root Cause:** Frontend wasn't passing `is_simulated: true` in API calls

**Solution:**
1. Always explicitly pass flags in API calls
2. Don't rely on server to "know" the context
3. Consider making critical flags required parameters

```javascript
// BAD - relies on server knowing this is an attack
await api.post('/api/reviews', { business_id, text, stars });

// GOOD - explicit flag
await api.post('/api/reviews', { business_id, text, stars, is_simulated: true });
```

### Stats Endpoints for Real-Time Aggregations
**Pattern:** Static document fields (like `business.stars`) don't update when related documents change. Create stats endpoints for real-time aggregations:

```python
@router.get("/{business_id}/stats")
async def get_business_stats(business_id: str, hours: int = 24):
    # Aggregate from reviews index in real-time
    recent_stats = await es.search(
        index="reviews",
        query={"bool": {"must": [
            {"term": {"business_id": business_id}},
            {"range": {"date": {"gte": f"now-{hours}h"}}}
        ]}},
        aggs={
            "avg_rating": {"avg": {"field": "stars"}},
            "review_count": {"value_count": {"field": "review_id"}}
        }
    )
    return calculated_stats
```

### Bulk Endpoints with Refresh
**Pattern:** For operations that need immediate visibility, use `refresh=True`:

```python
await es.bulk(operations=operations, refresh=True)
```

Note: This has performance implications at scale. For high-volume production, consider `refresh=wait_for` or accept eventual consistency.

---

## Debugging Strategies

### Check Backend Before Frontend
When data isn't showing in UI:
1. First verify data exists via API: `curl http://localhost:8000/api/endpoint`
2. Then check browser console for JavaScript errors
3. Then check network tab for failed requests

### Add Console Logging with Prefixes
For debugging async flows, add prefixed logs:

```javascript
console.log('[TURBO v3] Starting attack...');
console.log('[TURBO v3] Response:', result);
console.log('[TURBO v3] Reviews returned:', result.reviews?.length);
```

### Test APIs with curl Before UI
Always verify API works independently:

```bash
# Test endpoint directly
curl -s "http://localhost:8000/api/reviews?page_size=5" | python3 -m json.tool

# Test POST with data
curl -s -X POST "http://localhost:8000/api/reviews" \
  -H "Content-Type: application/json" \
  -d '{"business_id":"xxx","text":"test","stars":1}'
```

---

## Project Structure Recommendations

### Separate Concerns
```
app/
├── main.py          # FastAPI app setup, routes for HTML pages
├── config.py        # Settings with environment variable loading
├── dependencies.py  # Dependency injection (ES client, etc.)
├── routers/         # API endpoints by domain
│   ├── businesses.py
│   ├── reviews.py
│   └── incidents.py
├── models/          # Pydantic models
├── services/        # Business logic
└── templates/       # Jinja2 templates
```

### Environment-Based Configuration
```python
class Settings(BaseSettings):
    elasticsearch_url: Optional[str] = Field(default=None, alias="ELASTICSEARCH_URL")
    elasticsearch_api_key: Optional[str] = Field(default=None, alias="ELASTICSEARCH_API_KEY")

    class Config:
        env_file = ".env"
```

---

## Communication Patterns

### When User Reports "It's Not Working"
1. Ask what they expected vs what happened
2. Check backend state independently (curl, direct ES query)
3. Verify they have latest code (version badge)
4. Check browser console for errors
5. Don't assume - verify each layer

### Iterative Debugging
When a fix doesn't work:
1. Add more logging/visibility
2. Verify the fix was actually deployed (cache issues are common)
3. Test the smallest unit independently
4. Work up the stack from data → API → JavaScript → UI

---

## Key Takeaways

1. **Server-side for reliability** - Don't trust browser JS for critical operations
2. **Explicit over implicit** - Pass flags, don't rely on context
3. **Real-time needs aggregation** - Static fields don't update; use stats endpoints
4. **Verify each layer** - Backend, API, JavaScript, UI are separate failure points
5. **Version badges save time** - Quick way to confirm cache is cleared
6. **Auto-refresh for dashboards** - Users expect real-time updates
7. **Serverless has constraints** - Test on target platform early
8. **Stay in Discover for ES|QL** - Semantic search works with `:` operator; avoid unnecessary Dev Tools hops
9. **Use `:` not `MATCH()` for semantic_text** - Different operators for different field types

---

## Streaming Application Patterns

### Rate-Limited Bulk Indexing
**Problem:** Need to stream documents at a controlled rate while using bulk API for efficiency

**Solution:** Batch documents and use time-based rate limiting:

```python
import asyncio
from datetime import datetime

class ReviewStreamer:
    def __init__(self, rate_per_second: float = 2.0, batch_size: int = 5):
        self.rate = rate_per_second
        self.batch_size = batch_size
        self.batch = []

    async def stream_reviews(self, reviews):
        for review in reviews:
            self.batch.append(review)

            if len(self.batch) >= self.batch_size:
                await self._flush_batch()
                # Rate limit based on batch size
                await asyncio.sleep(self.batch_size / self.rate)

        # Flush remaining
        if self.batch:
            await self._flush_batch()

    async def _flush_batch(self):
        operations = []
        for doc in self.batch:
            operations.append({"index": {"_index": "reviews"}})
            operations.append(doc)

        await self.es.bulk(operations=operations, refresh="wait_for")
        self.batch = []
```

### Graceful Shutdown with Signal Handling
**Pattern:** Allow Ctrl+C to stop streaming cleanly:

```python
import signal

class StreamerWithShutdown:
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        print("\nShutdown requested, finishing current batch...")
        self.running = False

    async def stream(self, items):
        for item in items:
            if not self.running:
                break
            await self._process(item)

        print("Graceful shutdown complete")
```

---

## Auto-Incident Creation Pattern

### Duplicate Prevention
**Problem:** Detection runs periodically; don't want duplicate incidents for same ongoing attack

**Solution:** Check for existing open incidents before creating:

```python
async def create_incident_if_needed(business_id: str, attack_data: dict):
    # Check for existing open incident
    result = await es.search(
        index="incidents",
        query={
            "bool": {
                "must": [
                    {"term": {"business_id": business_id}},
                    {"terms": {"status": ["detected", "investigating", "open"]}}
                ]
            }
        },
        size=1
    )

    if result["hits"]["total"]["value"] > 0:
        # Update existing incident instead of creating new
        existing = result["hits"]["hits"][0]
        await update_incident_metrics(existing["_id"], attack_data)
        return existing["_id"]

    # Create new incident
    incident = create_incident_document(business_id, attack_data)
    result = await es.index(index="incidents", document=incident)
    return result["_id"]
```

### Severity Classification
**Pattern:** Use thresholds to classify severity:

```python
def determine_severity(metrics: dict) -> str:
    velocity = metrics.get("review_velocity", 0)
    count = metrics.get("recent_review_count", 0)
    rating_drop = abs(metrics.get("rating_trend", 0))

    if velocity > 5 or count > 20:
        return "critical"
    elif velocity > 3 or count > 10 or rating_drop > 2.0:
        return "high"
    elif count >= 5 or metrics.get("suspicious_count", 0) > 3:
        return "medium"
    return "low"
```

---

## Parallel Agent Execution

### When to Parallelize
**Insight:** Independent tasks can be executed in parallel using multiple agents

**Good candidates for parallel execution:**
- Different modules/features with no dependencies
- Read-only exploration tasks
- Documentation generation
- Test writing for different components

**Bad candidates (run sequentially):**
- Tasks where one depends on output of another
- Tasks modifying the same files
- Tasks requiring user input/decisions between steps

### Example: Parallel Feature Implementation

```
User request: "Implement streaming app AND Agent Builder tools"

These are independent → Launch two agents in parallel:
- Agent 1: Streaming application
- Agent 2: Agent Builder tools

Result: Both complete faster than sequential execution
```

---

## Python Environment Gotchas

### System Python Without venv
**Problem:** `python3-venv` not installed, can't create virtual environment

**Solution:** Use `--break-system-packages` flag when system Python is the only option:

```bash
python3 -m pip install -r requirements.txt --break-system-packages
```

**Better solution (when possible):** Install venv package:
```bash
apt install python3.11-venv  # Debian/Ubuntu
```

### PATH Issues with pip-installed Scripts
**Problem:** Scripts installed by pip not found

**Solution:** Add user local bin to PATH:
```bash
export PATH="$PATH:/home/node/.local/bin"
```

Or in Python:
```python
import sys
sys.path.insert(0, "/home/node/.local/lib/python3.11/site-packages")
```

---

## Elasticsearch Bulk Operations

### Use refresh="wait_for" for Demos
**Problem:** Documents not immediately visible after bulk indexing

**Solution:** Use `refresh="wait_for"` to ensure visibility before returning:

```python
await es.bulk(operations=operations, refresh="wait_for")
```

**Trade-off:** Slower than default, but necessary for demos where you need immediate visibility.

### Bulk Operation Structure
**Pattern:** Alternating action/document pairs:

```python
operations = []
for doc in documents:
    operations.append({"index": {"_index": "reviews"}})  # Action
    operations.append(doc)                                # Document

# NOT this (common mistake):
# operations = [{"index": {...}, "document": doc}]  # Wrong!
```

---

## Workshop Content Organization

### Challenge Structure
**Pattern:** Each Instruqt challenge should have:

```
challenge-name/
├── assignment.md   # User-facing instructions (Markdown)
├── setup.sh        # Environment preparation (idempotent!)
├── check.sh        # Verification script (clear pass/fail)
└── solve.sh        # Solution for testing (optional)
```

### Idempotent Setup Scripts
**Requirement:** Setup scripts must be safe to run multiple times:

```bash
#!/bin/bash
set -e

# Check if already set up
if curl -s "$ES_URL/reviews" | grep -q '"reviews"'; then
    echo "Index already exists, skipping creation"
else
    echo "Creating reviews index..."
    curl -X PUT "$ES_URL/reviews" -d @mappings/reviews.json
fi
```

### Clear Check Script Feedback
**Pattern:** Give helpful error messages:

```bash
#!/bin/bash

# Check 1: Index exists
if ! curl -s "$ES_URL/reviews" | grep -q '"reviews"'; then
    echo "FAIL: Reviews index not found"
    echo "Hint: Did you run the create_indices.py script?"
    exit 1
fi

# Check 2: Data loaded
count=$(curl -s "$ES_URL/reviews/_count" | jq '.count')
if [ "$count" -lt 100 ]; then
    echo "FAIL: Expected at least 100 reviews, found $count"
    echo "Hint: Run load_data.py to populate the index"
    exit 1
fi

echo "SUCCESS: All checks passed!"
exit 0
```

---

## Kibana API - Serverless Restrictions

### Workflows Management API Not Available on Serverless

**Problem:** Workflows Management API endpoints return 404 on Cloud Serverless despite plugin showing as "available"

**Root Cause:** The Workflows feature requires `workflows:ui:enabled: true` setting, but:
1. The settings API (`/internal/kibana/settings`) is blocked on serverless
2. The feature is disabled by default and cannot be enabled via API

**What We Found (Kibana 9.4.0, `build_flavor: serverless`):**
```bash
# These all return 404
curl "$KIBANA_URL/api/workflows"
curl "$KIBANA_URL/api/workflows/{id}"
curl "$KIBANA_URL/internal/workflows_management/workflows"

# But the plugin shows as available
curl "$KIBANA_URL/api/status" | jq '.status.plugins.workflowsManagement'
# Returns: {"level": "available", "summary": "All services and plugins are available"}
```

**Documented Endpoints (from [Kibana README](https://github.com/elastic/kibana/blob/main/src/platform/plugins/shared/workflows_management/README.md)):**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/workflows` | List workflows |
| POST | `/api/workflows` | Create workflow |
| GET | `/api/workflows/{id}` | Get workflow |
| PUT | `/api/workflows/{id}` | Update workflow |
| DELETE | `/api/workflows/{id}` | Delete workflow |
| POST | `/api/workflows/{id}/execute` | Execute workflow |
| GET | `/api/workflows/{id}/executions` | Get execution history |

**Solution:** On Cloud Serverless, workflows must be managed via the Kibana UI (`/app/workflows`), not the API.

---

### Agent Builder API Works on Serverless

**Good News:** The Agent Builder API is fully functional on serverless:

```bash
# List tools - WORKS
curl -H "Authorization: ApiKey $API_KEY" -H "kbn-xsrf: true" \
  "$KIBANA_URL/api/agent_builder/tools"

# Create tool - WORKS
curl -X POST -H "Authorization: ApiKey $API_KEY" -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  "$KIBANA_URL/api/agent_builder/tools" \
  -d '{"id": "my.tool", "type": "esql", "description": "...", "configuration": {...}}'

# List agents - WORKS
curl -H "Authorization: ApiKey $API_KEY" -H "kbn-xsrf: true" \
  "$KIBANA_URL/api/agent_builder/agents"

# Chat with agent - WORKS
curl -X POST -H "Authorization: ApiKey $API_KEY" -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  "$KIBANA_URL/api/agent_builder/converse" \
  -d '{"input": "List all indices"}'
```

**Working Agent Builder Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agent_builder/tools` | List all tools |
| GET | `/api/agent_builder/tools/{id}` | Get tool by ID |
| POST | `/api/agent_builder/tools` | Create tool |
| DELETE | `/api/agent_builder/tools/{id}` | Delete tool |
| GET | `/api/agent_builder/agents` | List agents |
| GET | `/api/agent_builder/conversations` | List conversations |
| POST | `/api/agent_builder/converse` | Chat with agent |

### Agent Builder Tool Schema (API vs UI)

**Problem:** Creating tools via API failed with validation errors about missing `params` or `configuration`

**Root Cause:** The API schema differs from what you might expect from the UI:

```json
// WRONG - won't work
{
  "id": "my_tool",
  "type": "esql",
  "esql": {
    "query": "FROM reviews | LIMIT 10",
    "parameters": []
  }
}

// CORRECT - API schema
{
  "id": "my_tool",
  "type": "esql",
  "description": "Tool description",
  "configuration": {
    "query": "FROM reviews | WHERE business_id == \"{{business_id}}\" | LIMIT 10",
    "params": {
      "business_id": {
        "type": "text",
        "description": "The business ID to query"
      }
    }
  }
}
```

**Key Differences:**
- Use `configuration.query` not `esql.query`
- Use `configuration.params` object (keyed by param name) not `esql.parameters` array
- Each param is an object with `type` and `description` properties
- For no parameters, use `"params": {}` (empty object)

---

### Kibana API Authentication

**Pattern:** Use API key with `Authorization` header (not basic auth):

```bash
# WORKS - API Key auth
curl -H "Authorization: ApiKey <base64-encoded-key>" \
     -H "kbn-xsrf: true" \
     "$KIBANA_URL/api/agent_builder/tools"

# FAILS on serverless - Basic auth
curl -u "elastic:password" \
     -H "kbn-xsrf: true" \
     "$KIBANA_URL/api/agent_builder/tools"
# Returns: 401 Unauthorized
```

**Key Points:**
- Always include `-H "kbn-xsrf: true"` header
- Use the same API key as Elasticsearch
- Kibana URL uses `.kb.` instead of `.es.` in the hostname

---

### Serverless API Restrictions Summary

**Blocked on Serverless:**
- `/internal/kibana/settings` - Cannot change UI settings
- `/api/console/proxy` - Dev Tools console proxy
- `/api/saved_objects/_find` - Saved objects search
- `/api/workflows/*` - Workflow management (requires disabled feature flag)

**Working on Serverless:**
- `/api/status` - Kibana status and plugin info
- `/api/features` - List features and privileges
- `/api/agent_builder/*` - Full Agent Builder API
- `/api/alerting/*` - Alerting rules API
- `/api/actions/connectors` - List connectors
- `/api/spaces/*` - Spaces management

---

### Workflows API Requires Session Auth (Not API Key)

**Problem:** Workflows REST API returns "not available with current configuration" when using API key auth via curl.

**Root Cause:** The Workflows API requires **session-based authentication** (browser cookies), not API key authentication. This is different from Agent Builder and Alerting APIs which support API key auth.

**Tested on:** Kibana 9.3.0 GA and 9.3.0-SNAPSHOT

| API | API Key Auth (curl) | Session Auth (Dev Tools) |
|-----|---------------------|--------------------------|
| Agent Builder | ✅ Works | ✅ Works |
| Alerting | ✅ Works | ✅ Works |
| **Workflows** | ❌ Blocked | ✅ Works |

**Solution:** Use Kibana Dev Tools with `kbn://` prefix for Workflows API calls:

```
# First enable the feature
POST kbn://internal/kibana/settings
{"changes": {"workflows:ui:enabled": true}}

# Then query workflows
POST kbn://api/workflows/search
{"limit": 20, "page": 1, "query": ""}
```

**For automation/scripts:** Use the Kibana UI at `/app/workflows` or consider using the Alerting API (`/api/alerting/rules`) which supports API key auth for rule-based automation.

---

### Cloud URL Patterns

**Problem:** Kibana URL format differs between deployment types and may not match ES URL pattern.

**Cloud Serverless URLs:**
```
ES:     https://<deployment-id>.es.<region>.gcp.elastic.cloud:443
Kibana: https://<deployment-id>.kb.<region>.gcp.elastic.cloud:443
```

**Cloud Hosted URLs:**
```
ES:     https://<deployment-id>.<region>.gcp.elastic-cloud.com:443
Kibana: https://<deployment-name>.kb.<region>.gcp.elastic-cloud.com:443
```

**Key differences:**
- Serverless: `.elastic.cloud` domain, `.es.` and `.kb.` subdomains
- Hosted: `.elastic-cloud.com` domain, different URL structure
- Hosted Kibana URL may have a **different prefix** than ES URL
- Always check the Cloud console for exact Kibana endpoint

---

### Test Script for API Connectivity

Created `admin/test_kibana_api.sh` to verify cluster connectivity after switching environments.

**Usage:**
```bash
./admin/test_kibana_api.sh
```

**Tests:**
- Elasticsearch connection and version
- Kibana status
- Agent Builder API (tools, agents, conversations)
- Workflows API (with feature flag check)
- Alerting API
- Connectors API

**Output indicates:**
- ✓ PASS - Endpoint working
- ✗ FAIL - Endpoint failed
- ⚠ SKIP - Endpoint not available (expected for some configurations)

---

## Workshop Navigation Best Practices

### Stay in Discover for ES|QL Queries

**Problem:** Workshop initially directed participants to Dev Tools for ES|QL queries, causing unnecessary context switching.

**Solution:** Use Kibana Discover with ES|QL mode for all data exploration:

1. Navigate to **Discover** (Menu > Analytics > Discover)
2. Click the language dropdown and select **ES|QL**
3. Run queries directly - including semantic search!

**When to use each tool:**

| Task | Recommended Tool |
|------|------------------|
| ES|QL queries (analytics) | **Discover** |
| ES|QL queries (semantic search) | **Discover** |
| LOOKUP JOIN queries | **Discover** |
| Kibana API calls (`kbn://`) | Dev Tools |
| Creating Workflows | Dev Tools (requires `kbn://`) |
| Agent Builder UI setup | Agent Builder app |

**Why this matters:**
- Discover provides better visualization of results
- No context switching improves workshop flow
- Semantic search works in ES|QL with `:` operator
- Only use Dev Tools when you need Kibana API access

### ES|QL Query Reference

```esql
// Basic analytics
FROM reviews
| WHERE stars <= 2 AND date > NOW() - 30 minutes
| STATS count = COUNT(*) BY business_id
| SORT count DESC

// LOOKUP JOIN for enrichment
FROM reviews
| WHERE date > NOW() - 24 hours
| LOOKUP JOIN users ON user_id
| KEEP review_id, user_id, stars, trust_score

// Semantic search (note the : operator)
FROM reviews METADATA _score
| WHERE text_semantic: "food poisoning made me ill"
| SORT _score DESC
| KEEP review_id, text, stars, _score
| LIMIT 10
```

### ES|QL KEEP Clause Does Not Support Aliases

**Problem:** ES|QL query failed with "mismatched input 'AS' expecting {<EOF>..."

**Root Cause:** ES|QL KEEP clause does not support the `AS` alias syntax. You cannot rename columns in KEEP.

```esql
// WRONG - AS not valid in KEEP clause
| KEEP incident_id, business_name, stars AS business_original_rating

// Error: mismatched input 'AS' expecting {<EOF>...
```

**Solution:** Use EVAL to create the renamed column before KEEP:

```esql
// CORRECT - Use EVAL to rename, then KEEP the new name
| EVAL business_original_rating = stars
| KEEP incident_id, business_name, business_original_rating
```

**Key Points:**
1. KEEP only accepts column names, not transformations
2. Use EVAL to create new columns or rename existing ones
3. Place EVAL before KEEP in the pipeline
4. This is different from SQL's `SELECT ... AS ...` pattern

### ES|QL COUNT(CASE WHEN) Not Supported

**Problem:** ES|QL query failed with "no viable alternative at input 'COUNT(CASE WHEN'"

**Root Cause:** ES|QL doesn't support `COUNT(CASE WHEN ...)` conditional aggregation patterns common in SQL.

```esql
// WRONG - Not valid ES|QL
| STATS held_count = COUNT(CASE WHEN status == "held" THEN 1 END)
```

**Solution:** Use one of these alternatives:

1. **Group by status:**
```esql
| STATS count = COUNT(*) BY status
```

2. **Filter first, then count:**
```esql
| WHERE status == "held"
| STATS held_count = COUNT(*)
```

3. **Use AVG for ratio:**
```esql
| EVAL is_held = CASE(status == "held", 1, 0)
| STATS held_ratio = AVG(is_held)
```

---

## Bulk Operations Must Create Related Records

### LOOKUP JOIN Requires Matching Records

**Problem:** LOOKUP JOIN returned null for `trust_score` even though attack reviews existed

**Root Cause:** The bulk-attack endpoint created reviews with `user_id` values like `attacker_abc123`, but never created corresponding records in the `users` index.

**Debugging steps that revealed the issue:**
```esql
// Step 1: Found reviews exist
FROM reviews
| WHERE business_id == "target_biz_001"
| WHERE date > NOW() - 30 minutes
| STATS count = COUNT(*)
// Result: count = 44

// Step 2: Checked user_ids
FROM reviews
| WHERE business_id == "target_biz_001"
| WHERE stars <= 2
| KEEP user_id
| LIMIT 10
// Result: attacker_2e9be573, attacker_xxx, ...

// Step 3: LOOKUP JOIN returned null
FROM reviews
| WHERE business_id == "target_biz_001"
| LOOKUP JOIN users ON user_id
| WHERE trust_score IS NOT NULL
| STATS count = COUNT(*)
// Result: count = 0  <-- No matching users!
```

**Solution:** The bulk-attack endpoint must create BOTH reviews AND users in the same bulk operation:

```python
@router.post("/bulk-attack")
async def bulk_attack(business_id: str, count: int = 15):
    operations = []
    users_created = set()

    for i in range(count):
        review_id = f"attack_{uuid.uuid4().hex[:12]}"
        user_id = f"attacker_{uuid.uuid4().hex[:8]}"

        # Create attacker user FIRST (with low trust score)
        if user_id not in users_created:
            user_doc = {
                "user_id": user_id,
                "name": f"Attacker {user_id[-6:]}",
                "trust_score": round(random.uniform(0.05, 0.25), 2),  # Low!
                "account_age_days": random.randint(1, 14),  # New account
                "is_attacker": True
            }
            operations.append({"index": {"_index": "users", "_id": user_id}})
            operations.append(user_doc)
            users_created.add(user_id)

        # Then create the review
        review_doc = {
            "review_id": review_id,
            "business_id": business_id,
            "user_id": user_id,  # References the user created above
            "stars": 1,
            "text": "Terrible!",
            "is_simulated": True
        }
        operations.append({"index": {"_index": "reviews", "_id": review_id}})
        operations.append(review_doc)

    await es.bulk(operations=operations, refresh=True)
```

**Key Lesson:** When creating data for LOOKUP JOIN detection, ensure both sides of the join have matching records. This is especially important for attack simulation where synthetic data is generated.

---

## Workflow Response Actions

### Automated Response Requires Explicit Implementation

**Problem:** Detection workflow found attacks but didn't automatically protect businesses or hold reviews.

**Root Cause:** The detection endpoint created incidents but had no code to execute response actions.

**Solution:** Implement response actions in the incident service:

```python
class IncidentService:
    async def protect_business(self, business_id: str) -> bool:
        """Enable rating protection on a business."""
        await self.es.update(
            index=self.settings.businesses_index,
            id=business_id,
            doc={
                "rating_protected": True,
                "protection_reason": "review_fraud_detected",
                "protected_since": datetime.utcnow().isoformat(),
            },
            refresh=True
        )
        return True

    async def hold_suspicious_reviews(self, business_id: str, hours: int = 1) -> int:
        """Mark suspicious reviews as held."""
        response = await self.es.update_by_query(
            index=self.settings.reviews_index,
            query={
                "bool": {
                    "must": [
                        {"term": {"business_id": business_id}},
                        {"range": {"date": {"gte": f"now-{hours}h"}}},
                        {"range": {"stars": {"lte": 2}}},
                    ]
                }
            },
            script={
                "source": "ctx._source.status = 'held'; ctx._source.hold_reason = 'review_fraud_detected'"
            },
            refresh=True
        )
        return response.get("updated", 0)

    async def execute_response_actions(self, business_id: str, incident_id: str) -> dict:
        """Execute all response actions for a detected attack."""
        actions = []
        if await self.protect_business(business_id):
            actions.append("business_protected")
        held = await self.hold_suspicious_reviews(business_id)
        if held > 0:
            actions.append(f"held_{held}_reviews")
        return {"actions": actions, "reviews_held": held}
```

**Key Pattern:** Response actions should be called both for new incidents AND existing incidents (to catch newly arriving attack reviews).

---

## Agent Builder API Gotchas

### Agent Creation - Don't Include 'type' Field

**Problem:** Creating agent via API failed with "definition for this key is missing" error.

**Root Cause:** The `type` field is auto-assigned by the API. Including it in the request causes a validation error (confusing error message).

**Solution:** Omit the `type` field when creating agents:

```python
# WRONG - causes error
agent = {
    "id": "my_agent",
    "name": "My Agent",
    "type": "chat",  # DON'T include this!
    "description": "...",
    "configuration": {...}
}

# CORRECT - type is auto-assigned
agent = {
    "id": "my_agent",
    "name": "My Agent",
    "description": "...",
    "configuration": {
        "instructions": "System prompt...",
        "tools": [{"tool_ids": ["tool1", "tool2"]}]
    }
}
```

### Agent Tools Format

**Problem:** Agent creation failed with "could not parse object value from json input" for tools.

**Root Cause:** Tools must be an array of objects with `tool_ids`, not just an array of strings.

```python
# WRONG
"tools": ["tool1", "tool2"]

# CORRECT
"tools": [{"tool_ids": ["tool1", "tool2"]}]
```

### Checking Existing Agent Format

**Pattern:** When API schema is unclear, check existing resources:

```bash
curl -s "$KIBANA_URL/api/agent_builder/agents" \
  -H "Authorization: ApiKey $API_KEY" \
  -H "kbn-xsrf: true" | jq '.results[0]'
```

This reveals the actual schema used by successful resources.

---

## Elastic Workflows Gotchas

### ES|QL Results in Foreach Return Arrays, Not Objects

**Problem:** Workflow validation error "Variable foreach.item.business_id is invalid"

**Root Cause:** ES|QL queries return results as arrays of arrays (rows), not arrays of objects. Each row is an array where values are accessed by index based on the KEEP clause order.

```yaml
# WRONG - Treats ES|QL results as objects
- name: process_attacks
  type: foreach
  foreach: "{{ steps.detect_review_frauds.output.values }}"
  steps:
    - name: protect_business
      type: elasticsearch.update
      with:
        id: "{{ foreach.item.business_id }}"  # ❌ Invalid!
```

```yaml
# CORRECT - Use array indices based on KEEP clause order
# KEEP business_id, name, city, review_count, avg_stars, avg_trust, unique_attackers
#      [0]          [1]   [2]   [3]           [4]        [5]        [6]
- name: process_attacks
  type: foreach
  foreach: "{{ steps.detect_review_frauds.output.values }}"
  steps:
    - name: protect_business
      type: elasticsearch.update
      with:
        id: "{{ foreach.item[0] }}"  # ✅ business_id is first column

    - name: create_notification
      with:
        title: "Attack on {{ foreach.item[1] }}"  # ✅ name is second column
```

**Key Points:**
1. Always add a comment showing the column order from KEEP clause
2. Use `foreach.item[0]`, `foreach.item[1]`, etc.
3. This applies to all ES|QL query results in workflows

### Workflow Detection Query Must LOOKUP JOIN Before Filtering

**Problem:** Workflow detection query filtering on `trust_score < 0.4` but `trust_score` is on the `users` index, not `reviews`.

**Root Cause:** The original query tried to filter on trust_score before joining with users.

```esql
// WRONG - trust_score doesn't exist on reviews
FROM reviews
| WHERE date > NOW() - 30 minutes
  AND trust_score < 0.4  // ❌ Field doesn't exist!
  AND stars <= 2
```

```esql
// CORRECT - LOOKUP JOIN first, then filter
FROM reviews
| WHERE date > NOW() - 30 minutes
  AND stars <= 2
| LOOKUP JOIN users ON user_id  // ✅ Join first
| WHERE trust_score < 0.4        // ✅ Now trust_score exists
```

### Reviews Need Status Field for Workflow Detection

**Problem:** Workflow couldn't detect attack reviews because they lacked required fields.

**Root Cause:** The bulk-attack endpoint created reviews without `status` or `@timestamp` fields that the workflow detection query expected.

**Solution:** Ensure attack reviews include all fields the workflow expects:

```python
review_doc = {
    "review_id": review_id,
    "business_id": business_id,
    "user_id": user_id,
    "stars": float(stars),
    "text": text,
    "date": timestamp,
    "@timestamp": timestamp,      # ✅ For workflow detection
    "status": "pending",          # ✅ For workflow to detect and hold
    "is_simulated": True,
}
```

### Use Correct Timestamp Field Name

**Problem:** Workflow queries referenced `@timestamp` but reviews use `date` field.

**Solution:** Check actual field names in your mappings:

```esql
// WRONG - if your index uses 'date' field
| WHERE @timestamp > NOW() - 30 minutes

// CORRECT - use actual field name
| WHERE date > NOW() - 30 minutes
```

---

## Incident Data Model Gotchas

### Incident Status is "detected" Not "open"

**Problem:** ES|QL queries filtering `status == "open"` returned no results.

**Root Cause:** The incident service creates incidents with `status: "detected"`, not `status: "open"`.

```esql
// WRONG
FROM incidents
| WHERE status == "open"  // Returns 0 results

// CORRECT
FROM incidents
| WHERE status == "detected"  // Returns incidents
```

**Incident Status Lifecycle:**
1. `detected` - Initial status when attack is found
2. `investigating` - Analyst is reviewing
3. `resolved` - Investigation complete
4. `false_positive` - Determined not an attack

### Incident Metrics Use Nested Field Paths

**Problem:** ES|QL query `KEEP review_count, avg_rating` failed - fields not found.

**Root Cause:** Incident metrics are stored in a nested `metrics` object.

```json
{
  "incident_id": "inc_xxx",
  "severity": "critical",
  "metrics": {
    "review_count": 15,
    "average_rating": 1.47,
    "unique_attackers": 13
  }
}
```

```esql
// WRONG - fields don't exist at top level
| KEEP incident_id, review_count, avg_rating, unique_reviewers

// CORRECT - use nested paths
| KEEP incident_id, metrics.review_count, metrics.average_rating, metrics.unique_attackers
```

### Resolution Field Name

**Problem:** Query referencing `resolution_notes` returned null.

**Root Cause:** The field is named `resolution`, not `resolution_notes`.

```esql
// WRONG
| KEEP incident_id, status, resolution_notes

// CORRECT
| KEEP incident_id, status, resolution
```

---

## Real Yelp Data at Scale

### Using Yelp Academic Dataset

**Achievement:** Successfully loaded the full Yelp Academic Dataset:
- **14,338 businesses** (Philadelphia, Tampa, Tucson)
- **100,000+ users** with calculated trust scores
- **1,090,358 reviews** with semantic embeddings

**Key Learnings:**
1. Data preparation takes significant time (~36 minutes for 1M+ reviews)
2. Connection timeout errors during bulk loading may not indicate failure - data often loads successfully
3. The `prepare_data.sh` script filters to specific cities to manage dataset size
4. Trust scores must be calculated and added to user documents
5. Semantic text fields require inference endpoint setup before loading

### Target Business Selection

**Best Practice:** Use a real, recognizable business for demos:
- **Reading Terminal Market** (`ytynqOUb3hjKeJfRj5Tshw`)
- Philadelphia landmark, 4.6 stars, 1,860+ reviews
- High-profile target makes attack simulation more impactful

### Attacker User Pool

**Pattern:** Create synthetic attacker accounts with realistic low-trust characteristics:
```python
attacker = {
    "user_id": f"sim_attacker_{i:03d}",
    "name": "NewReviewer2024",
    "trust_score": random.uniform(0.05, 0.35),  # Low trust
    "account_age_days": random.randint(1, 21),   # New account
    "review_count": random.randint(0, 4),        # Few reviews
    "synthetic": True
}
```
