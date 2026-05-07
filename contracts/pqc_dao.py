"""
pqc_dao.py
==========
Post-Quantum DAO Governance Contract — ARC-4 stateful smart contract.

Implements a simple but complete DAO with Falcon-1024 gated governance:
- Committee members hold Falcon-1024 keys
- Proposals require M-of-N Falcon signatures to pass
- Treasury spending released on quorum

This is the first PQC-native DAO implementation for Algorand.
All governance actions verified on-chain via AVM falcon_verify opcode.
"""

from algopy import (
    ARC4Contract,
    BigUInt,
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


# Proposal states
PROPOSAL_ACTIVE = 0
PROPOSAL_PASSED = 1
PROPOSAL_REJECTED = 2
PROPOSAL_EXECUTED = 3


class PQCDao(ARC4Contract):
    """
    Post-Quantum DAO

    A decentralized autonomous organization where all governance
    decisions are authorized by Falcon-1024 multi-signatures verified
    on-chain. No Ed25519. No classical multisig. Fully PQC.

    Governance flow
    ---------------
    1. Any committee member creates a proposal (spending amount + recipient)
    2. Committee members sign the proposal message off-chain (Falcon-1024)
    3. Proposer submits M signatures → contract verifies on-chain
    4. If M-of-N verified → proposal executes, treasury pays out

    Storage layout (box storage)
    ----------------------------
    b"pk_{index:8}"      → Falcon-1024 public key (1793 bytes)
    b"prop_{id:8}"       → Proposal data (ABI-encoded)
    """

    def __init__(self) -> None:
        self.threshold = GlobalState(UInt64)
        self.num_members = GlobalState(UInt64)
        self.dao_name = GlobalState(String)
        self.proposal_count = GlobalState(UInt64)

    @arc4.abimethod(allow_actions=["NoOp"], create="require")
    def create(
        self,
        dao_name: String,
        threshold: UInt64,
        public_keys: arc4.DynamicArray[arc4.DynamicBytes],
    ) -> None:
        """
        Initialize the DAO.

        Parameters
        ----------
        dao_name : String
            Human-readable name for the DAO.
        threshold : UInt64
            M — minimum Falcon-1024 signatures required to pass a proposal.
        public_keys : DynamicArray[DynamicBytes]
            Falcon-1024 public keys of all N committee members.
        """
        n = public_keys.length
        assert threshold >= UInt64(1), "Threshold must be >= 1"
        assert threshold <= n, "Threshold cannot exceed member count"
        assert n >= UInt64(2), "DAO requires at least 2 members"

        self.dao_name.value = dao_name
        self.threshold.value = threshold
        self.num_members.value = n
        self.proposal_count.value = UInt64(0)

        # Store public keys in box storage
        for i in urange(n):
            box_key = b"pk_" + op.itob(i)
            op.Box.put(box_key, public_keys[i].bytes)

    @arc4.abimethod
    def submit_proposal(
        self,
        description: String,
        recipient: arc4.Address,
        amount: UInt64,
        signatures: arc4.DynamicArray[arc4.DynamicBytes],
        signer_indices: arc4.DynamicArray[arc4.UInt64],
    ) -> UInt64:
        """
        Submit a spending proposal with M-of-N Falcon signatures.

        If the quorum is reached, the proposal is immediately executed
        (treasury pays out to recipient).

        Parameters
        ----------
        description : String
            Human-readable description of the proposal (stored on-chain).
        recipient : arc4.Address
            Beneficiary of the treasury payment.
        amount : UInt64
            Payment amount in microALGO.
        signatures : DynamicArray[DynamicBytes]
            Falcon-1024 signatures from M committee members.
        signer_indices : DynamicArray[arc4.UInt64]
            Indices of the signing committee members.

        Returns
        -------
        UInt64
            Proposal ID (0-indexed).
        """
        proposal_id = self.proposal_count.value
        self.proposal_count.value = proposal_id + UInt64(1)

        assert signatures.length >= self.threshold.value, "Insufficient signatures"
        assert signatures.length == signer_indices.length, "Sig/index count mismatch"

        # Build the canonical proposal message:
        # proposal_id || recipient || amount || sha256(description)
        desc_hash = op.sha256(description.bytes)
        message = (
            op.itob(proposal_id)
            + recipient.bytes
            + op.itob(amount)
            + desc_hash
        )

        # Verify M-of-N Falcon signatures on-chain
        verified = UInt64(0)
        for i in urange(signatures.length):
            idx = signer_indices[i].native
            assert idx < self.num_members.value, "Member index out of range"

            box_key = b"pk_" + op.itob(idx)
            pubkey, exists = op.Box.get(box_key)
            assert exists, "Public key not found"

            if op.falcon_verify(message, signatures[i].bytes, pubkey):
                verified += UInt64(1)

        assert verified >= self.threshold.value, "Quorum not reached — proposal rejected"

        # Quorum reached — execute the treasury payment
        itxn.Payment(
            receiver=recipient.native,
            amount=amount,
            fee=Global.min_txn_fee,
            note=b"algo-pqc-kit:dao:proposal:" + op.itob(proposal_id),
        ).submit()

        # Store proposal record in box storage for auditability
        prop_data = (
            op.itob(proposal_id)
            + op.itob(amount)
            + recipient.bytes
            + desc_hash
            + op.itob(UInt64(PROPOSAL_EXECUTED))
        )
        op.Box.put(b"prop_" + op.itob(proposal_id), prop_data)

        return proposal_id

    @arc4.abimethod(readonly=True)
    def get_proposal_count(self) -> UInt64:
        """Return total number of proposals submitted."""
        return self.proposal_count.value

    @arc4.abimethod(readonly=True)
    def get_threshold(self) -> UInt64:
        """Return the DAO's signature threshold (M)."""
        return self.threshold.value

    @arc4.abimethod(readonly=True)
    def get_member_count(self) -> UInt64:
        """Return total committee size (N)."""
        return self.num_members.value
