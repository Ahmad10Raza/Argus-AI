from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    DEBUG = "DEBUG"

class EventSource(BaseModel):
    app: str
    pod: Optional[str] = None
    node: Optional[str] = None

class BaseEvent(BaseModel):
    event_id: str = Field(..., description="Unique UUID for this event")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: EventSource

class LogEvent(BaseEvent):
    event_type: str = "log"
    severity: Severity
    message: str
    raw: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MetricEvent(BaseEvent):
    event_type: str = "metric"
    metrics: Dict[str, float] = Field(..., description="Key-value pairs of metric name and value")
    tags: Dict[str, str] = Field(default_factory=dict)
