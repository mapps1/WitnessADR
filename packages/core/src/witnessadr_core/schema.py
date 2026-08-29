"""JSON Schema validation for ADR entries."""

import importlib.resources
import json
from functools import lru_cache

from jsonschema import ValidationError  # re-exported for callers
from jsonschema.validators import validator_for

__all__ = ["validate_entry", "ValidationError"]


@lru_cache(maxsize=1)
def _load_schema() -> dict:
    ref = importlib.resources.files("witnessadr_core.schemas").joinpath("adr-schema-v1.json")
    return json.loads(ref.read_text(encoding="utf-8"))


def validate_entry(entry: dict) -> None:
    """Validate an ADR entry dict against the v1 JSON Schema.

    Raises:
        jsonschema.ValidationError: with the failing field path in the message.
    """
    schema = _load_schema()
    validator_cls = validator_for(schema)
    validator = validator_cls(schema)

    errors = sorted(validator.iter_errors(entry), key=lambda e: len(e.absolute_path))
    if errors:
        # Surface the most specific (deepest) error first
        best = errors[-1]
        path = " -> ".join(str(p) for p in best.absolute_path) or "(root)"
        raise ValidationError(
            f"Invalid ADR entry at '{path}': {best.message}",
            path=best.absolute_path,
            schema_path=best.absolute_schema_path,
        )
