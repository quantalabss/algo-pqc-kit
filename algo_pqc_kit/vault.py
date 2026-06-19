"""
vault.py -- PQCVault: deploy and interact with FalconVault on Algorand.

Updated for v0.3 Enterprise Vault (supports arbitrary transactions,
dynamic membership).
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
    ) -> "PQCVault":
        """
        Deploy a new FalconVault to Algorand TestNet/MainNet.

        Parameters
        ----------
        algod_client : algosdk.v2client.algod.AlgodClient
        deployer_account : dict with 'sk' key
        threshold : int -- M
        public_keys : list[bytes] -- N Falcon-1024 public keys

        Returns
        -------
        PQCVault
            Configured vault pointing at the deployed contract.
        """
        try:
            from algokit_utils import (
                AppFactory, Arc56Contract, AlgorandClient,
                AppFactoryParams, AppFactoryCreateMethodCallParams,
                AppClientMethodCallParams
            )
            from algosdk.atomic_transaction_composer import AccountTransactionSigner
            from algosdk import logic
            from pathlib import Path
        except ImportError:
            raise ImportError("algokit-utils v4 required: pip install algokit-utils")

        app_spec_path = Path(__file__).parent.parent / "contracts" / "FalconVault.arc56.json"
        if not app_spec_path.exists():
            raise FileNotFoundError(
                f"Contract artifact not found at {app_spec_path}. "
                "Run: puyapy --target-avm-version 12 contracts/falcon_vault.py"
            )

        private_key = deployer_account['sk']
        from algosdk.account import address_from_private_key
        sender_address = address_from_private_key(private_key)
        signer = AccountTransactionSigner(private_key)

        app_spec = Arc56Contract.from_json(app_spec_path.read_text())
        algorand = AlgorandClient.from_clients(algod=algod_client)

        factory = AppFactory(
            AppFactoryParams(
                app_spec=app_spec,
                algorand=algorand,
                default_sender=sender_address,
                default_signer=signer,
            )
        )

        result = factory.send.create(
            AppFactoryCreateMethodCallParams(
                method="create",
                args=[threshold, len(public_keys)]
            )
        )

        app_client = result[0]
        app_id = app_client.app_id
        app_address = app_client.app_address

        # Fund the contract for box storage
        sp = algod_client.suggested_params()
        from algosdk.transaction import PaymentTxn
        ptxn = PaymentTxn(sender_address, sp, app_address, 2_000_000)
        algod_client.send_transaction(ptxn.sign(private_key))

        # Add signers to box storage
        # app_client is already set
        for index, pk in enumerate(public_keys):
            box_name = b"pk_" + index.to_bytes(8, "big")
            app_client.send.call(
                AppClientMethodCallParams(
                    method="add_signer_init",
                    args=[index, pk],
                    box_references=[box_name]
                )
            )

        return cls(
            app_id=app_id,
            address=app_address,
            threshold=threshold,
            num_signers=len(public_keys)
        )

    @classmethod
    def from_app_id(cls, algod_client, app_id: int) -> "PQCVault":
        """Connect to an already-deployed vault."""
        try:
            info = algod_client.application_info(app_id)
            state = {s["key"]: s["value"] for s in info["params"]["global-state"]}
            threshold = state.get("dGhyZXNob2xk", {}).get("uint", 0)
            num_signers = state.get("bnVtX3NpZ25lcnM=", {}).get("uint", 0)
            from algosdk import logic
            address = logic.get_application_address(app_id)
            return cls(app_id=app_id, address=address, threshold=threshold, num_signers=num_signers)
        except Exception as e:
            raise RuntimeError(f"Failed to load vault {app_id}: {e}") from e
