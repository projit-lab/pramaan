import hashlib
import json
from pathlib import Path

import pytest

from app.domain.canonical import canonical_bytes


def find_vectors_file() -> Path:
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    candidates = [
        repo_root / "contracts" / "canonical" / "vectors.json",
        Path("contracts/canonical/vectors.json"),
        Path("../contracts/canonical/vectors.json"),
        Path("../../contracts/canonical/vectors.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"contracts/canonical/vectors.json not found in {candidates}")


def test_shared_vectors():
    vectors_path = find_vectors_file()
    with open(vectors_path, "r", encoding="utf-8") as f:
        vectors = json.load(f)

    assert len(vectors) > 0, "Vectors list should not be empty"

    for vec in vectors:
        name = vec["name"]
        payment = vec["payment"]
        expected_canonical = vec["canonical"]
        expected_utf8_bytes = vec["canonical_utf8_bytes"]
        expected_sha256 = vec["sha256"]

        actual_bytes = canonical_bytes(payment)
        actual_bytes_len = len(actual_bytes)
        actual_sha256 = hashlib.sha256(actual_bytes).hexdigest()

        expected_bytes = expected_canonical.encode("utf-8")

        print(f"Vector: {name}")
        assert actual_bytes == expected_bytes, f"Canonical bytes mismatch for {name}"
        assert actual_bytes_len == expected_utf8_bytes, f"Byte length mismatch for {name}"
        assert actual_sha256 == expected_sha256, f"SHA-256 mismatch for {name}"


def test_type_error_on_non_str():
    with pytest.raises(TypeError):
        canonical_bytes({"amount": 100})  # type: ignore

    with pytest.raises(TypeError):
        canonical_bytes({123: "val"})  # type: ignore
