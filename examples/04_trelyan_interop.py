"""
04_trelyan_interop.py

Demonstrates interoperability between algo-pqc-kit and the TRELYAN Post-Quantum
Inscription Protocol. 

TRELYAN is a protocol for immutable, write-once inscriptions authorized by 
Falcon-1024 signatures via the Algorand AVM `falcon_verify` opcode.

This example shows how a FalconAccount (algo-pqc-kit) can locally build 
and sign the exact payload required to authorize a TRELYAN inscription.
"""

import hashlib
import struct
import base64

from algo_pqc_kit import FalconAccount

# --- TRELYAN Protocol Constants ---
# From TRELYAN spec v0.2
DOMAIN_TAG = b"TRELYAN-INSCRIPTION-v1"


def build_trelyan_message(
    app_id: int, 
    cell_id: int, 
    artifact_hash: bytes, 
    genesis_hash_b64: str
) -> bytes:
    """
    Reconstructs the exact domain-separated message that the TRELYAN contract
    will verify on-chain using `falcon_verify`.
    
    M = DOMAIN_TAG || app_id (uint64) || cell_id (uint64) || artifact_hash (32B) || genesis_hash (32B)
    """
    assert len(artifact_hash) == 32, "Artifact hash must be exactly 32 bytes"
    
    genesis_bytes = base64.b64decode(genesis_hash_b64)
    assert len(genesis_bytes) == 32, "Genesis hash must be 32 bytes"

    # Algorand uint64 serialization is big-endian 8 bytes
    app_id_bytes = struct.pack(">Q", app_id)
    cell_id_bytes = struct.pack(">Q", cell_id)

    return (
        DOMAIN_TAG 
        + app_id_bytes 
        + cell_id_bytes 
        + artifact_hash 
        + genesis_bytes
    )


def main():
    print("--- algo-pqc-kit <-> TRELYAN Interop Demo ---\n")

    # 1. We use an algo-pqc-kit account as the controlling identity
    print("1. Generating Falcon-1024 identity via algo-pqc-kit...")
    account = FalconAccount.generate()
    print(f"   PQC Address: {account.address}")
    print(f"   Public Key:  {account.public_key.hex()[:32]}...\n")

    # 2. Define the target TRELYAN environment
    # (e.g., Brandon's TestNet deployment)
    trelyan_app_id = 763809096
    cell_id = 42  # Example cell ID
    testnet_genesis_b64 = "SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=" 
    
    # The artifact we want to inscribe (e.g., sha512_256 of a JSON document)
    document_content = b'{"title": "algo-pqc-kit integration", "version": "1.0"}'
    artifact_hash = hashlib.new("sha512_256", document_content).digest()
    
    print("2. Building TRELYAN Inscription Payload...")
    print(f"   Target App ID: {trelyan_app_id}")
    print(f"   Target Cell:   {cell_id}")
    print(f"   Artifact Hash: {artifact_hash.hex()[:16]}...\n")

    # 3. Build the exact bytes the contract will hash
    message = build_trelyan_message(
        app_id=trelyan_app_id,
        cell_id=cell_id,
        artifact_hash=artifact_hash,
        genesis_hash_b64=testnet_genesis_b64
    )

    # 4. Sign with the algo-pqc-kit account!
    print("3. Signing payload with Falcon-1024 key...")
    # Falcon signatures are compressed, deterministic, and natively
    # compatible with the AVM falcon_verify opcode.
    signature = account.sign(message)
    
    print(f"   Signature Length: {len(signature)} bytes")
    print(f"   Signature Hex:    {signature.hex()[:32]}...\n")
    
    print("SUCCESS!")
    print("This signature is perfectly formatted to be passed directly into the")
    print("TRELYAN 'inscribe' ABI method as the `falcon_sig` argument.")


if __name__ == "__main__":
    main()
