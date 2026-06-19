"""
deploy.py
=========
Production deployment script for algo-pqc-kit contracts.
Supports LocalNet, TestNet, and MainNet.

Usage:
    python scripts/deploy.py --network testnet
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

import algokit_utils
from algosdk.v2client import algod
from algosdk.atomic_transaction_composer import AccountTransactionSigner

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
from sdk.account import FalconAccount
from sdk.vault import PQCVault

def get_client_and_account(network: str):
    if network == "localnet":
        # Ensure algokit localnet is running
        try:
            client = algokit_utils.get_algod_client(algokit_utils.get_default_localnet_config("algod"))
            deployer = algokit_utils.get_localnet_default_account(client)
            deployer_dict = {"sk": deployer.private_key}
            return client, deployer_dict
        except Exception as e:
            print("Error connecting to LocalNet. Did you run 'algokit localnet start'?")
            sys.exit(1)
            
    else:
        # TestNet or MainNet
        load_dotenv()
        algod_url = os.getenv("ALGOD_URL")
        algod_token = os.getenv("ALGOD_TOKEN", "")
        mnemonic = os.getenv("DEPLOYER_MNEMONIC")

        if not algod_url or not mnemonic:
            print(f"Error: Missing ALGOD_URL or DEPLOYER_MNEMONIC in .env for {network} deployment.")
            sys.exit(1)

        client = algod.AlgodClient(algod_token, algod_url)
        from algosdk import mnemonic as algo_mnemonic
        private_key = algo_mnemonic.to_private_key(mnemonic)
        deployer_dict = {"sk": private_key}
        
        # Simple balance check
        from algosdk.account import address_from_private_key
        addr = address_from_private_key(private_key)
        try:
            info = client.account_info(addr)
            if info.get("amount", 0) < 5_000_000:
                print(f"Warning: Deployer {addr} may not have enough ALGO to fund Vault box storage.")
        except Exception as e:
            print(f"Failed to check deployer balance: {e}")
            
        return client, deployer_dict

def main():
    parser = argparse.ArgumentParser(description="Deploy algo-pqc-kit contracts.")
    parser.add_argument("--network", choices=["localnet", "testnet", "mainnet"], default="localnet")
    args = parser.parse_args()

    print(f"--- Deploying algo-pqc-kit to {args.network.upper()} ---")
    client, deployer_account = get_client_and_account(args.network)
    
    from algosdk.account import address_from_private_key
    print(f"Deployer Address: {address_from_private_key(deployer_account['sk'])}")

    print("\n1. Generating dummy PQC keys for initial deployment testing...")
    g1 = FalconAccount.generate()
    g2 = FalconAccount.generate()
    g3 = FalconAccount.generate()
    
    print("\n2. Deploying FalconVault (2-of-3)...")
    try:
        vault = PQCVault.deploy(
            algod_client=client,
            deployer_account=deployer_account,
            threshold=2,
            public_keys=[g1.public_key, g2.public_key, g3.public_key]
        )
        print(f"✅ Vault App ID: {vault.app_id}")
        print(f"✅ Vault Address: {vault.address}")
        
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        sys.exit(1)

    print("\nDeployment complete. Add these App IDs to your docs/deployments.md reference.")

if __name__ == "__main__":
    main()
