import json
import logging
from typing import Any

from google.cloud import pubsub_v1

from app.config import Settings
from app.domain.models import generate_event_id, get_current_ist_time

logger = logging.getLogger("pramaan")


class InMemoryEventBus:
    """In-memory event bus for local development and unit testing."""

    def __init__(self):
        self.events: list[dict[str, Any]] = []

    def publish(
        self,
        topic: str,
        event_type: str,
        company_id: str,
        intent_id: str | None,
        actor: dict[str, str],
        data: dict[str, Any],
    ) -> str:
        event_id = generate_event_id()
        occurred_at = get_current_ist_time()

        envelope = {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "company_id": company_id,
            "intent_id": intent_id,
            "actor": actor,
            "data": data,
        }
        self.events.append(envelope)
        logger.info(
            f"Event published to in-memory bus: {event_type} (topic: {topic}, id: {event_id})"
        )
        return event_id


class PubSubEventBus:
    """Cloud Pub/Sub publisher for dev, demo, and production."""

    def __init__(self, settings: Settings):
        self.project_id = settings.GCP_PROJECT
        self.publisher = pubsub_v1.PublisherClient()

    def publish(
        self,
        topic: str,
        event_type: str,
        company_id: str,
        intent_id: str | None,
        actor: dict[str, str],
        data: dict[str, Any],
    ) -> str:
        event_id = generate_event_id()
        occurred_at = get_current_ist_time()

        envelope = {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "company_id": company_id,
            "intent_id": intent_id,
            "actor": actor,
            "data": data,
        }

        topic_path = self.publisher.topic_path(self.project_id, topic)
        payload = json.dumps(envelope, ensure_ascii=False).encode("utf-8")

        future = self.publisher.publish(topic_path, payload)
        future.result(timeout=10)

        logger.info(
            f"Event published to Pub/Sub: {event_type} (topic: {topic_path}, id: {event_id})"
        )
        return event_id


def get_event_bus(settings: Settings):
    if settings.ENV == "local":
        return InMemoryEventBus()
    return PubSubEventBus(settings)
