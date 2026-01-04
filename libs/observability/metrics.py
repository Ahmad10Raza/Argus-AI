from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time
from typing import Callable, Any

# Define standard metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

INGESTED_EVENTS = Counter(
    "ingested_events_total",
    "Total events received by ingestion service",
    ["type", "status"]
)

def track_metrics(endpoint_name: str):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            method = "POST" # Simplified for now, usually needs request object inspection
            start_time = time.time()
            status_code = 200
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                raise e
            finally:
                duration = time.time() - start_time
                REQUEST_LATENCY.labels(method=method, endpoint=endpoint_name).observe(duration)
                REQUEST_COUNT.labels(method=method, endpoint=endpoint_name, status_code=status_code).inc()
        return wrapper
    return decorator
