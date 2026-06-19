"""
algo-pqc-kit SDK
================
Python SDK for Algorand post-quantum cryptography development.

Provides:
- FalconAccount: Generate Falcon-1024 keypairs, derive Algorand Logic Sig addresses
- FalconMultisig: M-of-N threshold co-signing sessions
- PQCVault: Deploy and interact with the FalconVault ARC-4 contract

Quick start
-----------
    from algo_pqc_kit import FalconAccount, FalconMultisig

    # Generate a PQC account
    account = FalconAccount.generate()
    print(f"Algorand address: {account.address}")

    # Create a 2-of-3 committee
    keys = [FalconAccount.generate() for _ in range(3)]
    multisig = FalconMultisig.create(threshold=2, members=[k.public_key for k in keys])
    print(f"Multisig address: {multisig.address}")
"""

from .account import FalconAccount
from .multisig import FalconMultisig
from .vault import PQCVault

__all__ = ["FalconAccount", "FalconMultisig", "PQCVault"]
__version__ = "0.3.0"
