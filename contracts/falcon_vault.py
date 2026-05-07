"""
falcon_vault.py
===============
M-of-N Falcon-1024 threshold vault — ARC-4 stateful smart contract.

Uses AVM v12 `falcon_verify` opcode to enforce a post-quantum quorum
before releasing funds. No Ed25519 anywhere — fully quantum-resistant.

Architecture Update (v2)
------------------------
Implements a Multi-Transaction Session Pattern to bypass the 2048-byte
ApplicationArgs limit. Public keys and signatures are aggregated sequentially
via Box Storage, enabling theoretically infinite M-of-N threshold sizes for
massive PQC public keys (1793B) and signatures (1220B).
"""

from algopy import (
    ARC4Contract,
    Asset,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
)

class Proposal(arc4.Struct):
    recipient: arc4.Address
    amount: arc4.UInt64
    approval_count: arc4.UInt64
    executed: arc4.Bool

class FalconVault(ARC4Contract):
    """
    M-of-N Post-Quantum Threshold Vault
    """

    def __init__(self) -> None:
        self.threshold = GlobalState(UInt64)
        self.num_signers = GlobalState(UInt64)
        self.asset_id = GlobalState(UInt64)
        self.proposal_count = GlobalState(UInt64)

    @arc4.abimethod(allow_actions=["NoOp"], create="require")
    def create(self, threshold: UInt64, num_signers: UInt64, asset_id: UInt64) -> None:
        assert threshold <= num_signers, "Threshold > signer count"
        assert threshold >= UInt64(1), "Threshold must be >= 1"
        assert num_signers >= UInt64(1), "Vault requires at least 1 member"
        
        self.threshold.value = threshold
        self.num_signers.value = num_signers
        self.asset_id.value = asset_id
        self.proposal_count.value = UInt64(0)

    @arc4.abimethod
    def add_signer(self, index: UInt64, public_key: arc4.DynamicBytes) -> None:
        """
        Sequentially add a 1793B Falcon-1024 public key into Box Storage.
        Bypasses the 2048B argument limit of the AVM.
        """
        assert Txn.sender == Global.creator_address, "Only creator can initialize"
        assert index < self.num_signers.value, "Index out of bounds"
        box_key = b"pk_" + op.itob(index)
        op.Box.put(box_key, public_key.bytes)

    @arc4.abimethod
    def propose_release(self, recipient: arc4.Address, amount: UInt64) -> UInt64:
        """Create a new payment proposal."""
        proposal_id = self.proposal_count.value
        self.proposal_count.value = proposal_id + UInt64(1)
        
        box_key = b"prop_" + op.itob(proposal_id)
        
        prop = Proposal(
            recipient=recipient,
            amount=arc4.UInt64(amount),
            approval_count=arc4.UInt64(0),
            executed=arc4.Bool(False)
        )
        op.Box.put(box_key, prop.bytes)
        return proposal_id

    @arc4.abimethod
    def submit_signature(
        self,
        proposal_id: UInt64,
        signer_index: UInt64,
        signature: arc4.DynamicBytes
    ) -> None:
        """
        Submit a single 1220B Falcon-1024 signature for a proposal.
        """
        assert signer_index < self.num_signers.value, "Invalid signer index"
        
        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "Proposal does not exist"
        
        prop = Proposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Already executed"

        sig_key = b"sig_" + op.itob(proposal_id) + b"_" + op.itob(signer_index)
        sig_data, sig_exists = op.Box.get(sig_key)
        assert not sig_exists, "Signer already approved"

        pk_key = b"pk_" + op.itob(signer_index)
        pubkey, pk_exists = op.Box.get(pk_key)
        assert pk_exists, "Signer public key not initialized"

        # payload: itob(proposal_id) || recipient bytes || itob(amount)
        message = op.itob(proposal_id) + prop.recipient.bytes + op.itob(prop.amount.native)
        assert op.falcon_verify(message, signature.bytes, pubkey), "Invalid Falcon-1024 signature"

        op.Box.put(sig_key, Bytes(b"1"))

        new_prop = Proposal(
            recipient=prop.recipient,
            amount=prop.amount,
            approval_count=arc4.UInt64(prop.approval_count.native + 1),
            executed=prop.executed
        )
        op.Box.put(prop_key, new_prop.bytes)

    @arc4.abimethod
    def execute_release(self, proposal_id: UInt64) -> None:
        """Execute the payment if threshold is met."""
        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "Proposal does not exist"
        
        prop = Proposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Already executed"
        assert prop.approval_count.native >= self.threshold.value, "Quorum not reached"

        new_prop = Proposal(
            recipient=prop.recipient,
            amount=prop.amount,
            approval_count=prop.approval_count,
            executed=arc4.Bool(True)
        )
        op.Box.put(prop_key, new_prop.bytes)

        if self.asset_id.value == UInt64(0):
            itxn.Payment(
                receiver=prop.recipient.native,
                amount=prop.amount.native,
                fee=Global.min_txn_fee,
            ).submit()
        else:
            itxn.AssetTransfer(
                asset_receiver=prop.recipient.native,
                asset_amount=prop.amount.native,
                xfer_asset=Asset(self.asset_id.value),
                fee=Global.min_txn_fee,
            ).submit()
