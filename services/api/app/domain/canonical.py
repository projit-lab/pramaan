import json
import unicodedata


def canonical_bytes(fields: dict[str, str]) -> bytes:
    """NFC-normalises keys and values and serializes to canonical JSON bytes.

    Raises:
        TypeError: If any key or value is not a str.
    """
    normalized: dict[str, str] = {}
    for k, v in fields.items():
        if not isinstance(k, str):
            raise TypeError(f"Key {k!r} is not a str (type: {type(k).__name__})")
        if not isinstance(v, str):
            raise TypeError(f"Value for key {k!r} is not a str (type: {type(v).__name__})")

        norm_k = unicodedata.normalize("NFC", k)
        norm_v = unicodedata.normalize("NFC", v)
        normalized[norm_k] = norm_v

    json_str = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return json_str.encode("utf-8")
