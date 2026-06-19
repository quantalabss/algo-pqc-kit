"""
pqc_dao.py
==========
Enterprise Post-Quantum DAO Governance Contract.
Features: Voting Periods, Timelocks, Yes/No/Abstain votes.
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
    start_time: arc4.UInt64
    end_time: arc4.UInt64
    yes_votes: arc4.UInt64
    no_votes: arc4.UInt64
    executed: arc4.Bool

class DaoProposalCreated(arc4.Struct):
    proposal_id: arc4.UInt64
    end_time: arc4.UInt64

class DaoVoteSubmitted(arc4.Struct):
    proposal_id: arc4.UInt64
    signer_index: arc4.UInt64
    vote_type: arc4.UInt8

class DaoExecuted(arc4.Struct):
    proposal_id: arc4.UInt64

class PQCDao(ARC4Contract):
    def __init__(self) -> None:
        self.dao_name = GlobalState(String)
        self.threshold = GlobalState(UInt64)
        self.num_members = GlobalState(UInt64)
        self.proposal_count = GlobalState(UInt64)
        self.voting_period = GlobalState(UInt64)
        self.execution_delay = GlobalState(UInt64)

    @arc4.abimethod(allow_actions=["NoOp"], create="require")
    def create(
        self,
        dao_name: String,
        threshold: UInt64,
        num_members: UInt64,
        voting_period: UInt64,
        execution_delay: UInt64
    ) -> None:
        assert threshold >= UInt64(1), "Threshold must be >= 1"
        assert threshold <= num_members, "Threshold cannot exceed member count"
        assert num_members >= UInt64(1), "DAO requires at least 1 member"

        self.dao_name.value = dao_name
        self.threshold.value = threshold
        self.num_members.value = num_members
        self.proposal_count.value = UInt64(0)
        self.voting_period.value = voting_period
        self.execution_delay.value = execution_delay

    @arc4.abimethod
    def add_member(self, index: UInt64, public_key: arc4.DynamicBytes) -> None:
        assert Txn.sender == Global.creator_address, "Only creator"
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
        
        start = Global.latest_timestamp
        end = start + self.voting_period.value

        prop = DaoProposal(
            recipient=recipient,
            amount=arc4.UInt64(amount),
            desc_hash=arc4.DynamicBytes(desc_hash),
            start_time=arc4.UInt64(start),
            end_time=arc4.UInt64(end),
            yes_votes=arc4.UInt64(0),
            no_votes=arc4.UInt64(0),
            executed=arc4.Bool(False)
        )
        op.Box.put(box_key, prop.bytes)
        
        arc4.emit(DaoProposalCreated(
            proposal_id=arc4.UInt64(proposal_id),
            end_time=arc4.UInt64(end)
        ))
        return proposal_id

    @arc4.abimethod
    def submit_vote(
        self,
        proposal_id: UInt64,
        signer_index: UInt64,
        vote_type: arc4.UInt8, # 1=Yes, 2=No
        signature: arc4.DynamicBytes
    ) -> None:
        assert signer_index < self.num_members.value, "Invalid index"

        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "No proposal"
        
        prop = DaoProposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Executed"
        
        assert Global.latest_timestamp >= prop.start_time.native, "Voting hasn't started"
        assert Global.latest_timestamp <= prop.end_time.native, "Voting ended"

        sig_key = b"sig_" + op.itob(proposal_id) + b"_" + op.itob(signer_index)
        sig_data, sig_exists = op.Box.get(sig_key)
        assert not sig_exists, "Already voted"

        pk_key = b"pk_" + op.itob(signer_index)
        pubkey, pk_exists = op.Box.get(pk_key)
        assert pk_exists, "Signer key missing"

        message = (
            op.itob(proposal_id)
            + prop.recipient.bytes
            + op.itob(prop.amount.native)
            + prop.desc_hash.bytes
            + op.itob(vote_type.native)
        )
        assert op.falcon_verify(message, signature.bytes, pubkey), "Invalid signature"

        op.Box.put(sig_key, Bytes(b"1"))

        y = prop.yes_votes.native
        n = prop.no_votes.native
        if vote_type.native == UInt64(1):
            y += UInt64(1)
        elif vote_type.native == UInt64(2):
            n += UInt64(1)

        new_prop = DaoProposal(
            recipient=prop.recipient,
            amount=prop.amount,
            desc_hash=prop.desc_hash.copy(),
            start_time=prop.start_time,
            end_time=prop.end_time,
            yes_votes=arc4.UInt64(y),
            no_votes=arc4.UInt64(n),
            executed=prop.executed
        )
        op.Box.put(prop_key, new_prop.bytes)
        
        arc4.emit(DaoVoteSubmitted(
            proposal_id=arc4.UInt64(proposal_id),
            signer_index=arc4.UInt64(signer_index),
            vote_type=vote_type
        ))

    @arc4.abimethod
    def execute_proposal(self, proposal_id: UInt64) -> None:
        prop_key = b"prop_" + op.itob(proposal_id)
        prop_bytes, exists = op.Box.get(prop_key)
        assert exists, "No proposal"
        
        prop = DaoProposal.from_bytes(prop_bytes)
        assert not prop.executed.native, "Executed"
        
        executable_time = prop.end_time.native + self.execution_delay.value
        assert Global.latest_timestamp >= executable_time, "Timelock active"
        
        assert prop.yes_votes.native >= self.threshold.value, "Quorum not reached"
        assert prop.yes_votes.native > prop.no_votes.native, "Rejected by majority"

        new_prop = DaoProposal(
            recipient=prop.recipient,
            amount=prop.amount,
            desc_hash=prop.desc_hash.copy(),
            start_time=prop.start_time,
            end_time=prop.end_time,
            yes_votes=prop.yes_votes,
            no_votes=prop.no_votes,
            executed=arc4.Bool(True)
        )
        op.Box.put(prop_key, new_prop.bytes)
        
        arc4.emit(DaoExecuted(proposal_id=arc4.UInt64(proposal_id)))

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
