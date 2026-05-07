"""
account.py
==========
FalconAccount — Falcon-1024 keypair with Algorand Logic Sig address derivation.

This wraps the Algorand-compatible Falcon-1024 implementation and derives
the on-chain address by compiling the falcon_lsig Logic Signature program
with the public key embedded, then computing sha512/256 of the program bytes.

Key sizes (Falcon-1024)
-----------------------
    Public key:  1793 bytes
    Private key: 2305 bytes (secret — never logged)
    Signature:   1232 bytes (compressed deterministic)

Algorand address derivation
---------------------------
    lsig_program = compile(falcon_lsig_template, public_key=pk)
    address = sha512_256("Program" || lsig_program)
    address_str = base32(address) + checksum_suffix
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Real Falcon-1024 via falcon-python (pip install falcon-python)
from falcon_python import Falcon1024 as _Falcon

# ---------------------------------------------------------------------------
# Falcon-1024 key / signature sizes
# ---------------------------------------------------------------------------
FALCON_PUBKEY_SIZE  = 1793   # bytes (fixed)
FALCON_PRIVKEY_SIZE = 2305   # bytes (fixed)
FALCON_SIG_MAX_SIZE = 1280   # bytes (variable-length upper bound for Falcon-1024)
FALCON_SIG_SIZE     = FALCON_SIG_MAX_SIZE   # alias kept for compatibility


@dataclass
class FalconAccount:
    """
    A post-quantum Algorand account backed by a Falcon-1024 keypair.

    The Algorand "address" is derived from a Logic Signature program that
    embeds the Falcon-1024 public key and verifies a Falcon signature on
    the transaction ID using the AVM `falcon_verify` opcode.

    Attributes
    ----------
    public_key : bytes
        Falcon-1024 public key (1793 bytes). Safe to share.
    _private_key : bytes
        Falcon-1024 private key (2305 bytes). Never expose.
    address : str
        Algorand address string (base32 + checksum).
    lsig_program : bytes
        Compiled Logic Signature program bytes (TEAL bytecode).
    """

    public_key: bytes
    _private_key: bytes = field(repr=False)
    address: str = field(init=False)
    lsig_program: bytes = field(init=False)

    def __post_init__(self) -> None:
        assert len(self.public_key) == FALCON_PUBKEY_SIZE, (
            f"Expected Falcon-1024 public key ({FALCON_PUBKEY_SIZE} bytes), "
            f"got {len(self.public_key)} bytes"
        )
        self.lsig_program = self._derive_lsig_program()
        self.address = self._derive_address()

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def generate(cls) -> "FalconAccount":
        """
        Generate a new Falcon-1024 keypair and derive the Algorand address.

        Returns
        -------
        FalconAccount
            A new account with a fresh Falcon-1024 keypair.
        """
        pk, sk = _generate_falcon_keypair()
        return cls(public_key=pk, _private_key=sk)

    @classmethod
    def from_private_key(cls, private_key: bytes) -> "FalconAccount":
        """
        Restore a FalconAccount from an existing private key.

        Parameters
        ----------
        private_key : bytes
            Falcon-1024 private key bytes (2305 bytes).
        """
        pk = _derive_public_key(private_key)
        return cls(public_key=pk, _private_key=private_key)

    @classmethod
    def load(cls, path: str) -> "FalconAccount":
        """
        Load a FalconAccount from a JSON key file.
        The file must have been saved with save() — both pk and sk are required.
        """
        data = json.loads(Path(path).read_text())
        pk = bytes.fromhex(data["public_key"])
        sk = bytes.fromhex(data["private_key"])
        return cls(public_key=pk, _private_key=sk)

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def sign(self, message: bytes) -> bytes:
        """
        Sign a message with the Falcon-1024 private key.

        Parameters
        ----------
        message : bytes
            The message to sign (for transactions, use the 32-byte TxID).

        Returns
        -------
        bytes
            Falcon-1024 signature (1232 bytes, deterministic).
        """
        return _falcon_sign(self._private_key, message)

    def sign_transaction(self, tx_id: bytes) -> bytes:
        """
        Sign a transaction ID for use with an Algorand Logic Signature.

        Parameters
        ----------
        tx_id : bytes
            The 32-byte Algorand transaction ID.

        Returns
        -------
        bytes
            Falcon-1024 signature (1232 bytes) to attach as lsig argument.
        """
        assert len(tx_id) == 32, "Transaction ID must be 32 bytes"
        return self.sign(tx_id)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Save the account to a JSON key file.

        WARNING: The private key is stored in plaintext.
        Keep this file secure — anyone with the private key controls the account.
        """
        data = {
            "version": "algo-pqc-kit/0.1",
            "algorithm": "falcon-1024",
            "public_key": self.public_key.hex(),
            "private_key": self._private_key.hex(),
            "address": self.address,
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def to_dict(self) -> dict:
        """Return a dict with public information (no private key)."""
        return {
            "algorithm": "falcon-1024",
            "public_key": self.public_key.hex(),
            "address": self.address,
        }

    # ------------------------------------------------------------------
    # Internal: address derivation
    # ------------------------------------------------------------------

    def _derive_lsig_program(self) -> bytes:
        """
        Derive the Logic Signature TEAL bytecode for this public key.

        The lsig program embeds the public key and calls falcon_verify.
        This is the canonical Algorand PQC account program.

        Program structure (TEAL bytecode):
            #pragma version 12
            arg 0                    // push signature (1232 bytes)
            txn TxID                 // push transaction ID (32 bytes)
            byte 0x<public_key_hex>  // push embedded public key (1793 bytes)
            falcon_verify            // opcode 0x85 — verifies and pushes bool
        """
        # Minimal TEAL v12 bytecode for falcon_verify lsig:
        # version(12) | arg(0) | txn TxID | pushbytes(pubkey) | falcon_verify
        version_byte = bytes([12])   # #pragma version 12 → 0x0c (1 byte)

        # TEAL opcodes
        OP_ARG_0 = b"\x2e\x00"       # arg 0
        OP_TXN_TXID = b"\x31\x01"    # txn TxID (field index 0x01)
        OP_FALCON_VERIFY = b"\x85"   # falcon_verify (AVM v12)

        # pushbytes opcode: 0x80 + varint(length) + bytes
        pubkey_len = len(self.public_key)
        # varint encoding for 1793
        varint_len = _encode_varint(pubkey_len)
        OP_PUSHBYTES_PUBKEY = b"\x80" + varint_len + self.public_key

        program = (
            version_byte
            + OP_ARG_0
            + OP_TXN_TXID
            + OP_PUSHBYTES_PUBKEY
            + OP_FALCON_VERIFY
        )
        return program

    def _derive_address(self) -> str:
        """
        Derive the Algorand address from the Logic Signature program bytes.

        address = base32( sha512_256("Program" || program_bytes) || checksum )
        """
        import base64
        prefix = b"Program"
        digest = hashlib.new("sha512_256", prefix + self.lsig_program).digest()
        # Checksum = last 4 bytes of sha512_256 of the digest
        checksum = hashlib.new("sha512_256", digest).digest()[-4:]
        address_bytes = digest + checksum
        # Algorand uses base32 without padding
        return base64.b32encode(address_bytes).decode().rstrip("=")


# ---------------------------------------------------------------------------
# Low-level Falcon operations
# (Wraps Algorand Falcon CLI or native Python binding)
# ---------------------------------------------------------------------------

def _generate_falcon_keypair() -> tuple[bytes, bytes]:
    """Generate a real Falcon-1024 keypair via falcon-python."""
    pk, sk = _Falcon.generate_keypair()
    return pk, sk


def _derive_public_key(private_key: bytes) -> bytes:
    """Not directly supported by falcon-python — store pk at generation time."""
    raise NotImplementedError(
        "falcon-python does not support deriving pk from sk after generation. "
        "Use FalconAccount.generate() and save() to persist both keys."
    )


def _falcon_sign(private_key: bytes, message: bytes) -> bytes:
    """Sign a message with a Falcon-1024 private key."""
    return _Falcon.detached_sign(private_key, message)


def _encode_varint(n: int) -> bytes:
    """Encode an integer as a TEAL-compatible varint."""
    result = bytearray()
    while n > 0x7F:
        result.append((n & 0x7F) | 0x80)
        n >>= 7
    result.append(n)
    return bytes(result)
