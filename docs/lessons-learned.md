# Lessons Learned - Review Bomb Workshop

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
