import asyncio
import json
import os
from aiokafka import AIOKafkaProducer
from libs.logging.logger import setup_logger

logger = setup_logger("kafka_producer", "ingestion-service")

class KafkaProducerWrapper:
    def __init__(self, bootstrap_servers: str = None):
        self.bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        self.producer = None

    async def start(self):
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.producer.start()
            logger.info(f"Kafka producer connected to {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise e

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")

    async def send(self, topic: str, value: dict):
        if not self.producer:
            raise RuntimeError("Producer not started")
        try:
            # Fire and forget for higher throughput, or await for reliability
            # For ingestion, usually we want some ack but not full blocking
            future = await self.producer.send(topic, value)
            logger.debug(f"Sent message to {topic}")
            return future
        except Exception as e:
            logger.error(f"Failed to send message to {topic}: {e}")
            raise e

kafka_producer = KafkaProducerWrapper()
