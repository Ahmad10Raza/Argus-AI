# ============================================================================
# IMPORTS
# ============================================================================

from datetime import datetime  # For timestamp fields
from enum import Enum  # For creating enumeration of fixed values
from typing import Dict, Any, Optional  # Type hints for better code clarity and validation
from pydantic import BaseModel, Field  # Pydantic for data validation and serialization

# ============================================================================
# ENUMERATIONS
# ============================================================================

class Severity(str, Enum):
    """
    Enumeration for log severity levels.
    
    Inherits from both str and Enum:
    - str: Makes enum values behave like strings (can be compared, serialized easily)
    - Enum: Restricts values to only those defined below
    
    Usage:
        severity = Severity.ERROR  # Valid
        severity = "INVALID"       # Would fail Pydantic validation
    
    Benefits:
    - Type safety: Only valid severity levels accepted
    - Auto-completion in IDEs
    - Clear documentation of allowed values
    """
    INFO = "INFO"          # General informational messages
    WARNING = "WARNING"    # Warning messages for potential issues
    ERROR = "ERROR"        # Error messages for failures
    CRITICAL = "CRITICAL"  # Critical system failures
    DEBUG = "DEBUG"        # Debug-level detailed information

# ============================================================================
# SOURCE INFORMATION MODEL
# ============================================================================

class EventSource(BaseModel):
    """
    Model representing the source/origin of an event.
    Used to track where events come from in a distributed system.
    
    Inherits from BaseModel (Pydantic):
    - Automatic data validation
    - JSON serialization/deserialization
    - Type checking at runtime
    """
    
    # Required field: Name of the application generating the event
    app: str
    # Example: "user-service", "payment-gateway", "api-gateway"
    
    # Optional field: Kubernetes pod name (only relevant in K8s environments)
    pod: Optional[str] = None
    # Example: "user-service-7d4f8c9b-xk2p9"
    # Optional[str] means: can be a string or None
    # = None sets the default value if not provided
    
    # Optional field: Node/server name where the event originated
    node: Optional[str] = None
    # Example: "worker-node-3", "192.168.1.50"

# ============================================================================
# BASE EVENT MODEL (PARENT CLASS)
# ============================================================================

class BaseEvent(BaseModel):
    """
    Base model for all event types.
    Contains common fields shared by all events.
    
    This is an abstract base class that other event types inherit from.
    Promotes code reuse and ensures consistency across event types.
    """
    
    # Unique identifier for the event
    event_id: str = Field(..., description="Unique UUID for this event")
    # Field(...) means: this field is REQUIRED (... is Ellipsis, means no default)
    # description: Provides documentation (appears in API docs, schema)
    # Example: "550e8400-e29b-41d4-a716-446655440000"
    
    # When the event occurred
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # default_factory: Calls datetime.utcnow() to generate timestamp when object is created
    # Why default_factory instead of default?
    #   - default=datetime.utcnow() would call it ONCE at class definition
    #   - default_factory=datetime.utcnow calls it EACH TIME a new object is created
    # Result: Each event gets the current time when it's created
    
    # Information about where the event came from
    source: EventSource
    # This is a nested Pydantic model
    # Pydantic automatically validates this as an EventSource object

# ============================================================================
# LOG EVENT MODEL (SPECIFIC EVENT TYPE)
# ============================================================================

class LogEvent(BaseEvent):
    """
    Model for log events (traditional application logs).
    
    Inherits from BaseEvent, so automatically includes:
    - event_id
    - timestamp
    - source
    
    Use case: Capturing application logs (INFO, ERROR, etc.)
    """
    
    # Type identifier for this event
    event_type: str = "log"
    # This is a CLASS-LEVEL default value
    # All LogEvent instances will have event_type="log"
    # Useful for discriminating between event types in a union
    
    # Log severity level (must be one of the Severity enum values)
    severity: Severity
    # Pydantic validates this is a valid Severity enum value
    # Example: severity=Severity.ERROR (valid)
    #          severity="INVALID" (validation error)
    
    # The actual log message
    message: str
    # Example: "User authentication failed for user_id: 12345"
    
    # Optional: Raw log string before parsing
    raw: Optional[str] = None
    # Useful for storing the original log line
    # Example: "[2024-01-04 10:30:45] ERROR: User authentication failed"
    
    # Additional contextual information
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Dict[str, Any] means: dictionary with string keys and any type of values
    # default_factory=dict creates a NEW empty dict for each instance
    # WARNING: Never use default={} - it creates a shared mutable default!
    # Example: {"user_id": 12345, "ip_address": "192.168.1.100", "endpoint": "/login"}

# ============================================================================
# METRIC EVENT MODEL (SPECIFIC EVENT TYPE)
# ============================================================================

class MetricEvent(BaseEvent):
    """
    Model for metric events (performance metrics, counters, gauges).
    
    Inherits from BaseEvent, so automatically includes:
    - event_id
    - timestamp  
    - source
    
    Use case: Capturing performance metrics, system stats, business metrics
    """
    
    # Type identifier for this event
    event_type: str = "metric"
    # All MetricEvent instances will have event_type="metric"
    
    # The actual metrics being reported
    metrics: Dict[str, float] = Field(..., description="Key-value pairs of metric name and value")
    # Dict[str, float] means: dictionary with string keys and float values
    # Field(...) means this is REQUIRED
    # Example: {
    #     "cpu_usage_percent": 78.5,
    #     "memory_mb": 2048.0,
    #     "request_count": 1523.0,
    #     "response_time_ms": 245.3
    # }
    
    # Additional labels/tags for filtering and grouping metrics
    tags: Dict[str, str] = Field(default_factory=dict)
    # Dict[str, str] means: dictionary with string keys and string values
    # Used for dimensions/labels in time-series databases
    # Example: {
    #     "environment": "production",
    #     "region": "us-east-1",
    #     "version": "v2.3.1",
    #     "service": "api"
    # }

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
# Creating a LogEvent:
log_event = LogEvent(
    event_id="550e8400-e29b-41d4-a716-446655440000",
    source=EventSource(app="user-service", pod="user-service-abc123"),
    severity=Severity.ERROR,
    message="Database connection failed",
    metadata={"db_host": "postgres.internal", "retry_count": 3}
)

# Creating a MetricEvent:
metric_event = MetricEvent(
    event_id="660e8400-e29b-41d4-a716-446655440001",
    source=EventSource(app="payment-service", node="worker-2"),
    metrics={
        "transactions_processed": 1523.0,
        "average_amount": 45.67,
        "error_rate": 0.02
    },
    tags={
        "payment_method": "credit_card",
        "currency": "USD"
    }
)

# Pydantic automatically validates:
invalid_log = LogEvent(
    event_id="123",
    source=EventSource(app="test"),
    severity="INVALID_LEVEL",  # ❌ ValidationError: not a valid Severity
    message="test"
)

# JSON serialization:
json_data = log_event.model_dump_json()
# Result: {"event_id": "550e...", "timestamp": "2024-01-04T10:30:45", ...}

# JSON deserialization:
log_event = LogEvent.model_validate_json(json_string)
"""
```

## Key Concepts Explained:

### **1. Pydantic BaseModel Benefits:**
- **Automatic validation**: Type checking at runtime
- **Serialization**: Easy conversion to/from JSON, dict
- **IDE support**: Auto-completion and type hints
- **Documentation**: Auto-generated schemas for API docs

### **2. Inheritance Hierarchy:**
```
BaseEvent (common fields)
    ├── LogEvent (log-specific fields)
    └── MetricEvent (metric-specific fields)