"""Tests for Ed25519 keypair generation, signing, and verification."""

from witnessadr_core.signing import generate_keypair, sign_hash, verify_signature

_SAMPLE_HASH = "sha256:" + "a" * 64


def test_generate_keypair_returns_32_byte_keys():
    private_key, public_key = generate_keypair()
    assert len(private_key) == 32
    assert len(public_key) == 32


def test_generate_keypair_unique_each_call():
    priv1, pub1 = generate_keypair()
    priv2, pub2 = generate_keypair()
    assert priv1 != priv2
    assert pub1 != pub2


def test_sign_hash_format():
    private_key, _ = generate_keypair()
    sig = sign_hash(_SAMPLE_HASH, private_key)
    assert sig.startswith("ed25519:")
    b64_part = sig[len("ed25519:"):]
    assert len(b64_part) > 0


def test_verify_signature_valid():
    private_key, public_key = generate_keypair()
    sig = sign_hash(_SAMPLE_HASH, private_key)
    assert verify_signature(_SAMPLE_HASH, sig, public_key) is True


def test_verify_signature_wrong_public_key():
    private_key, _ = generate_keypair()
    _, different_public = generate_keypair()
    sig = sign_hash(_SAMPLE_HASH, private_key)
    assert verify_signature(_SAMPLE_HASH, sig, different_public) is False


def test_verify_signature_tampered_hash():
    private_key, public_key = generate_keypair()
    sig = sign_hash(_SAMPLE_HASH, private_key)
    tampered_hash = "sha256:" + "b" * 64
    assert verify_signature(tampered_hash, sig, public_key) is False


def test_verify_signature_malformed_sig_returns_false():
    _, public_key = generate_keypair()
    assert verify_signature(_SAMPLE_HASH, "not-a-sig", public_key) is False
    assert verify_signature(_SAMPLE_HASH, "ed25519:!!!invalid_base64!!!", public_key) is False


def test_sign_deterministic_for_same_inputs():
    """Ed25519 signing is deterministic (RFC 8032)."""
    private_key, _ = generate_keypair()
    sig1 = sign_hash(_SAMPLE_HASH, private_key)
    sig2 = sign_hash(_SAMPLE_HASH, private_key)
    assert sig1 == sig2
