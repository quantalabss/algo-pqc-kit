"""
falcon_vault.py
===============
Enterprise M-of-N Falcon-1024 threshold vault — ARC-4 stateful smart contract.
Features: Arbitrary Transactions & Dynamic Membership.
"""

from algopy import (
    ARC4Contract,
    Asset,
    Application,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
)

# Proposal Types
# 0 = Payment
# 1 = Asset Transfer
# 2 = App Call
# 3 = Add Signer
# 4 = Remove Signer

class Proposal(arc4.Struct):
    proposal_type: arc4.UInt8
    recipient: arc4.Address
    amount_or_id: arc4.UInt64
    payload: arc4.DynamicBytes
    approval_count: arc4.UInt64
    executed: arc4.Bool

class ProposalCreated(arc4.Struct):
    proposal_id: arc4.UInt64
    proposal_type: arc4.UInt8

class SignatureSubmitted(arc4.Struct):
    proposal_id: arc4.UInt64
    signer_index: arc4.UInt64

class VaultExecuted(arc4.Struct):
    proposal_id: arc4.UInt64

class FalconVault(ARC4Contract):
    def __init__(self) -> None:
        self.threshold = GlobalState(UInt64)
        self.num_signers = GlobalState(UInt64)
        self.proposal_count = GlobalState(UInt64)

    @arc4.abimethod(allow_actions=["NoOp"], create="require")
    def create(self, threshold: UInt64, num_signers: UInt64) -> None:
        assert threshold <= num_signers, "Threshold > signer count"
        assert threshold >= UInt64(1), "Threshold must be >= 1"
        assert num_signers >= UInt64(1), "Vault requires at least 1 member"
        
        self.threshold.value = threshold
        self.num_signers.value = num_signers
        self.proposal_count.value = UInt64(0)

    @arc4.abimethod
    def add_signer_init(self, index: UInt64, public_key: arc4.DynamicBytes) -> None:
        """Initialize original signers. Only creator can call."""
        assert Txn.sender == Global.creator_address, "Only creator"
        assert index < self.num_signers.value, "Index out of bounds"
        box_key = b"pk_" + op.itob(index)
        op.Box.put(box_key, public_key.bytes)

    @arc4.abimethod
    def propose_transaction(
        self, 
        prop_type: arc4.UInt8, 
        recipient: arc4.Address, 
        amount_or_id: UInt64, 
        payload: arc4.DynamicBytes
    ) -> UInt64:
        proposal_id = self.proposal_count.value
        self.proposal_count.value = proposal_id + UInt64(1)
        
        box_key = b"prop_" + op.itob(proposal_id)
        
        prop = Proposal(
            proposal_type=prop_type,
            recipient=recipient,
            amount_or_id=arc4.UInt64(amount_or_id),
            payload=payload.copy(),
            approval_count=arc4.UInt64(0),
            executed=arc4.Bool(False)
        )
        op.Box.put(box_key, prop.bytes)
        
        arc4.emit(ProposalCreated(
            proposal_id=arc4.UInt64(proposal_id),
            proposal_type=prop_type
        ))
        return proposal_id

    @arc4.abimethod
    def submit_signature(
        self,
        proposal_id: UInt64,
        signer_index: UInt64,
        signature: arc4.DynamicBytes
    ) -> None:
        assert signer_index < self.num_signers.value, "Invalid signer"
        
        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "Proposal does not exist"
        
        prop = Proposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Already executed"

        sig_key = b"sig_" + op.itob(proposal_id) + b"_" + op.itob(signer_index)
        sig_data, sig_exists = op.Box.get(sig_key)
        assert not sig_exists, "Already approved"

        pk_key = b"pk_" + op.itob(signer_index)
        pubkey, pk_exists = op.Box.get(pk_key)
        assert pk_exists, "Signer key missing"

        # message payload
        message = (
            op.itob(proposal_id) 
            + op.itob(prop.proposal_type.native)
            + prop.recipient.bytes 
            + op.itob(prop.amount_or_id.native)
            + prop.payload.bytes
        )
        assert op.falcon_verify(message, signature.bytes, pubkey), "Invalid signature"

        op.Box.put(sig_key, Bytes(b"1"))

        new_prop = Proposal(
            proposal_type=prop.proposal_type,
            recipient=prop.recipient,
            amount_or_id=prop.amount_or_id,
            payload=prop.payload.copy(),
            approval_count=arc4.UInt64(prop.approval_count.native + 1),
            executed=prop.executed
        )
        op.Box.put(prop_key, new_prop.bytes)
        
        arc4.emit(SignatureSubmitted(
            proposal_id=arc4.UInt64(proposal_id),
            signer_index=arc4.UInt64(signer_index)
        ))

    @arc4.abimethod
    def execute_proposal(self, proposal_id: UInt64) -> None:
        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "No proposal"
        
        prop = Proposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Executed"
        assert prop.approval_count.native >= self.threshold.value, "No quorum"

        # CEI Pattern
        new_prop = Proposal(
            proposal_type=prop.proposal_type,
            recipient=prop.recipient,
            amount_or_id=prop.amount_or_id,
            payload=prop.payload.copy(),
            approval_count=prop.approval_count,
            executed=arc4.Bool(True)
        )
        op.Box.put(prop_key, new_prop.bytes)
        
        arc4.emit(VaultExecuted(proposal_id=arc4.UInt64(proposal_id)))

        ptype = prop.proposal_type.native
        if ptype == UInt64(0):
            # Payment
            itxn.Payment(
                receiver=prop.recipient.native,
                amount=prop.amount_or_id.native,
                fee=Global.min_txn_fee,
            ).submit()
        elif ptype == UInt64(1):
            # Asset Transfer
            itxn.AssetTransfer(
                asset_receiver=prop.recipient.native,
                asset_amount=prop.amount_or_id.native,
                xfer_asset=Asset(op.btoi(prop.payload.bytes)), 
                fee=Global.min_txn_fee,
            ).submit()
        elif ptype == UInt64(2):
            # App Call
            itxn.ApplicationCall(
                app_id=Application(prop.amount_or_id.native),
                app_args=(prop.payload.bytes,),
                fee=Global.min_txn_fee,
            ).submit()
        elif ptype == UInt64(3):
            # Add Signer
            new_idx = self.num_signers.value
            self.num_signers.value = new_idx + UInt64(1)
            new_pk_key = b"pk_" + op.itob(new_idx)
            op.Box.put(new_pk_key, prop.payload.bytes)
        elif ptype == UInt64(4):
            # Remove Signer
            idx_to_remove = prop.amount_or_id.native
            assert idx_to_remove < self.num_signers.value, "Bad index"
            pk_key = b"pk_" + op.itob(idx_to_remove)
            del1 = op.Box.delete(pk_key)
            
            last_idx = self.num_signers.value - UInt64(1)
            if idx_to_remove != last_idx:
                last_pk_key = b"pk_" + op.itob(last_idx)
                last_pk, last_pk_exists = op.Box.get(last_pk_key)
                assert last_pk_exists
                op.Box.put(pk_key, last_pk)
                del2 = op.Box.delete(last_pk_key)
            self.num_signers.value = last_idx
            
            if self.threshold.value > self.num_signers.value:
                self.threshold.value = self.num_signers.value
