"""
pqc_dao.py
==========
Post-Quantum DAO Governance Contract — ARC-4 stateful smart contract.

Architecture Update (v2)
------------------------
Implements a Multi-Transaction Session Pattern using Box Storage.
Bypasses the 2048-byte AVM limit to enable infinite M-of-N sizes.
"""

from algopy import (
    ARC4Contract,
    Bytes,
    Global,
    GlobalState,
    String,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
)

class DaoProposal(arc4.Struct):
    recipient: arc4.Address
    amount: arc4.UInt64
    desc_hash: arc4.DynamicBytes
    approval_count: arc4.UInt64
    executed: arc4.Bool

class PQCDao(ARC4Contract):
    def __init__(self) -> None:
        self.dao_name = GlobalState(String)
        self.threshold = GlobalState(UInt64)
        self.num_members = GlobalState(UInt64)
        self.proposal_count = GlobalState(UInt64)

    @arc4.abimethod(allow_actions=["NoOp"], create="require")
    def create(
        self,
        dao_name: String,
        threshold: UInt64,
        num_members: UInt64,
    ) -> None:
        assert threshold >= UInt64(1), "Threshold must be >= 1"
        assert threshold <= num_members, "Threshold cannot exceed member count"
        assert num_members >= UInt64(1), "DAO requires at least 1 member"

        self.dao_name.value = dao_name
        self.threshold.value = threshold
        self.num_members.value = num_members
        self.proposal_count.value = UInt64(0)

    @arc4.abimethod
    def add_member(self, index: UInt64, public_key: arc4.DynamicBytes) -> None:
        assert Txn.sender == Global.creator_address, "Only creator can initialize"
        assert index < self.num_members.value, "Index out of bounds"
        box_key = b"pk_" + op.itob(index)
        op.Box.put(box_key, public_key.bytes)

    @arc4.abimethod
    def submit_proposal(
        self,
        description: String,
        recipient: arc4.Address,
        amount: UInt64,
    ) -> UInt64:
        proposal_id = self.proposal_count.value
        self.proposal_count.value = proposal_id + UInt64(1)

        desc_hash = op.sha256(description.bytes)
        box_key = b"prop_" + op.itob(proposal_id)
        
        prop = DaoProposal(
            recipient=recipient,
            amount=arc4.UInt64(amount),
            desc_hash=arc4.DynamicBytes(desc_hash),
            approval_count=arc4.UInt64(0),
            executed=arc4.Bool(False)
        )
        op.Box.put(box_key, prop.bytes)
        return proposal_id

    @arc4.abimethod
    def submit_vote(
        self,
        proposal_id: UInt64,
        signer_index: UInt64,
        signature: arc4.DynamicBytes
    ) -> None:
        assert signer_index < self.num_members.value, "Invalid signer index"

        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "Proposal does not exist"
        
        prop = DaoProposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Already executed"

        sig_key = b"sig_" + op.itob(proposal_id) + b"_" + op.itob(signer_index)
        sig_data, sig_exists = op.Box.get(sig_key)
        assert not sig_exists, "Signer already voted"

        pk_key = b"pk_" + op.itob(signer_index)
        pubkey, pk_exists = op.Box.get(pk_key)
        assert pk_exists, "Signer public key not initialized"

        message = (
            op.itob(proposal_id)
            + prop.recipient.bytes
            + op.itob(prop.amount.native)
            + prop.desc_hash.bytes
        )
        assert op.falcon_verify(message, signature.bytes, pubkey), "Invalid Falcon-1024 signature"

        op.Box.put(sig_key, Bytes(b"1"))

        new_prop = DaoProposal(
            recipient=prop.recipient,
            amount=prop.amount,
            desc_hash=prop.desc_hash.copy(),
            approval_count=arc4.UInt64(prop.approval_count.native + 1),
            executed=prop.executed
        )
        op.Box.put(prop_key, new_prop.bytes)

    @arc4.abimethod
    def execute_proposal(self, proposal_id: UInt64) -> None:
        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "Proposal does not exist"
        
        prop = DaoProposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Already executed"
        assert prop.approval_count.native >= self.threshold.value, "Quorum not reached"

        new_prop = DaoProposal(
            recipient=prop.recipient,
            amount=prop.amount,
            desc_hash=prop.desc_hash.copy(),
            approval_count=prop.approval_count,
            executed=arc4.Bool(True)
        )
        op.Box.put(prop_key, new_prop.bytes)

        itxn.Payment(
            receiver=prop.recipient.native,
            amount=prop.amount.native,
            fee=Global.min_txn_fee,
            note=b"algo-pqc-kit:dao:proposal:" + op.itob(proposal_id),
        ).submit()

    @arc4.abimethod(readonly=True)
    def get_proposal_count(self) -> UInt64:
        return self.proposal_count.value

    @arc4.abimethod(readonly=True)
    def get_threshold(self) -> UInt64:
        return self.threshold.value

    @arc4.abimethod(readonly=True)
    def get_member_count(self) -> UInt64:
        return self.num_members.value
