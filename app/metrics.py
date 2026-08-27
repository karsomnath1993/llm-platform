from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "llm_requests_total",
    "Total LLM chat requests",
    ["status"]
)

REQUEST_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "LLM request latency in seconds"
)

CACHE_HITS = Counter(
    "cache_hits_total",
    "Total cache hits"
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total cache misses"
)