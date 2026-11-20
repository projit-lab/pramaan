import os
from typing import Any

from google.cloud import firestore

from app.config import Settings


class InMemoryReadModel:
    """In-memory read model for local development and unit tests."""

    def __init__(self):
        self._store: dict[str, dict[str, dict[str, Any]]] = {}

    def set_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        if collection not in self._store:
            self._store[collection] = {}
        self._store[collection][doc_id] = dict(data)

    def update_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        if collection not in self._store:
            self._store[collection] = {}
        if doc_id not in self._store[collection]:
            self._store[collection][doc_id] = {}
        self._store[collection][doc_id].update(data)

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        return self._store.get(collection, {}).get(doc_id)


class FirestoreReadModel:
    """Firestore read model adapter writing camelCase fields per contracts/firestore.md."""

    def __init__(self, settings: Settings):
        if settings.FIRESTORE_EMULATOR_HOST:
            os.environ["FIRESTORE_EMULATOR_HOST"] = settings.FIRESTORE_EMULATOR_HOST

        self.client = firestore.Client(project=settings.GCP_PROJECT)

    def set_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        doc_ref = self.client.collection(collection).document(doc_id)
        doc_ref.set(data)

    def update_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        doc_ref = self.client.collection(collection).document(doc_id)
        doc_ref.update(data)

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        doc_ref = self.client.collection(collection).document(doc_id)
        snap = doc_ref.get()
        if snap.exists:
            return snap.to_dict()
        return None


def get_read_model(settings: Settings):
    if settings.ENV == "local":
        return InMemoryReadModel()
    return FirestoreReadModel(settings)
