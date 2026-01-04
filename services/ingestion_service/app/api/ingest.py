# ============================================================================
# IMPORTS
# ============================================================================

from fastapi import APIRouter, HTTPException, status
# APIRouter: Creates a modular router for grouping related endpoints
# HTTPException: Raises HTTP errors with status codes and detail messages
# status: Contains HTTP status code constants (200, 404, 500, etc.)

from libs.schemas.common import LogEvent, MetricEvent
# Import the Pydantic models we defined earlier
# These will automatically validate incoming request data

from libs.logging.logger import setup_logger
# Custom logging setup function (likely configures structured logging)

from libs.observability.metrics import track_metrics, INGESTED_EVENTS
# track_metrics: The decorator we explained earlier for tracking request metrics
# INGESTED_EVENTS: The Prometheus Counter for tracking ingested events

from services.ingestion_service.app.core.kafka import kafka_producer
# Kafka producer instance for sending events to Kafka topics
# Kafka acts as a message queue/event stream

# ============================================================================
# ROUTER AND LOGGER SETUP
# ============================================================================

# Create a router instance for grouping ingestion endpoints
router = APIRouter()
# This router will be registered with the main FastAPI app
# Example: app.include_router(router, prefix="/api/v1/ingest")

# Initialize a logger specific to this module
logger = setup_logger("ingest_api", "ingestion-service")
# Parameters:
#   - "ingest_api": Logger name (helps identify log source)
#   - "ingestion-service": Service name (used for correlation)
# This logger likely outputs structured logs (JSON format)

# ============================================================================
# LOG INGESTION ENDPOINT
# ============================================================================

@router.post("/logs", status_code=status.HTTP_202_ACCEPTED)
# Decorator: Defines this as a POST endpoint at /logs
# status_code=202: "Accepted" - Request received but not yet processed
#   - 202 is appropriate for async processing (Kafka is async)
#   - Tells client: "I got your data, processing it asynchronously"

@track_metrics("ingest_logs")
# Custom decorator that tracks metrics for this endpoint:
#   - Request count (success/failure)
#   - Request latency (how long the function takes)
#   - Labeled with endpoint="ingest_logs"

async def ingest_logs(event: LogEvent):
    """
    Ingest a log event, normalize it, and push to Kafka.
    
    Flow:
    1. FastAPI automatically validates incoming JSON against LogEvent schema
    2. Convert Pydantic model to dictionary
    3. Send to Kafka topic "raw-logs"
    4. Track success/failure metrics
    5. Return acknowledgment to client
    
    Args:
        event: LogEvent - Automatically parsed and validated from request body
               FastAPI uses Pydantic to deserialize JSON → LogEvent object
               If validation fails, FastAPI returns 422 Unprocessable Entity
    
    Returns:
        dict: {"status": "accepted", "event_id": "..."}
    
    Raises:
        HTTPException: 500 if Kafka send fails or other processing error
    """
    try:
        # ====================================================================
        # STEP 1: CONVERT PYDANTIC MODEL TO DICTIONARY
        # ====================================================================
        
        # Pydantic has already validated the schema at this point
        # FastAPI did this automatically before calling this function
        # If data was invalid, we would never reach here (422 error sent)
        
        payload = event.model_dump(mode="json")
        # model_dump(): Converts Pydantic model to dict
        # mode="json": Ensures all values are JSON-serializable
        #   - datetime → ISO format string
        #   - Enum → string value
        #   - UUID → string
        # Example output: {
        #     "event_id": "550e8400-...",
        #     "timestamp": "2024-01-04T10:30:45.123456",
        #     "source": {"app": "user-service", "pod": "...", "node": null},
        #     "event_type": "log",
        #     "severity": "ERROR",
        #     "message": "Database connection failed",
        #     "raw": null,
        #     "metadata": {"db_host": "postgres.internal"}
        # }
        
        # ====================================================================
        # STEP 2: SEND TO KAFKA
        # ====================================================================
        
        # Push to Kafka topic for downstream processing
        await kafka_producer.send("raw-logs", payload)
        # Parameters:
        #   - "raw-logs": Kafka topic name (where raw log events are stored)
        #   - payload: The dictionary to send (will be serialized to JSON)
        # await: Waits for Kafka to acknowledge receipt
        # Benefits of Kafka:
        #   - Durability: Events are persisted
        #   - Decoupling: Consumers process independently
        #   - Scalability: Multiple consumers can process in parallel
        #   - Replay: Can reprocess events if needed
        
        # ====================================================================
        # STEP 3: TRACK SUCCESS METRICS
        # ====================================================================
        
        INGESTED_EVENTS.labels(type="log", status="success").inc()
        # Increment the Prometheus counter for successful log ingestion
        # labels(): Sets dimensions for filtering
        #   - type="log": Distinguishes from metric events
        #   - status="success": Tracks successful ingestions
        # inc(): Increments counter by 1
        # This allows Prometheus queries like:
        #   - Total logs ingested: ingested_events_total{type="log"}
        #   - Success rate: rate(ingested_events_total{status="success"}[5m])
        
        # ====================================================================
        # STEP 4: LOG DEBUG MESSAGE
        # ====================================================================
        
        logger.debug(f"Ingested log event: {event.event_id}")
        # Debug-level log (only visible if log level is DEBUG)
        # Helps with troubleshooting without cluttering production logs
        # Includes event_id for correlation with other logs
        
        # ====================================================================
        # STEP 5: RETURN SUCCESS RESPONSE
        # ====================================================================
        
        return {"status": "accepted", "event_id": event.event_id}
        # FastAPI automatically:
        #   - Converts dict to JSON
        #   - Sets Content-Type: application/json
        #   - Returns HTTP 202 (defined in decorator)
        # Client receives: {"status": "accepted", "event_id": "550e8400-..."}
        
    except Exception as e:
        # ====================================================================
        # ERROR HANDLING
        # ====================================================================
        
        # Catch any exception (Kafka connection failure, serialization error, etc.)
        logger.error(f"Failed to ingest log: {e}")
        # Log the error with full exception details
        # In production, this would include stack trace
        
        INGESTED_EVENTS.labels(type="log", status="error").inc()
        # Track failed ingestion in Prometheus
        # Allows monitoring of error rates and alerting
        
        raise HTTPException(status_code=500, detail="Internal processing error")
        # Raise HTTP 500 Internal Server Error
        # FastAPI converts this to JSON response:
        # {"detail": "Internal processing error"}
        # Note: We don't expose internal error details to client (security best practice)

