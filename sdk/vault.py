"""
vault.py — PQCVault: deploy and interact with FalconVault on Algorand.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class PQCVault:
    """
    High-level interface to a deployed FalconVault ARC-4 contract.

    Usage
    -----
        vault = PQCVault.deploy(client, deployer, threshold=2, public_keys=[pk1, pk2, pk3])
        print(vault.app_id)
        print(vault.address)
    """
    app_id: int
    address: str
    threshold: int
    num_signers: int

    @classmethod
    def deploy(
        cls,
        algod_client,
        deployer_account,
        threshold: int,
        public_keys: list[bytes],
        asset_id: int = 0,
    ) -> "PQCVault":
        """
        Deploy a new FalconVault to Algorand Testnet/Mainnet.

        Parameters
        ----------
        algod_client : algosdk.v2client.algod.AlgodClient
        deployer_account : dict with 'pk' and 'sk' keys
        threshold : int — M
        public_keys : list[bytes] — N Falcon-1024 public keys
        asset_id : int — 0 for ALGO, ASA ID otherwise

        Returns
        -------
        PQCVault
            Configured vault pointing at the deployed contract.
        """
        # Import AlgoKit utils for deployment
        try:
            from algokit_utils import ApplicationClient, Account
        except ImportError:
            raise ImportError("algokit-utils required: pip install algokit-utils")

        # Compile and deploy the FalconVault contract
        # (Requires puyapy to compile contracts/falcon_vault.py first)
        raise NotImplementedError(
            "Run: puyapy contracts/falcon_vault.py\n"
            "Then use algokit deploy to push to Testnet.\n"
            "See scripts/deploy_vault.py for the full deployment script."
        )

    @classmethod
    def from_app_id(cls, algod_client, app_id: int) -> "PQCVault":
        """Connect to an already-deployed vault."""
        try:
            info = algod_client.application_info(app_id)
            state = {s["key"]: s["value"] for s in info["params"]["global-state"]}
            threshold = state.get("dGhyZXNob2xk", {}).get("uint", 0)   # base64("threshold")
            num_signers = state.get("bnVtX3NpZ25lcnM=", {}).get("uint", 0)
            from algosdk import logic
            address = logic.get_application_address(app_id)
            return cls(app_id=app_id, address=address, threshold=threshold, num_signers=num_signers)
        except Exception as e:
            raise RuntimeError(f"Failed to load vault {app_id}: {e}") from e
