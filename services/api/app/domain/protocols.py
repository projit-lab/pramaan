from typing import Any, Protocol


class MandateSigner(Protocol):
    def sign_mandate(self, canonical_mandate_bytes: bytes) -> tuple[bytes, str]:
        """Signs canonical mandate bytes using ECDSA P-256 with SHA-256.

        Returns:
            tuple[bytes, str]: (DER-encoded signature bytes, key_version_resource_or_id)
        """
        ...

    def get_public_key_pem(self) -> tuple[str, str]:
        """Returns the SubjectPublicKeyInfo PEM-encoded public key and key version."""
        ...


class EventBus(Protocol):
    def publish(
        self,
        topic: str,
        event_type: str,
        company_id: str,
        intent_id: str | None,
        actor: dict[str, str],
        data: dict[str, Any],
    ) -> str:
        """Publishes an event envelope according to contracts/events.md.

        Returns:
            str: event_id
        """
        ...


class ReadModel(Protocol):
    def set_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        """Writes or overwrites a document in the read model using camelCase fields."""
        ...

    def update_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        """Updates fields in a document in the read model."""
        ...

    def get_document(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Fetches a document from the read model."""
        ...


class Ledger(Protocol):
    def append_record(self, table_name: str, record: dict[str, Any]) -> None:
        """Appends an event record to the append-only ledger."""
        ...
