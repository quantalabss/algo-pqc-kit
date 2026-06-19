"""
Example 02: 2-of-3 FalconVault Deployment.
This script demonstrates how to deploy a M-of-N threshold vault, 
funding it and adding guardians to its box storage.
Requires LocalNet or TestNet environment variables.
"""

import os
from sdk.account import FalconAccount
from sdk.vault import PQCVault

def main():
    print("--- algo-pqc-kit: 2-of-3 FalconVault ---\n")

    print("1. Generating 3 Falcon-1024 guardian accounts...")
    g1 = FalconAccount.generate()
    g2 = FalconAccount.generate()
    g3 = FalconAccount.generate()

    print(f"Guardian 1: {g1.address}")
    print(f"Guardian 2: {g2.address}")
    print(f"Guardian 3: {g3.address}")

    threshold = 2
    print(f"\nConfiguration: {threshold}-of-3 threshold signature required for release.")

    print("\n[NOTE] Deployment requires an Algod client and funded deployer account.")
    print("To deploy on TestNet, use:")
    print('''
    from algosdk.v2client import algod
    algod_client = algod.AlgodClient("", "https://testnet-api.algonode.cloud")
    deployer_sk = "YOUR_TESTNET_PRIVATE_KEY" # Base64 string or mnemonic
    deployer_account = {"pk": ..., "sk": deployer_sk}

    vault = PQCVault.deploy(
        algod_client=algod_client,
        deployer_account=deployer_account,
        threshold=2,
        public_keys=[g1.public_key, g2.public_key, g3.public_key]
    )
    print(f"Vault App ID: {vault.app_id}")
    print(f"Vault Address: {vault.address}")
    ''')

    print("For LocalNet deployment, ensure you have Algokit running (`algokit localnet start`)")
    print("and use `algokit_utils` to fetch the default client and dispenser account.")

if __name__ == "__main__":
    main()
