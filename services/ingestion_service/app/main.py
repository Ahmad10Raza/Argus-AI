import sys
import os

# Add the project root to python path so we can import 'libs'
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from fastapi import FastAPI
from contextlib import asynccontextmanager
from libs.logging.logger import setup_logger
from services.ingestion_service.app.core.kafka import kafka_producer
from services.ingestion_service.app.api import ingest
from prometheus_client import make_asgi_app

logger = setup_logger("main", "ingestion-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Ingestion Service...")
    # Initialize Kafka
    # In a real app we might retry connection here
    try:
        await kafka_producer.start()
    except Exception as e:
        logger.warning(f"Could not connect to Kafka on startup (normal during dev if kafka is initializing): {e}")

    yield
    
    # Shutdown
    logger.info("Shutting down Ingestion Service...")
    await kafka_producer.stop()

app = FastAPI(title="Argus AI Ingestion Service", version="0.1.0", lifespan=lifespan)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(ingest.router, prefix="/api/v1", tags=["ingestion"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ingestion-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.ingestion_service.app.main:app", host="0.0.0.0", port=8000, reload=True)
