# ============================================================================
# PYTHON PATH CONFIGURATION
# ============================================================================

import sys
import os

# Add the project root to python path so we can import 'libs'
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
# 
# PATH MANIPULATION BREAKDOWN:
# 
# __file__                           → /path/to/services/ingestion_service/app/main.py
# os.path.abspath(__file__)          → /path/to/services/ingestion_service/app/main.py (absolute)
# os.path.dirname(...)               → /path/to/services/ingestion_service/app
# os.path.dirname(...)               → /path/to/services/ingestion_service
# os.path.dirname(...)               → /path/to/services
# os.path.dirname(...)               → /path/to (PROJECT ROOT)
# 
# WHY THIS IS NEEDED:
# - Python's import system looks for modules in sys.path
# - By default, only the script's directory is in sys.path
# - We have a 'libs' folder at project root that needs to be importable
# - This adds project root so we can do: from libs.logging.logger import ...
# 
# PROJECT STRUCTURE:
# /path/to/                          ← Added to sys.path
# ├── libs/                          ← Now importable
# │   ├── logging/
# │   ├── observability/
# │   └── schemas/
# ├── services/
# │   └── ingestion_service/
# │       └── app/
# │           └── main.py            ← Current file
# 
# ALTERNATIVE APPROACHES:
# - Use PYTHONPATH environment variable: export PYTHONPATH=/path/to
# - Install project as package: pip install -e .
# - Use relative imports (more complex, less flexible)

# ============================================================================
# IMPORTS
# ============================================================================

from fastapi import FastAPI
# Main FastAPI application class
# Handles routing, middleware, startup/shutdown events

from contextlib import asynccontextmanager
# Context manager for managing async resources (startup/shutdown)
# Replaces older @app.on_event("startup") and @app.on_event("shutdown")

from libs.logging.logger import setup_logger
# Custom logging configuration (structured logs)

from services.ingestion_service.app.core.kafka import kafka_producer
# Singleton Kafka producer instance we created earlier

from services.ingestion_service.app.api import ingest
# Router containing /logs and /metrics endpoints

from prometheus_client import make_asgi_app
# Creates an ASGI app that serves Prometheus metrics
# Exposes /metrics endpoint for Prometheus scraping

# ============================================================================
# LOGGER SETUP
# ============================================================================

logger = setup_logger("main", "ingestion-service")
# Create logger for this module
# Parameters:
#   - "main": Logger name (identifies this is the main app file)
#   - "ingestion-service": Service name (for correlation)
# Used for logging application lifecycle events

