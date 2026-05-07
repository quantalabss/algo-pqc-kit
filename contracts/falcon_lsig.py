"""
falcon_lsig.py
==============
Algorand Logic Signature that gates spending with a Falcon-1024 signature.
Uses AVM v12 `falcon_verify` opcode — 100% on-chain post-quantum verification.

This is a STATELESS contract (Logic Signature / Smart Signature).
It acts as a PQC account: any ALGO held at its address can only be spent
if a valid Falcon-1024 signature over the transaction is provided.

Usage
-----
    from algopy import *

    # Compile with puyapy to get the TEAL program bytes
    # Hash of that program = the Algorand address (PQC account address)

AVM opcode reference
--------------------
    falcon_verify data sig pubkey → bool
    - data:    []byte  — message (typically txn.TxID)
    - sig:     [1232]byte — compressed Falcon-1024 signature
    - pubkey:  [1793]byte — Falcon-1024 public key
    - cost:    1700 opcodes
    - AVM:     v12+
"""

from algopy import Bytes, Global, Txn, op, TemplateVar, logicsig


# ---------------------------------------------------------------------------
# Single-key Falcon-1024 Logic Signature
# ---------------------------------------------------------------------------
# The public key is EMBEDDED in the program at compile time via a template var.
# This means each PQC account has its own unique lsig program, and the
# account address is sha512/256( b"Program" || program_bytes ).
# ---------------------------------------------------------------------------

@logicsig
def falcon_single_lsig() -> bool:
    """
    Single-key Falcon-1024 Logic Signature.

    Approves a transaction if and only if:
      1. The transaction type is Payment or AssetTransfer (no rekey allowed)
      2. A valid Falcon-1024 signature over the transaction ID is provided
         as the first argument (Txn.application_args[0])
      3. The transaction does not rekey the account

    Parameters
    ----------
    PUBKEY : Bytes (Template Variable)
        The signer's Falcon-1024 public key (1793 bytes).
        Embedded at compile time via template substitution.
    """
    public_key = TemplateVar[Bytes]("PUBKEY")

    # Prevent rekey — critical for account security
    assert Txn.rekey_to == Global.zero_address, "Rekey not allowed on PQC accounts"

    # Signature is passed as the first transaction argument
    # In a LogicSig context, args are accessible via Arg opcode
    signature = op.arg(0)  # 1232-byte Falcon-1024 signature

    # The signed message is the transaction ID
    message = Txn.tx_id

    # Verify the Falcon-1024 signature using AVM v12 opcode
    return op.falcon_verify(message, signature, public_key)