# ============================================================================
# METRIC INGESTION ENDPOINT
# ============================================================================

@router.post("/metrics", status_code=status.HTTP_202_ACCEPTED)
# Separate endpoint for metrics (same pattern as logs)
# Keeps concerns separated and allows different routing/scaling

@track_metrics("ingest_metrics")
# Track metrics for this endpoint separately from logs endpoint
# Allows independent monitoring of log vs metric ingestion performance

async def ingest_metrics(event: MetricEvent):
    """
    Ingest a metric event, normalize it, and push to Kafka.
    
    Nearly identical to ingest_logs() but:
    - Uses MetricEvent schema instead of LogEvent
    - Sends to "raw-metrics" Kafka topic instead of "raw-logs"
    - Labels metrics with type="metric"
    
    This separation allows:
    - Different validation rules for logs vs metrics
    - Different downstream processing pipelines
    - Independent scaling (e.g., more resources for metrics if needed)
    - Clearer monitoring and alerting
    
    Args:
        event: MetricEvent - Validated metric event from request body
    
    Returns:
        dict: {"status": "accepted", "event_id": "..."}
    
    Raises:
        HTTPException: 500 if processing fails
    """
    try:
        # Convert Pydantic model to JSON-serializable dict
        payload = event.model_dump(mode="json")
        # Example payload: {
        #     "event_id": "660e8400-...",
        #     "timestamp": "2024-01-04T10:30:45.123456",
        #     "source": {"app": "payment-service", "pod": "...", "node": "worker-2"},
        #     "event_type": "metric",
        #     "metrics": {
        #         "transactions_processed": 1523.0,
        #         "average_amount": 45.67,
        #         "error_rate": 0.02
        #     },
        #     "tags": {
        #         "payment_method": "credit_card",
        #         "currency": "USD"
        #     }
        # }
        
        # Send to metrics-specific Kafka topic
        await kafka_producer.send("raw-metrics", payload)
        # Downstream consumers can subscribe to "raw-metrics" topic
        # Separate topic allows different:
        #   - Retention policies (metrics might be kept longer)
        #   - Partitioning strategies (for parallel processing)
        #   - Consumer groups (different services process logs vs metrics)
        
        # Track successful metric ingestion
        INGESTED_EVENTS.labels(type="metric", status="success").inc()
        # Now we can monitor:
        #   - Log ingestion rate: rate(ingested_events_total{type="log"}[5m])
        #   - Metric ingestion rate: rate(ingested_events_total{type="metric"}[5m])
        #   - Compare volumes and success rates
        
        logger.debug(f"Ingested metric event: {event.event_id}")
        
        return {"status": "accepted", "event_id": event.event_id}
        
    except Exception as e:
        logger.error(f"Failed to ingest metric: {e}")
        INGESTED_EVENTS.labels(type="metric", status="error").inc()
        raise HTTPException(status_code=500, detail="Internal processing error")

# ============================================================================
# ARCHITECTURE OVERVIEW
# ============================================================================

"""
REQUEST FLOW:

1. Client sends POST to /logs or /metrics with JSON body
   ↓
2. FastAPI receives request
   ↓
3. Pydantic validates JSON against LogEvent/MetricEvent schema
   - If invalid: Return 422 Unprocessable Entity
   - If valid: Continue to handler function
   ↓
4. @track_metrics decorator starts timing the request
   ↓
5. Handler function executes:
   - Convert Pydantic model to dict
   - Send to Kafka topic
   - Track success metric
   - Log debug message
   - Return 202 response
   ↓
6. @track_metrics decorator records:
   - Request duration
   - Request count
   - Success/failure status
   ↓
7. Client receives 202 Accepted response

DOWNSTREAM PROCESSING:

Kafka Topic: raw-logs / raw-metrics
   ↓
Consumer Service (e.g., processor-service)
   ↓
Parse, enrich, transform events
   ↓
Store in databases, data lakes, or forward to other systems
   ↓
Query and visualization tools (Grafana, Kibana, etc.)

MONITORING:

Prometheus scrapes /metrics endpoint:
- http_requests_total{endpoint="ingest_logs", status_code="202"}
- http_request_duration_seconds{endpoint="ingest_logs"}
- ingested_events_total{type="log", status="success"}

Grafana dashboards show:
- Ingestion rate (events/second)
- Error rate (errors/total)
- Latency (p50, p95, p99)
- Event type distribution (logs vs metrics)
"""