# ============================================================================
# APPLICATION LIFECYCLE MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle: startup and shutdown events.
    
    This is the modern FastAPI way to handle lifecycle events.
    Replaces the older @app.on_event("startup") and @app.on_event("shutdown").
    
    Flow:
    1. Code before 'yield' runs at startup
    2. Application runs (handles requests)
    3. Code after 'yield' runs at shutdown
    
    Why context manager?
    - Guarantees cleanup code runs even if startup fails
    - Single place for startup/shutdown logic
    - More Pythonic than separate event handlers
    - Better error handling
    """
    
    # ========================================================================
    # STARTUP LOGIC
    # ========================================================================
    
    # Log application startup
    logger.info("Starting Ingestion Service...")
    # Appears in logs when service starts
    # Example: {"level": "INFO", "message": "Starting Ingestion Service...", "service": "ingestion-service"}
    
    # Initialize Kafka producer connection
    # In a real app we might retry connection here
    try:
        await kafka_producer.start()
        # Attempts to connect to Kafka brokers
        # This is an async operation that:
        #   1. Resolves broker addresses
        #   2. Establishes TCP connections
        #   3. Performs Kafka handshake
        #   4. Fetches cluster metadata
        # 
        # If successful:
        #   - Producer is ready to send messages
        #   - Application can start accepting requests
        
    except Exception as e:
        # GRACEFUL DEGRADATION STRATEGY
        logger.warning(f"Could not connect to Kafka on startup (normal during dev if kafka is initializing): {e}")
        # 
        # WHY WARNING INSTEAD OF ERROR?
        # - In development, Kafka might not be ready yet
        # - Docker Compose starts services in parallel
        # - Kafka takes time to initialize (30-60 seconds)
        # - Service can still start and health checks pass
        # 
        # PRODUCTION CONSIDERATIONS:
        # In production, you might want to:
        #   1. Retry connection with exponential backoff
        #   2. Fail startup if Kafka is critical
        #   3. Use Kubernetes readiness probes
        #   4. Implement circuit breaker pattern
        # 
        # Example retry logic:
        # for i in range(5):
        #     try:
        #         await kafka_producer.start()
        #         break
        #     except:
        #         await asyncio.sleep(2 ** i)  # Exponential backoff
        # else:
        #     raise RuntimeError("Could not connect to Kafka after retries")

    # ========================================================================
    # YIELD - APPLICATION RUNS HERE
    # ========================================================================
    
    yield
    # Everything after this point runs at SHUTDOWN
    # 
    # While yielded:
    # - FastAPI accepts and processes HTTP requests
    # - Endpoints handle /logs and /metrics
    # - Prometheus scrapes /metrics
    # - Application runs normally
    
    # ========================================================================
    # SHUTDOWN LOGIC
    # ========================================================================
    
    # Log application shutdown
    logger.info("Shutting down Ingestion Service...")
    # Triggered by:
    #   - SIGTERM signal (Kubernetes pod termination)
    #   - SIGINT signal (Ctrl+C)
    #   - Application crash
    #   - Docker stop command
    
    # Gracefully stop Kafka producer
    await kafka_producer.stop()
    # CRITICAL: This ensures no message loss
    # Process:
    #   1. Flush all buffered messages (send pending messages)
    #   2. Wait for in-flight requests to complete
    #   3. Close connections to brokers
    # 
    # Without this:
    #   - Buffered messages would be lost
    #   - In-flight messages might fail
    #   - Connections would be abruptly closed
    # 
    # Kubernetes termination flow:
    #   1. SIGTERM sent to pod
    #   2. lifespan shutdown code runs (this block)
    #   3. 30-second grace period (configurable)
    #   4. SIGKILL if not stopped (force kill)

# ============================================================================
# FASTAPI APPLICATION INSTANCE
# ============================================================================

app = FastAPI(
    title="Argus AI Ingestion Service",
    # Application title (appears in OpenAPI docs)
    # Shown in Swagger UI header
    
    version="0.1.0",
    # API version (semantic versioning)
    # Helps clients track breaking changes
    # Should increment with API changes
    
    lifespan=lifespan
    # Pass our lifecycle manager
    # FastAPI will:
    #   1. Call lifespan function at startup
    #   2. Execute code before yield
    #   3. Keep application running
    #   4. Execute code after yield at shutdown
)
# 
# OTHER COMMON FASTAPI PARAMETERS:
# - description: Longer API description
# - docs_url: Custom Swagger UI path (default: "/docs")
# - redoc_url: Custom ReDoc path (default: "/redoc")
# - openapi_url: OpenAPI schema path (default: "/openapi.json")
# - middleware: List of middleware to apply
# - exception_handlers: Custom exception handlers

# ============================================================================
# PROMETHEUS METRICS ENDPOINT
# ============================================================================

# Create ASGI app that serves Prometheus metrics
metrics_app = make_asgi_app()
# Creates a complete ASGI application that:
#   - Exposes /metrics endpoint
#   - Returns metrics in Prometheus text format
#   - Includes all registered metrics (REQUEST_COUNT, REQUEST_LATENCY, etc.)
# 
# Example response:
# # HELP http_requests_total Total HTTP requests
# # TYPE http_requests_total counter
# http_requests_total{method="POST",endpoint="ingest_logs",status_code="202"} 1523.0
# http_requests_total{method="POST",endpoint="ingest_logs",status_code="500"} 5.0
# 
# # HELP http_request_duration_seconds HTTP request latency
# # TYPE http_request_duration_seconds histogram
# http_request_duration_seconds_bucket{method="POST",endpoint="ingest_logs",le="0.005"} 1200.0
# http_request_duration_seconds_bucket{method="POST",endpoint="ingest_logs",le="0.01"} 1450.0
# http_request_duration_seconds_sum{method="POST",endpoint="ingest_logs"} 345.67
# http_request_duration_seconds_count{method="POST",endpoint="ingest_logs"} 1523.0

# Mount metrics app at /metrics path
app.mount("/metrics", metrics_app)
# Mounts the Prometheus metrics ASGI app
# Now accessible at: http://localhost:8000/metrics
# 
# mount() vs include_router():
#   - mount(): Mounts entire ASGI/WSGI app (separate app)
#   - include_router(): Adds FastAPI routes (same app)
# 
# Prometheus will scrape this endpoint periodically:
# scrape_configs:
#   - job_name: 'ingestion-service'
#     static_configs:
#       - targets: ['ingestion-service:8000']
#     metrics_path: '/metrics'
#     scrape_interval: 15s

# ============================================================================
# INCLUDE API ROUTERS
# ============================================================================

app.include_router(ingest.router, prefix="/api/v1", tags=["ingestion"])
# Add the ingestion router to the application
# 
# Parameters:
#   - ingest.router: The APIRouter instance with /logs and /metrics endpoints
#   - prefix="/api/v1": Prepends to all routes
#   - tags=["ingestion"]: Groups endpoints in OpenAPI docs
# 
# RESULTING ENDPOINTS:
# - POST /api/v1/logs      (from ingest.router)
# - POST /api/v1/metrics   (from ingest.router)
# 
# WHY USE PREFIX?
# - API versioning: /api/v1, /api/v2 (can run multiple versions)
# - Clear URL structure: /api/v1/ingest, /api/v1/query
# - Easier to deprecate old versions
# - Standard REST API convention
# 
# WHY USE TAGS?
# - Organizes OpenAPI/Swagger documentation
# - Groups related endpoints together
# - Makes docs easier to navigate
# - Can apply middleware to specific tags

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    
    Used by:
    - Kubernetes liveness probes (is container alive?)
    - Kubernetes readiness probes (is service ready for traffic?)
    - Load balancers (should traffic be routed here?)
    - Monitoring systems (is service up?)
    
    Returns:
        dict: {"status": "ok", "service": "ingestion-service"}
    
    Note: This is a basic check - always returns 200 OK
    """
    return {"status": "ok", "service": "ingestion-service"}
    # Always returns success
    # Indicates the Python process is running
    # 
    # PRODUCTION IMPROVEMENTS:
    # 1. Check Kafka connection:
    #    if not kafka_producer.producer:
    #        raise HTTPException(503, "Kafka not connected")
    # 
    # 2. Check dependencies:
    #    - Database connection
    #    - Redis connection
    #    - External API availability
    # 
    # 3. Return detailed status:
    #    return {
    #        "status": "healthy",
    #        "service": "ingestion-service",
    #        "version": "0.1.0",
    #        "kafka": "connected",
    #        "uptime": time.time() - start_time
    #    }
    # 
    # 4. Separate liveness vs readiness:
    #    @app.get("/health/live")  - Just check process is alive
    #    @app.get("/health/ready") - Check all dependencies ready

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Direct execution entry point.
    
    Runs when executing: python main.py
    Does NOT run when importing: from main import app
    
    Used for:
    - Local development
    - Quick testing
    - Debugging
    
    Production: Use uvicorn directly or via Docker
    """
    
    import uvicorn
    # ASGI server for running FastAPI applications
    # High-performance async server
    # Alternative to gunicorn + uvicorn workers
    
    uvicorn.run(
        "services.ingestion_service.app.main:app",
        # Application path: "module:variable"
        # Format: "path.to.module:app_instance_name"
        # 
        # WHY STRING PATH INSTEAD OF app OBJECT?
        # - Enables auto-reload (can reimport module)
        # - Fresh import on code changes
        # - Better memory management
        # 
        # If you pass app directly:
        #   uvicorn.run(app, ...)  # Auto-reload won't work properly
        
        host="0.0.0.0",
        # Listen on all network interfaces
        # "0.0.0.0" means: accept connections from anywhere
        # "127.0.0.1" would only accept localhost connections
        # 
        # Docker containers need "0.0.0.0" to accept external traffic
        
        port=8000,
        # Port to listen on
        # HTTP server will be available at: http://localhost:8000
        # 
        # Common ports:
        #   - 8000: Development default
        #   - 80: HTTP (requires root/admin)
        #   - 443: HTTPS (requires root/admin + SSL cert)
        
        reload=True
        # Auto-reload on code changes
        # 
        # HOW IT WORKS:
        #   1. Watches Python files for changes
        #   2. Detects file modification
        #   3. Restarts server automatically
        #   4. Reimports all modules
        # 
        # DEVELOPMENT ONLY:
        #   - Slower startup (watches file system)
        #   - Higher memory usage (keeps multiple processes)
        #   - Not suitable for production
        # 
        # PRODUCTION:
        #   reload=False  # Or omit parameter
        #   workers=4     # Multiple worker processes
        #   # Use process manager like systemd or supervisord
    )
    # 
    # PRODUCTION DEPLOYMENT EXAMPLE:
    # 
    # Using Docker:
    #   CMD ["uvicorn", "services.ingestion_service.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    # 
    # Using systemd:
    #   ExecStart=/usr/bin/uvicorn services.ingestion_service.app.main:app --host 0.0.0.0 --port 8000 --workers 4
    # 
    # Using Kubernetes:
    #   command: ["uvicorn", "services.ingestion_service.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================================================
# COMPLETE APPLICATION FLOW
# ============================================================================

"""
1. APPLICATION STARTUP:
   python main.py
   ↓
   uvicorn.run() starts
   ↓
   FastAPI initializes
   ↓
   lifespan() startup code executes:
     - Logger initialized
     - Kafka producer connects
   ↓
   Application ready for requests

