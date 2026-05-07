"""
test_multisig.py — Unit tests for FalconMultisig
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.account import FalconAccount, FALCON_SIG_SIZE
from sdk.multisig import FalconMultisig, SigningSession


def make_committee(M: int, N: int):
    accounts = [FalconAccount.generate() for _ in range(N)]
    pks = [a.public_key for a in accounts]
    committee = FalconMultisig.create(threshold=M, members=pks)
    return accounts, committee


class TestFalconMultisig:

    def test_create_2_of_3(self):
        _, c = make_committee(2, 3)
        assert c.threshold == 2
        assert c.total_signers == 3

    def test_create_3_of_5(self):
        _, c = make_committee(3, 5)
        assert c.threshold == 3
        assert c.total_signers == 5

    def test_committee_id_deterministic(self):
        accs, c1 = make_committee(2, 3)
        pks = [a.public_key for a in accs]
        c2 = FalconMultisig.create(threshold=2, members=pks)
        assert c1.committee_id == c2.committee_id

    def test_address_has_ms_prefix(self):
        _, c = make_committee(2, 3)
        assert c.address.startswith("ms:")

    def test_invalid_threshold_zero(self):
        accs = [FalconAccount.generate() for _ in range(3)]
        pks = [a.public_key for a in accs]
        with pytest.raises(AssertionError):
            FalconMultisig.create(threshold=0, members=pks)

    def test_invalid_threshold_exceeds_n(self):
        accs = [FalconAccount.generate() for _ in range(3)]
        pks = [a.public_key for a in accs]
        with pytest.raises(AssertionError):
            FalconMultisig.create(threshold=4, members=pks)

    def test_session_collects_signatures(self):
        accs, committee = make_committee(2, 3)
        message = b"test_release_message_12345678901"
        session = committee.start_session(message)
        # Add 2 mock signatures (dev mode — no real Falcon verification)
        mock_sig = b"\x00" * FALCON_SIG_SIZE
        session._signatures[0] = mock_sig
        session._signatures[1] = mock_sig
        assert session.is_complete

    def test_session_not_complete_below_threshold(self):
        _, committee = make_committee(3, 5)
        message = b"test_release_message_12345678901"
        session = committee.start_session(message)
        mock_sig = b"\x00" * FALCON_SIG_SIZE
        session._signatures[0] = mock_sig
        session._signatures[1] = mock_sig
        assert not session.is_complete
        assert session.collected == 2

    def test_finalize_raises_below_threshold(self):
        _, committee = make_committee(3, 5)
        session = committee.start_session(b"msg")
        with pytest.raises(RuntimeError, match="Need 3"):
            session.finalize()

    def test_finalize_returns_payload(self):
        _, committee = make_committee(2, 3)
        session = committee.start_session(b"msg")
        mock_sig = b"\x01" * FALCON_SIG_SIZE
        session._signatures[0] = mock_sig
        session._signatures[2] = mock_sig
        payload = session.finalize()
        assert payload.is_complete()
        assert payload.indices == [0, 2]
        assert len(payload.signatures) == 2

    def test_build_release_message_length(self):
        _, committee = make_committee(2, 3)
        msg = committee.build_release_message(
            nonce=0,
            recipient="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            amount=1_000_000,
        )
        # 8 (nonce) + 32 (addr) + 8 (amount) = 48
        assert len(msg) == 48

    def test_duplicate_index_raises(self):
        _, committee = make_committee(2, 3)
        session = committee.start_session(b"msg")
        mock_sig = b"\x00" * FALCON_SIG_SIZE
        session._signatures[0] = mock_sig
        with pytest.raises(ValueError, match="Duplicate"):
            session.add_signature(0, mock_sig)
