# ============================================================================
# IMPORTS
# ============================================================================

import asyncio
# Async I/O library for concurrent operations
# Allows non-blocking Kafka operations

import json
# For serializing Python dicts to JSON strings
# Kafka stores messages as bytes, so we need serialization

import os
# For reading environment variables (configuration)

from aiokafka import AIOKafkaProducer
# Async Kafka client library for Python
# Non-blocking alternative to confluent-kafka or kafka-python
# Perfect for FastAPI (which is async)

from libs.logging.logger import setup_logger
# Custom logging setup for structured logs

# ============================================================================
# LOGGER SETUP
# ============================================================================

logger = setup_logger("kafka_producer", "ingestion-service")
# Create logger instance for this module
# Parameters:
#   - "kafka_producer": Logger name (identifies source of logs)
#   - "ingestion-service": Service name (for correlation across services)
# Logs will include context like: {"logger": "kafka_producer", "service": "ingestion-service"}

# ============================================================================
# KAFKA PRODUCER WRAPPER CLASS
# ============================================================================

class KafkaProducerWrapper:
    """
    Wrapper around AIOKafkaProducer for easier lifecycle management.
    
    Provides:
    - Automatic JSON serialization
    - Connection lifecycle management (start/stop)
    - Error handling and logging
    - Simplified send interface
    - Configuration from environment variables
    
    Why wrap the producer?
    - Encapsulates connection management logic
    - Provides consistent error handling
    - Makes testing easier (can mock this class)
    - Adds observability (logging)
    - Simplifies usage in FastAPI endpoints
    """
    
    def __init__(self, bootstrap_servers: str = None):
        """
        Initialize the Kafka producer wrapper.
        
        Args:
            bootstrap_servers: Comma-separated list of Kafka broker addresses
                             If None, reads from environment variable
                             Example: "kafka1:9092,kafka2:9092,kafka3:9092"
        
        Note: Producer is not connected yet - call start() to connect
        """
        
        # Get Kafka broker addresses
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        # Priority:
        #   1. Parameter passed to __init__
        #   2. Environment variable KAFKA_BOOTSTRAP_SERVERS
        #   3. Default: "kafka:29092" (common Docker Compose setup)
        # 
        # Why "kafka:29092"?
        #   - "kafka" is the Docker service name (DNS resolution in Docker network)
        #   - 29092 is the internal broker port (9092 is usually external)
        
        # Initialize producer as None (not connected yet)
        self.producer = None
        # Lazy initialization pattern: Don't connect until start() is called
        # Benefits:
        #   - Faster app startup
        #   - Can handle connection errors gracefully
        #   - Allows configuration changes before connection

    # ========================================================================
    # CONNECTION LIFECYCLE METHODS
    # ========================================================================

    async def start(self):
        """
        Start the Kafka producer and establish connection to brokers.
        
        This should be called during application startup (e.g., FastAPI lifespan event).
        
        Process:
        1. Create AIOKafkaProducer instance with configuration
        2. Connect to Kafka brokers
        3. Log success or raise exception on failure
        
        Raises:
            Exception: If connection to Kafka fails
        """
        try:
            # ================================================================
            # CREATE PRODUCER INSTANCE
            # ================================================================
            
            self.producer = AIOKafkaProducer(
                # Kafka broker addresses to connect to
                bootstrap_servers=self.bootstrap_servers,
                # Example: "kafka1:9092,kafka2:9092" or ["kafka1:9092", "kafka2:9092"]
                
                # Value serializer: Converts Python objects to bytes
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
                # Flow:
                #   Python dict → json.dumps() → JSON string → encode('utf-8') → bytes
                # Example:
                #   {"event_id": "123"} → '{"event_id": "123"}' → b'{"event_id": "123"}'
                # 
                # Why lambda?
                #   - AIOKafkaProducer calls this for each message
                #   - Takes value parameter (our dict)
                #   - Returns bytes that Kafka can store
                # 
                # Why UTF-8?
                #   - Universal text encoding
                #   - Compatible with all Kafka consumers
                #   - Standard for JSON data
                
                # Other common parameters (not used here but available):
                # key_serializer: For message keys (partitioning)
                # compression_type: 'gzip', 'snappy', 'lz4' (reduces network usage)
                # acks: 0 (no ack), 1 (leader ack), 'all' (all replicas ack)
                # retries: Number of retry attempts on failure
                # max_in_flight_requests_per_connection: Concurrent requests
                # linger_ms: Wait time to batch messages (throughput vs latency)
                # batch_size: Max batch size in bytes
            )
            
            # ================================================================
            # CONNECT TO KAFKA
            # ================================================================
            
            await self.producer.start()
            # Async operation that:
            #   1. Resolves broker addresses (DNS lookup)
            #   2. Establishes TCP connections to brokers
            #   3. Performs Kafka handshake protocol
            #   4. Fetches cluster metadata (topics, partitions)
            # 
            # This can fail if:
            #   - Kafka brokers are unreachable (network issue)
            #   - Bootstrap servers are misconfigured
            #   - Authentication fails (if SASL enabled)
            #   - Connection timeout
            
            # ================================================================
            # LOG SUCCESS
            # ================================================================
            
            logger.info(f"Kafka producer connected to {self.bootstrap_servers}")
            # Successful connection logged at INFO level
            # Helps verify service startup in logs
            # Example log: {"level": "INFO", "message": "Kafka producer connected to kafka:29092"}
            
        except Exception as e:
            # ================================================================
            # HANDLE CONNECTION FAILURE
            # ================================================================
            
            logger.error(f"Failed to start Kafka producer: {e}")
            # Log the error with full exception details
            # In production, this includes stack trace
            # Helps diagnose connection issues
            
            raise e
            # Re-raise the exception to stop application startup
            # FastAPI will catch this and prevent the app from starting
            # Better to fail fast than run without Kafka connection

    async def stop(self):
        """
        Stop the Kafka producer and close connections gracefully.
        
        This should be called during application shutdown (e.g., FastAPI lifespan event).
        
        Process:
        1. Check if producer exists
        2. Flush pending messages (send all buffered messages)
        3. Close connections to brokers
        4. Log shutdown
        
        Important: Always call this to avoid data loss!
        """
        
        # Check if producer was initialized and started
        if self.producer:
            # self.producer is None if start() was never called
            # or if it failed during initialization
            
            await self.producer.stop()
            # Graceful shutdown:
            #   1. Flush all buffered messages (send pending messages)
            #   2. Wait for in-flight requests to complete
            #   3. Close TCP connections to brokers
            # 
            # This ensures no message loss during shutdown
            # Blocks until all pending operations complete or timeout
            
            logger.info("Kafka producer stopped")
            # Log successful shutdown
            # Helps track service lifecycle in logs

    # ========================================================================
    # MESSAGE SENDING METHOD
    # ========================================================================

    async def send(self, topic: str, value: dict):
        """
        Send a message to a Kafka topic.
        
        Args:
            topic: Kafka topic name (e.g., "raw-logs", "raw-metrics")
            value: Python dictionary to send (will be JSON serialized)
                   Example: {"event_id": "123", "message": "test"}
        
        Returns:
            RecordMetadata: Metadata about the sent message
                           Contains: topic, partition, offset, timestamp
        
        Raises:
            RuntimeError: If producer not started (call start() first)
            Exception: If send fails (network error, topic doesn't exist, etc.)
        
        Performance Note:
        - This method awaits the send operation for reliability
        - For higher throughput, could use fire-and-forget pattern
        - Current approach balances reliability and performance
        """
        
        # ====================================================================
        # VALIDATE PRODUCER IS STARTED
        # ====================================================================
        
        if not self.producer:
            # Producer is None if start() hasn't been called
            raise RuntimeError("Producer not started")
            # Fail fast with clear error message
            # Prevents sending before connection is established
            # Helps catch programming errors during development
        
        try:
            # ================================================================
            # SEND MESSAGE TO KAFKA
            # ================================================================
            
            # Fire and forget for higher throughput, or await for reliability
            # For ingestion, usually we want some ack but not full blocking
            
            future = await self.producer.send(topic, value)
            # Parameters:
            #   - topic: Destination Kafka topic name
            #   - value: Dictionary (will be serialized by value_serializer)
            # 
            # What happens internally:
            #   1. value_serializer converts dict → JSON → bytes
            #   2. Message is added to internal buffer
            #   3. Producer sends batch to appropriate partition
            #   4. Waits for broker acknowledgment (acks setting)
            #   5. Returns RecordMetadata
            # 
            # await means: Wait for Kafka to acknowledge receipt
            # This provides reliability but adds latency (~1-50ms depending on config)
            # 
            # Alternative patterns:
            #   - Fire-and-forget: asyncio.create_task(self.producer.send(...))
            #     Faster but might lose messages on errors
            #   - Callbacks: self.producer.send(...).add_callback(...)
            #     Non-blocking with notification on success/failure
            
            # ================================================================
            # WHAT IS RecordMetadata (future)?
            # ================================================================
            # 
            # RecordMetadata contains:
            #   - topic: "raw-logs"
            #   - partition: 2 (which partition the message went to)
            #   - offset: 12345 (position in partition log)
            #   - timestamp: 1704369045123 (when broker received it)
            #   - serialized_key_size: 0 (if no key)
            #   - serialized_value_size: 256 (message size in bytes)
            # 
            # Uses:
            #   - Debugging: Know exactly where message was stored
            #   - Exactly-once semantics: Use offset for idempotency
            #   - Monitoring: Track partition distribution
            
            # ================================================================
            # LOG SUCCESS
            # ================================================================
            
            logger.debug(f"Sent message to {topic}")
            # Debug-level log (only visible if DEBUG logging enabled)
            # Prevents log flooding in production
            # Useful for development and troubleshooting
            # 
            # For production, might want to:
            #   - Log at INFO level but sample (e.g., every 100th message)
            #   - Use metrics instead (counter of messages sent)
            #   - Include event_id in log for correlation
            
            return future
            # Return metadata so caller can access partition, offset, etc.
            # Usually not needed but available for advanced use cases
            
        except Exception as e:
            # ================================================================
            # HANDLE SEND FAILURE
            # ================================================================
            
            logger.error(f"Failed to send message to {topic}: {e}")
            # Log the error with topic context
            # Common failures:
            #   - Topic doesn't exist (auto-create might be disabled)
            #   - Network partition (can't reach brokers)
            #   - Broker is down
            #   - Serialization error (value_serializer failed)
            #   - Buffer full (producing faster than Kafka can handle)
            #   - Message too large (exceeds max.message.bytes)
            
            raise e
            # Re-raise so FastAPI can return 500 to client
            # Client should retry or handle appropriately

# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

kafka_producer = KafkaProducerWrapper()
# Create a single shared instance of the producer
# This is the instance imported by other modules
# 
# Why singleton pattern?
#   - Share one connection pool across all requests
#   - Efficient: Don't create new connections per request
#   - Manage lifecycle centrally (start once, stop once)
# 
# Usage in other files:
#   from services.ingestion_service.app.core.kafka import kafka_producer
#   await kafka_producer.send("raw-logs", {"event_id": "123"})

# ============================================================================
# FASTAPI INTEGRATION EXAMPLE
# ============================================================================

"""
# In your FastAPI app startup:

from contextlib import asynccontextmanager
from fastapi import FastAPI
from services.ingestion_service.app.core.kafka import kafka_producer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to Kafka
    await kafka_producer.start()
    
    yield  # Application runs here
    
    # Shutdown: Disconnect from Kafka
    await kafka_producer.stop()

app = FastAPI(lifespan=lifespan)

# Now kafka_producer is ready to use in all endpoints!
"""

# ============================================================================
# ARCHITECTURE BENEFITS
# ============================================================================

"""
1. ASYNC/NON-BLOCKING:
   - Doesn't block FastAPI event loop
   - Can handle thousands of concurrent requests
   - Perfect for high-throughput ingestion

2. RELIABILITY:
   - Awaits broker acknowledgment
   - Exceptions propagate to caller
   - Graceful shutdown flushes pending messages

3. OBSERVABILITY:
   - Logs all connection events
   - Logs send failures
   - Can add metrics (total sent, errors, latency)

4. TESTABILITY:
   - Can mock KafkaProducerWrapper in tests
   - Can inject test configuration
   - Clear separation of concerns

5. SCALABILITY:
   - Single producer handles many concurrent sends
   - Connection pooling built into aiokafka
   - Can tune batch size, linger time for throughput

PERFORMANCE TUNING OPTIONS:

# Higher throughput (trades latency for throughput):
producer = AIOKafkaProducer(
    compression_type='lz4',      # Compress messages (reduces network)
    linger_ms=10,                # Wait 10ms to batch messages
    batch_size=32768,            # 32KB batches
    acks=1,                      # Only wait for leader ack (faster)
)

# Higher reliability (trades throughput for safety):
producer = AIOKafkaProducer(
    acks='all',                  # Wait for all replicas
    retries=10,                  # Retry 10 times on failure
    max_in_flight_requests_per_connection=1,  # Preserve order
)
"""