"""Tests for hash chain verification."""



from witnessadr_core.signing import generate_keypair
from witnessadr_core.verify import verify_chain

from .conftest import build_chain


def test_empty_chain_is_valid():
    result = verify_chain([])
    assert result.is_valid is True
    assert result.total_entries == 0
    assert result.first_broken_index is None


def test_single_entry_chain_valid():
    chain = build_chain(1)
    result = verify_chain(chain)
    assert result.is_valid is True
    assert result.total_entries == 1


def test_valid_5_entry_chain():
    chain = build_chain(5)
    result = verify_chain(chain)
    assert result.is_valid is True
    assert result.total_entries == 5


def test_valid_signed_5_entry_chain(keypair):
    private_key, public_key = keypair
    chain = build_chain(5, private_key_bytes=private_key)
    result = verify_chain(chain, public_key_bytes=public_key)
    assert result.is_valid is True


def test_mutation_at_entry_3_detected_at_index_3():
    """Core tamper-detection test: mutating entry 3 must be caught at index 3, not 4 or 5."""
    chain = build_chain(5)
    # Mutate content of entry at index 3 WITHOUT updating its entry_hash
    chain[3] = dict(chain[3])
    chain[3]["outcome"] = "TAMPERED — this value was changed after recording"

    result = verify_chain(chain)
    assert result.is_valid is False
    assert result.first_broken_index == 3, (
        f"Expected failure at index 3, got {result.first_broken_index}. "
        f"Reason: {result.broken_reason}"
    )


def test_mutation_at_entry_0_detected_at_index_0():
    chain = build_chain(5)
    chain[0] = dict(chain[0])
    chain[0]["agent_id"] = "TAMPERED"
    result = verify_chain(chain)
    assert result.is_valid is False
    assert result.first_broken_index == 0


def test_mutation_at_last_entry_detected():
    chain = build_chain(5)
    chain[4] = dict(chain[4])
    chain[4]["outcome"] = "TAMPERED"
    result = verify_chain(chain)
    assert result.is_valid is False
    assert result.first_broken_index == 4


def test_sequence_number_gap_caught():
    chain = build_chain(5)
    # Introduce a gap: sequence 0,1,2,4,5 (skip 3)
    chain[3] = dict(chain[3])
    chain[3]["sequence_number"] = 4
    result = verify_chain(chain)
    assert result.is_valid is False
    assert result.first_broken_index == 3
    assert "sequence_number gap" in result.broken_reason


def test_sequence_number_out_of_order_caught():
    chain = build_chain(5)
    chain[2] = dict(chain[2])
    chain[2]["sequence_number"] = 99
    result = verify_chain(chain)
    assert result.is_valid is False
    assert result.first_broken_index == 2


def test_wrong_public_key_fails_signature_verification(keypair):
    private_key, _ = keypair
    _, different_public = generate_keypair()
    chain = build_chain(5, private_key_bytes=private_key)
    result = verify_chain(chain, public_key_bytes=different_public)
    assert result.is_valid is False
    assert result.first_broken_index == 0
    assert "signature" in result.broken_reason.lower()


def test_missing_signature_when_key_provided(keypair):
    _, public_key = keypair
    chain = build_chain(5)  # unsigned chain
    result = verify_chain(chain, public_key_bytes=public_key)
    assert result.is_valid is False
    assert result.first_broken_index == 0
    assert "missing signature" in result.broken_reason


def test_verify_without_public_key_ignores_signatures(keypair):
    private_key, _ = keypair
    chain = build_chain(5, private_key_bytes=private_key)
    # Verify without a key — signatures are present but not checked
    result = verify_chain(chain, public_key_bytes=None)
    assert result.is_valid is True


def test_tampered_prev_hash_caught():
    chain = build_chain(5)
    chain[2] = dict(chain[2])
    chain[2]["prev_hash"] = "sha256:" + "0" * 64  # wrong prev_hash
    result = verify_chain(chain)
    assert result.is_valid is False
    assert result.first_broken_index == 2


def test_verification_result_str_pass():
    chain = build_chain(3)
    result = verify_chain(chain)
    assert "PASS" in str(result)
    assert "3 entries" in str(result)


def test_verification_result_str_fail():
    chain = build_chain(3)
    chain[1] = dict(chain[1])
    chain[1]["outcome"] = "tampered"
    result = verify_chain(chain)
    assert "FAIL" in str(result)
    assert "index 1" in str(result)
