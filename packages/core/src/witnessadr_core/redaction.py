"""Pluggable redaction interface and built-in redactor implementations.

Use redactors to scrub or hash sensitive input context before it touches
storage. The default (HashOnlyRedactor) stores nothing — only the hash —
making it safe for regulated environments without any configuration.
"""

import hashlib
import json
import re
from typing import Protocol, runtime_checkable


@runtime_checkable
class Redactor(Protocol):
    """Protocol for pre-storage input context redaction.

    A Redactor takes a raw input context dict and returns:
    - A (possibly empty) dict safe to store in input_context_ref
    - A SHA-256 hash of the original, used as input_context_hash

    The hash is always computed over the original content, so the stored
    hash is still useful for auditing even when the content is not kept.
    """

    def redact(self, raw_context: dict) -> tuple[dict, str]:
        """Redact raw_context.

        Returns:
            (safe_to_store_dict, "sha256:<hex>" hash of original)
        """
        ...


class HashOnlyRedactor:
    """The safest default: store nothing, keep only the SHA-256 hash.

    Use this when you want tamper-evident proof that specific context
    existed at decision time without retaining the content at all.
    Suitable for all regulated environments.
    """

    def redact(self, raw_context: dict) -> tuple[dict, str]:
        canonical = json.dumps(
            raw_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        return {}, f"sha256:{digest}"


class RegexPIIRedactor:
    """Redact common PII patterns while keeping the rest of the context readable.

    Patterns scrubbed:
    - Email addresses  → [REDACTED_EMAIL]
    - US phone numbers → [REDACTED_PHONE]
    - SSN patterns     → [REDACTED_SSN]
    - Credit card-like → [REDACTED_CC]

    Use this when you need a readable-but-scrubbed context log. For maximum
    safety in regulated environments, prefer HashOnlyRedactor.
    """

    _EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
    _PHONE = re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    )
    _SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    _CC = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

    def redact(self, raw_context: dict) -> tuple[dict, str]:
        canonical = json.dumps(
            raw_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        redacted = self._EMAIL.sub("[REDACTED_EMAIL]", canonical)
        redacted = self._PHONE.sub("[REDACTED_PHONE]", redacted)
        redacted = self._SSN.sub("[REDACTED_SSN]", redacted)
        redacted = self._CC.sub("[REDACTED_CC]", redacted)

        try:
            redacted_dict = json.loads(redacted)
        except json.JSONDecodeError:
            # Regex replacement broke the JSON structure; fall back to hash-only
            redacted_dict = {}

        return redacted_dict, f"sha256:{digest}"
