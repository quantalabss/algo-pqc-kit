"""
test_account.py — Unit tests for FalconAccount
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.account import FalconAccount, FALCON_PUBKEY_SIZE, FALCON_SIG_SIZE


class TestFalconAccount:

    def test_generate_returns_account(self):
        acc = FalconAccount.generate()
        assert acc is not None
        assert acc.public_key is not None
        assert acc.address is not None

    def test_public_key_size(self):
        acc = FalconAccount.generate()
        assert len(acc.public_key) == FALCON_PUBKEY_SIZE, (
            f"Expected {FALCON_PUBKEY_SIZE} bytes, got {len(acc.public_key)}"
        )

    def test_address_format(self):
        acc = FalconAccount.generate()
        # Algorand addresses are base32 encoded, 58 chars (no padding)
        assert len(acc.address) > 0
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in acc.address), (
            "Address must be base32"
        )

    def test_address_deterministic(self):
        """Same public key → same address."""
        acc1 = FalconAccount.generate()
        acc2 = FalconAccount(public_key=acc1.public_key, _private_key=acc1._private_key)
        assert acc1.address == acc2.address

    def test_lsig_program_not_empty(self):
        acc = FalconAccount.generate()
        assert len(acc.lsig_program) > FALCON_PUBKEY_SIZE  # program > key alone

    def test_sign_returns_bytes(self):
        acc = FalconAccount.generate()
        msg = b"test_transaction_id_32_bytes_xxx!"
        sig = acc.sign(msg)
        assert isinstance(sig, bytes)
        assert 0 < len(sig) <= FALCON_SIG_SIZE  # variable-length

    def test_two_accounts_different_addresses(self):
        acc1 = FalconAccount.generate()
        acc2 = FalconAccount.generate()
        assert acc1.address != acc2.address

    def test_to_dict_no_private_key(self):
        acc = FalconAccount.generate()
        d = acc.to_dict()
        assert "private_key" not in d
        assert "public_key" in d
        assert "address" in d
        assert "algorithm" in d
        assert d["algorithm"] == "falcon-1024"

    def test_save_and_load(self, tmp_path):
        acc = FalconAccount.generate()
        path = str(tmp_path / "test_key.json")
        acc.save(path)
        loaded = FalconAccount.load(path)
        assert loaded.address == acc.address
        assert loaded.public_key == acc.public_key