2. REQUEST HANDLING:
   Client → POST /api/v1/logs
   ↓
   FastAPI routes to ingest.ingest_logs()
   ↓
   @track_metrics decorator measures latency
   ↓
   Pydantic validates request body
   ↓
   Handler sends to Kafka
   ↓
   Metrics recorded
   ↓
   Response returned (202 Accepted)

3. METRICS SCRAPING:
   Prometheus → GET /metrics
   ↓
   metrics_app returns all metrics
   ↓
   Prometheus stores time-series data
   ↓
   Grafana visualizes metrics

4. HEALTH CHECKS:
   Load Balancer → GET /health
   ↓
   health_check() returns {"status": "ok"}
   ↓
   Load balancer routes traffic to healthy instances

5. APPLICATION SHUTDOWN:
   SIGTERM received (Ctrl+C or Kubernetes)
   ↓
   lifespan() shutdown code executes:
     - Kafka producer stops (flushes messages)
     - Connections closed gracefully
   ↓
   Application exits

KUBERNETES DEPLOYMENT EXAMPLE:

apiVersion: apps/v1
kind: Deployment
metadata:
  name: ingestion-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: ingestion
        image: ingestion-service:0.1.0
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        env:
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka:29092"

---
apiVersion: v1
kind: Service
metadata:
  name: ingestion-service
spec:
  selector:
    app: ingestion
  ports:
  - port: 8000
    targetPort: 8000
  type: LoadBalancer
"""