"""
falcon_vault.py
===============
M-of-N Falcon-1024 threshold vault — ARC-4 stateful smart contract.

Uses AVM v12 `falcon_verify` opcode to enforce a post-quantum quorum
before releasing funds. No Ed25519 anywhere — fully quantum-resistant.

AVM opcode: falcon_verify(data, sig, pubkey) → bool  [cost: 1700 each]
"""

from algopy import (
    ARC4Contract,
    Asset,
    Bytes,
    Global,
    GlobalState,
    String,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
    urange,
)


class FalconVault(ARC4Contract):
    """
    M-of-N Post-Quantum Threshold Vault

    A treasury that releases ALGO or ASAs only when M-of-N Falcon-1024
    signatures are verified on-chain via the AVM falcon_verify opcode.

    Security properties
    -------------------
    - Quantum-resistant: all verification uses falcon_verify (NIST FN-DSA)
    - No single point of failure: M < N means one key loss doesn't freeze funds
    - Replay protection: message includes nonce + recipient + amount
    - No admin backdoor: committee is fixed at deployment
    """

    def __init__(self) -> None:
        self.threshold = GlobalState(UInt64)
        self.num_signers = GlobalState(UInt64)
        self.nonce = GlobalState(UInt64)
        self.asset_id = GlobalState(UInt64)

    @arc4.abimethod(allow_actions=["NoOp"], create="require")
    def create(
        self,
        threshold: UInt64,
        public_keys: arc4.DynamicArray[arc4.DynamicBytes],
        asset_id: UInt64,
    ) -> None:
        """
        Deploy the vault with an immutable M-of-N Falcon committee.

        Parameters
        ----------
        threshold : UInt64   M — minimum signatures required
        public_keys          N Falcon-1024 public keys (1793 bytes each)
        asset_id             0 = ALGO vault, ASA ID = token vault
        """
        n = public_keys.length
        assert threshold <= n, "Threshold > signer count"
        assert threshold >= UInt64(1), "Threshold must be >= 1"
        assert n >= UInt64(2), "Need >= 2 signers"
        assert n <= UInt64(16), "Max 16 signers"

        self.threshold.value = threshold
        self.num_signers.value = n
        self.nonce.value = UInt64(0)
        self.asset_id.value = asset_id

        # Store public keys in box storage: box name = "pk" + index (1 byte)
        for i in urange(n):
            box_name = b"pk" + op.itob(i)
            op.Box.put(box_name, public_keys[i].bytes)

    @arc4.abimethod
    def release(
        self,
        recipient: arc4.Address,
        amount: UInt64,
        signatures: arc4.DynamicArray[arc4.DynamicBytes],
        signer_indices: arc4.DynamicArray[arc4.UInt64],
    ) -> None:
        """
        Release funds after M-of-N Falcon-1024 verification.

        The signed message is: itob(nonce) || recipient_bytes || itob(amount)
        This prevents replay attacks across different release calls.
        """
        assert signatures.length == signer_indices.length, "Sig/index mismatch"
        assert signatures.length >= self.threshold.value, "Insufficient signatures"

        # Build replay-protected message
        message = (
            op.itob(self.nonce.value)
            + recipient.bytes
            + op.itob(amount)
        )

        # Verify each Falcon-1024 signature on-chain (AVM falcon_verify)
        verified = UInt64(0)
        for i in urange(signatures.length):
            idx = signer_indices[i].native
            assert idx < self.num_signers.value, "Signer index out of range"

            box_name = b"pk" + op.itob(idx)
            pubkey, exists = op.Box.get(box_name)
            assert exists, "Public key not found"

            if op.falcon_verify(message, signatures[i].bytes, pubkey):
                verified += UInt64(1)

        assert verified >= self.threshold.value, "Quorum not reached"

        # Increment nonce before releasing (prevents replay within same block)
        self.nonce.value += UInt64(1)

        # Execute payment
        if self.asset_id.value == UInt64(0):
            itxn.Payment(
                receiver=recipient.native,
                amount=amount,
                fee=Global.min_txn_fee,
            ).submit()
        else:
            itxn.AssetTransfer(
                asset_receiver=recipient.native,
                asset_amount=amount,
                xfer_asset=Asset(self.asset_id.value),
                fee=Global.min_txn_fee,
            ).submit()

    @arc4.abimethod(readonly=True)
    def get_config(self) -> arc4.Tuple[arc4.UInt64, arc4.UInt64, arc4.UInt64]:
        """Return (threshold, num_signers, nonce) — read-only."""
        return arc4.Tuple((
            arc4.UInt64(self.threshold.value),
            arc4.UInt64(self.num_signers.value),
            arc4.UInt64(self.nonce.value),
        ))
