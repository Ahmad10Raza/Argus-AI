# Import Prometheus client library components for metrics collection
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps  # Preserves function metadata in decorators
import time  # For measuring request duration
from typing import Callable, Any  # Type hints for better code clarity

# ============================================================================
# METRIC DEFINITIONS
# ============================================================================

# Counter: A metric that only increases (never decreases)
# Used for counting events like total requests
REQUEST_COUNT = Counter(
    "http_requests_total",  # Metric name (appears in Prometheus)
    "Total HTTP requests",   # Human-readable description
    ["method", "endpoint", "status_code"]  # Labels for filtering/grouping data
    # Example: You can query requests by GET method, /api/users endpoint, 200 status
)

# Histogram: Records observations and counts them in configurable buckets
# Used for measuring distributions like request durations
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",  # Metric name
    "HTTP request latency",            # Description
    ["method", "endpoint"]             # Labels (no status_code since measured before response)
    # Automatically creates buckets: count, sum, and predefined duration buckets
)

# Counter for tracking ingested events (application-specific metric)
INGESTED_EVENTS = Counter(
    "ingested_events_total",          # Metric name
    "Total events received by ingestion service",  # Description
    ["type", "status"]                # Labels: event type and processing status
)

# ============================================================================
# DECORATOR FUNCTION FOR AUTOMATIC METRICS TRACKING
# ============================================================================

def track_metrics(endpoint_name: str):
    """
    Decorator factory that creates a decorator to track metrics for an endpoint.
    
    Args:
        endpoint_name: Name of the endpoint (e.g., "/api/users", "login")
    
    Returns:
        A decorator function that wraps async functions with metric tracking
    """
    
    # The actual decorator that will wrap the target function
    def decorator(func: Callable) -> Callable:
        """
        Decorator that wraps a function with metrics tracking logic.
        
        Args:
            func: The async function to be wrapped
            
        Returns:
            The wrapped function with metrics tracking
        """
        
        # @wraps preserves the original function's metadata (__name__, __doc__, etc.)
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            """
            Wrapper function that executes around the original function.
            Tracks request count, latency, and handles errors.
            
            Flow:
            1. Record start time
            2. Execute the original function
            3. Track success/failure
            4. Record metrics in the 'finally' block (always executes)
            """
            
            # HTTP method - hardcoded here, ideally extracted from request object
            method = "POST"  # Simplified for now, usually needs request object inspection
            
            # Record the start time to calculate duration later
            start_time = time.time()
            
            # Default to success status code
            status_code = 200
            
            try:
                # Execute the original async function with all its arguments
                result = await func(*args, **kwargs)
                return result  # Return the result to the caller
                
            except Exception as e:
                # If an exception occurs, mark it as a server error
                status_code = 500
                raise e  # Re-raise the exception so it's not swallowed
                
            finally:
                # This block ALWAYS executes, whether success or failure
                # Perfect for recording metrics
                
                # Calculate how long the request took
                duration = time.time() - start_time
                
                # Record the request duration in the histogram
                # .labels() sets the label values
                # .observe() records the duration value
                REQUEST_LATENCY.labels(
                    method=method, 
                    endpoint=endpoint_name
                ).observe(duration)
                
                # Increment the request counter
                # .inc() increases the counter by 1 (default)
                REQUEST_COUNT.labels(
                    method=method, 
                    endpoint=endpoint_name, 
                    status_code=status_code
                ).inc()
        
        return wrapper  # Return the wrapped function
    return decorator  # Return the decorator

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

"""
How to use this decorator:

@track_metrics(endpoint_name="/api/ingest")
async def ingest_data(data: dict):
    # Your endpoint logic here
    process_data(data)
    return {"status": "success"}

This will automatically track:
- Request count with method, endpoint, and status code
- Request latency (duration) with method and endpoint
- All metrics available at /metrics endpoint for Prometheus to scrape
"""