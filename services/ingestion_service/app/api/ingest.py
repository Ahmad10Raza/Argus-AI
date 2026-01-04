from fastapi import APIRouter, HTTPException, status
from libs.schemas.common import LogEvent, MetricEvent
from libs.logging.logger import setup_logger
from libs.observability.metrics import track_metrics, INGESTED_EVENTS
from services.ingestion_service.app.core.kafka import kafka_producer

router = APIRouter()
logger = setup_logger("ingest_api", "ingestion-service")

@router.post("/logs", status_code=status.HTTP_202_ACCEPTED)
@track_metrics("ingest_logs")
async def ingest_logs(event: LogEvent):
    """
    Ingest a log event, normalize it, and push to Kafka.
    """
    try:
        # Pydantic has already validated the schema at this point
        payload = event.model_dump(mode="json")
        
        # Push to Kafka
        await kafka_producer.send("raw-logs", payload)
        
        INGESTED_EVENTS.labels(type="log", status="success").inc()
        logger.debug(f"Ingested log event: {event.event_id}")
        return {"status": "accepted", "event_id": event.event_id}
        
    except Exception as e:
        logger.error(f"Failed to ingest log: {e}")
        INGESTED_EVENTS.labels(type="log", status="error").inc()
        raise HTTPException(status_code=500, detail="Internal processing error")

@router.post("/metrics", status_code=status.HTTP_202_ACCEPTED)
@track_metrics("ingest_metrics")
async def ingest_metrics(event: MetricEvent):
    """
    Ingest a metric event, normalize it, and push to Kafka.
    """
    try:
        payload = event.model_dump(mode="json")
        await kafka_producer.send("raw-metrics", payload)
        
        INGESTED_EVENTS.labels(type="metric", status="success").inc()
        logger.debug(f"Ingested metric event: {event.event_id}")
        return {"status": "accepted", "event_id": event.event_id}
        
    except Exception as e:
        logger.error(f"Failed to ingest metric: {e}")
        INGESTED_EVENTS.labels(type="metric", status="error").inc()
        raise HTTPException(status_code=500, detail="Internal processing error")
