"""Tests for redaction implementations."""

import json

from witnessadr_core.redaction import HashOnlyRedactor, Redactor, RegexPIIRedactor

_SAMPLE_CONTEXT = {
    "user_message": "My email is alice@example.com and my phone is 555-867-5309.",
    "system_prompt": "You are a helpful assistant.",
    "conversation_history": [{"role": "user", "content": "Hello"}],
}


class TestHashOnlyRedactor:
    def setup_method(self):
        self.redactor = HashOnlyRedactor()

    def test_implements_protocol(self):
        assert isinstance(self.redactor, Redactor)

    def test_returns_empty_dict_for_stored_context(self):
        stored, _ = self.redactor.redact(_SAMPLE_CONTEXT)
        assert stored == {}

    def test_returns_sha256_hash(self):
        _, h = self.redactor.redact(_SAMPLE_CONTEXT)
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64

    def test_never_leaks_raw_content(self):
        stored, _ = self.redactor.redact(_SAMPLE_CONTEXT)
        # The stored dict must not contain any substring from the raw input
        stored_str = json.dumps(stored)
        assert "alice@example.com" not in stored_str
        assert "555-867-5309" not in stored_str
        assert "conversation_history" not in stored_str

    def test_hash_is_deterministic(self):
        _, h1 = self.redactor.redact(_SAMPLE_CONTEXT)
        _, h2 = self.redactor.redact(_SAMPLE_CONTEXT)
        assert h1 == h2

    def test_different_context_different_hash(self):
        _, h1 = self.redactor.redact({"key": "value1"})
        _, h2 = self.redactor.redact({"key": "value2"})
        assert h1 != h2


class TestRegexPIIRedactor:
    def setup_method(self):
        self.redactor = RegexPIIRedactor()

    def test_implements_protocol(self):
        assert isinstance(self.redactor, Redactor)

    def test_email_redacted(self):
        context = {"message": "Contact alice@example.com for details."}
        stored, _ = self.redactor.redact(context)
        stored_str = json.dumps(stored)
        assert "alice@example.com" not in stored_str
        assert "[REDACTED_EMAIL]" in stored_str

    def test_phone_redacted(self):
        context = {"message": "Call me at 555-867-5309 tomorrow."}
        stored, _ = self.redactor.redact(context)
        stored_str = json.dumps(stored)
        assert "555-867-5309" not in stored_str
        assert "[REDACTED_PHONE]" in stored_str

    def test_non_pii_text_preserved(self):
        context = {"message": "The meeting is at 3pm in conference room B."}
        stored, _ = self.redactor.redact(context)
        stored_str = json.dumps(stored)
        assert "conference room B" in stored_str

    def test_hash_computed_from_original_not_redacted(self):
        """Hash must reflect the ORIGINAL content, not the redacted version."""
        context = {"message": "Email: bob@test.com"}
        stored, h_with_pii = self.redactor.redact(context)

        # Hash of the original context (unredacted) via HashOnlyRedactor
        from witnessadr_core.redaction import HashOnlyRedactor
        _, h_original = HashOnlyRedactor().redact(context)

        assert h_with_pii == h_original

    def test_ssn_redacted(self):
        context = {"message": "SSN: 123-45-6789"}
        stored, _ = self.redactor.redact(context)
        stored_str = json.dumps(stored)
        assert "123-45-6789" not in stored_str
        assert "[REDACTED_SSN]" in stored_str

    def test_multiple_pii_types_all_redacted(self):
        stored, _ = self.redactor.redact(_SAMPLE_CONTEXT)
        stored_str = json.dumps(stored)
        assert "alice@example.com" not in stored_str
        assert "555-867-5309" not in stored_str
