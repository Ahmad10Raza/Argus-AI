# Argus-AI Development Guide

This document serves as the **Engineer's Handbook** for the Argus-AI platform. It details the implemented architecture, code structure, component responsibilities, and workflows for development.

---

## 1. System Architecture

Argus-AI follows an **Event-Driven Microservices Architecture**.

### High-Level Flow

1. **Ingestion**: Receives raw logs/metrics via HTTP → Normalizes them → Publishes to Kafka.
2. **Bus**: Apache Kafka acts as the central nervous system, decoupling producers from consumers.
3. **storage/Intelligence/Action** (Future): Will consume events from Kafka.

### Network Topology (Docker Compose)

* **Docker Internal Network**: Services talk to Kafka via `kafka:29092`.
* **Host Machine (Localhost)**: Developers/Tools talk to Kafka via `localhost:9093`.

---

## 2. Monorepo Structure

We use a strict monorepo layout to manage services and shared code.

```
Argus-AI/
├── docs/                 # Design & Architecture documentation
├── infra/                # Infrastructure-as-Code (Docker/Terraform)
├── libs/                 # Shared Python libraries (installed by all services)
├── schemas/              # Language-agnostic JSON schemas (Data Contracts)
├── services/             # Microservices source code
│   └── ingestion_service/
└── tests/                # System-level integration tests
```

---

## 3. Component Deep Dive

### A. Shared Libraries (`libs/`)

These enforce consistency across all microservices.

* **`libs/schemas`**: Contains Pydantic models (e.g., `LogEvent`, `MetricEvent`).
  * *Purpose*: Ensures every service speaks the same data language.
  * *Code*: `services/ingestion_service/app/api/ingest.py` imports these to validate HTTP bodies.
* **`libs/logging`**: Configures structured JSON logging.
  * *Purpose*: Logs are machine-readable (JSON) for easy aggregation (ELK/Loki).
  * *Usage*: `logger = setup_logger("component_name", "service_name")`
* **`libs/observability`**: Prometheus decorators.
  * *Purpose*: Auto-instrument API endpoints with `http_requests_total` and latency metrics.
  * *Usage*: `@track_metrics("endpoint_label")` decorator on FastAPI routes.

### B. Ingestion Service (`services/ingestion_service`)

The entry point for all observability data.

* **`app/main.py`**:
  * Initialize FastAPI app.
  * Manages Lifecycle (starts/stops Kafka producer).
  * Mounts `/metrics` endpoint for Prometheus.
* **`app/core/kafka.py`**:
  * Wrapper around `aiokafka`.
  * Handles async message producing.
  * *Config*: defaults to `kafka:29092` (Docker internal).
* **`app/api/ingest.py`**:
  * `POST /logs`: Accepts `LogEvent` → Validates → Sends to `raw-logs` topic.
  * `POST /metrics`: Accepts `MetricEvent` → Validates → Sends to `raw-metrics` topic.
* **`Dockerfile`**:
  * Multi-stage build that installs `libs/` and service requirements.

---

## 4. Infrastructure (`infra/`)

* **`docker-compose.yml`**:
  * **Zookeeper**: Coordinator for Kafka.
  * **Kafka**: The event bus.
    * Port `9093`: For Host access.
    * Port `29092`: For Container access.
  * **Prometheus**: Scrapes metrics from services.
  * **Ingestion Service**: The app itself (Port `8000`).

---

## 5. Development Workflows

### Option A: Running with Docker (Recommended)

This ensures the environment matches production.

1. **Build**:

    ```bash
    sudo docker-compose -f infra/docker/docker-compose.yml build ingestion-service
    ```

2. **Start**:

    ```bash
    sudo docker-compose -f infra/docker/docker-compose.yml up -d
    ```

3. **Test**:

    ```bash
    curl -X POST http://localhost:8000/api/v1/logs \
      -H "Content-Type: application/json" \
      -d '{
        "event_id": "test-uuid",
        "source": {"app": "local-test"},
        "severity": "INFO",
        "message": "Testing Docker Setup"
      }'
    ```

### Option B: Running Locally (Python)

Useful for fast debugging, but requires switching config.

> **Crucial Config Change**: When running locally, the service cannot reach `kafka:29092`. It must connect to `localhost:9093`.

1. **Start Infra Only** (Kafka/Zookeeper):

    ```bash
    sudo docker-compose -f infra/docker/docker-compose.yml up -d kafka zookeeper
    ```

2. **Set Environment Variable**:

    ```bash
    export KAFKA_BOOTSTRAP_SERVERS="localhost:9093"
    ```

    *(Note: You might need to update `kafka.py` to read this env var if it's currently hardcoded)*
3. **Run**:

    ```bash
    python services/ingestion_service/app/main.py
    ```

### Troubleshooting

* **Kafka Connection Error**: If running locally, ensure you use `localhost:9093`. If running in Docker, use `kafka:29092`.
* **ModuleNotFoundError**: Ensure you run python from the **root** of the repository (`Argus-AI/`), so `services.ingestion...` and `libs...` can be resolved.

---

## 6. What's Next? (Roadmap)

* **Phase 3**: Implement the **Intelligence Service** to consume these Kafka events and detect anomalies.
