import json
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from app.config import Settings


class LocalJsonlLedger:
    """Local JSONL append-only ledger in services/api/.local/."""

    def __init__(self):
        self.ledger_dir = Path(__file__).resolve().parent.parent.parent / ".local"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.ledger_dir / "ledger.jsonl"

    def append_record(self, table_name: str, record: dict[str, Any]) -> None:
        entry = {
            "table": table_name,
            "record": record,
        }
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class BigQueryLedger:
    """BigQuery ledger adapter for pramaan_ledger dataset."""

    def __init__(self, settings: Settings):
        self.client = bigquery.Client(project=settings.GCP_PROJECT)
        self.dataset_id = f"{settings.GCP_PROJECT}.pramaan_ledger"

    def append_record(self, table_name: str, record: dict[str, Any]) -> None:
        table_id = f"{self.dataset_id}.{table_name}"
        errors = self.client.insert_rows_json(table_id, [record])
        if errors:
            raise RuntimeError(f"BigQuery insert failed for table {table_id}: {errors}")


def get_ledger(settings: Settings):
    if settings.ENV == "local":
        return LocalJsonlLedger()
    return BigQueryLedger(settings)
