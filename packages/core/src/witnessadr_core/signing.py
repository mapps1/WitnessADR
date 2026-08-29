"""Ed25519 key generation, signing, and signature verification."""

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 keypair.

    Returns:
        (private_key_bytes, public_key_bytes) — raw 32-byte keys.
        Store private_key_bytes securely; distribute public_key_bytes to auditors.
    """
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_bytes, public_bytes


def sign_hash(entry_hash: str, private_key_bytes: bytes) -> str:
    """Sign an entry hash with an Ed25519 private key.

    Args:
        entry_hash: The "sha256:<hex>" entry hash string to sign.
        private_key_bytes: Raw 32-byte Ed25519 private key.

    Returns:
        Signature as "ed25519:<base64>" string.
    """
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    sig_bytes = private_key.sign(entry_hash.encode("utf-8"))
    return f"ed25519:{base64.b64encode(sig_bytes).decode('ascii')}"


def verify_signature(entry_hash: str, signature: str, public_key_bytes: bytes) -> bool:
    """Verify an Ed25519 signature over an entry hash.

    Args:
        entry_hash: The "sha256:<hex>" string that was signed.
        signature: The "ed25519:<base64>" signature to verify.
        public_key_bytes: Raw 32-byte Ed25519 public key.

    Returns:
        True if the signature is valid, False otherwise.
        Never raises — invalid or malformed signatures return False.
    """
    if not signature.startswith("ed25519:"):
        return False
    try:
        sig_bytes = base64.b64decode(signature[len("ed25519:"):])
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(sig_bytes, entry_hash.encode("utf-8"))
        return True
    except Exception:
        return False
