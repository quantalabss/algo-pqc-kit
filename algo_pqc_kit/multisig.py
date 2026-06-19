"""
multisig.py — FalconMultisig: M-of-N Falcon-1024 threshold co-signing.
"""
from __future__ import annotations
import hashlib, struct
from dataclasses import dataclass, field
from .account import FALCON_PUBKEY_SIZE, FALCON_SIG_MAX_SIZE as FALCON_SIG_SIZE


@dataclass
class SignedPayload:
    message: bytes
    signatures: list[bytes]
    indices: list[int]
    threshold: int
    total_signers: int

    def is_complete(self) -> bool:
        return len(self.signatures) >= self.threshold


@dataclass
class SigningSession:
    committee: "FalconMultisig"
    message: bytes
    _signatures: dict[int, bytes] = field(default_factory=dict)

    def add_signature(self, index: int, sig: bytes) -> bool:
        if not (0 <= index < self.committee.total_signers):
            raise ValueError(f"Index {index} out of range")
        if len(sig) == 0 or len(sig) > FALCON_SIG_SIZE:
            raise ValueError(f"Bad sig size: {len(sig)}")
        if index in self._signatures:
            raise ValueError(f"Duplicate signature from index {index}")
        self._signatures[index] = sig
        return True

    @property
    def collected(self) -> int:
        return len(self._signatures)

    @property
    def is_complete(self) -> bool:
        return self.collected >= self.committee.threshold

    def finalize(self) -> SignedPayload:
        if not self.is_complete:
            raise RuntimeError(f"Need {self.committee.threshold}, have {self.collected}")
        items = sorted(self._signatures.items())
        return SignedPayload(
            message=self.message,
            signatures=[s for _, s in items],
            indices=[i for i, _ in items],
            threshold=self.committee.threshold,
            total_signers=self.committee.total_signers,
        )


@dataclass
class FalconMultisig:
    """M-of-N Falcon-1024 threshold committee descriptor."""
    threshold: int
    total_signers: int
    public_keys: list[bytes]

    @classmethod
    def create(cls, threshold: int, members: list[bytes]) -> "FalconMultisig":
        n = len(members)
        assert 1 <= threshold <= n >= 2, "Invalid M-of-N parameters"
        for i, pk in enumerate(members):
            assert len(pk) == FALCON_PUBKEY_SIZE, f"Member {i}: wrong key size"
        return cls(threshold=threshold, total_signers=n, public_keys=list(members))

    @property
    def committee_id(self) -> bytes:
        h = hashlib.sha256(b"FALCON_MULTISIG_V1:")
        h.update(struct.pack(">HH", self.threshold, self.total_signers))
        for pk in sorted(self.public_keys):
            h.update(pk)
        return h.digest()

    @property
    def address(self) -> str:
        return "ms:" + self.committee_id.hex()[:16]

    def build_release_message(self, nonce: int, recipient: str, amount: int) -> bytes:
        import base64
        addr = base64.b32decode(recipient + "=" * (-len(recipient) % 8))[:32]
        return struct.pack(">Q", nonce) + addr + struct.pack(">Q", amount)

    def build_proposal_message(self, proposal_id: int, recipient: str, amount: int, description: str) -> bytes:
        import base64
        addr = base64.b32decode(recipient + "=" * (-len(recipient) % 8))[:32]
        desc_hash = hashlib.sha256(description.encode()).digest()
        return struct.pack(">Q", proposal_id) + addr + struct.pack(">Q", amount) + desc_hash

    def start_session(self, message: bytes) -> SigningSession:
        return SigningSession(committee=self, message=message)
