import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import algosdk
from algosdk.atomic_transaction_composer import AccountTransactionSigner
from algokit_utils import AlgorandClient, ApplicationClient, TransactionParameters, ApplicationSpecification, PaymentParams, AlgoAmount
from algokit_utils.config import config

# Import our SDK to generate real Falcon keys for the committee
sys.path.append(str(Path(__file__).parent.parent))
from sdk.account import FalconAccount

def ensure_deployer() -> str:
    load_dotenv()
    mnemonic = os.getenv("DEPLOYER_MNEMONIC")
    if not mnemonic:
        private_key, address = algosdk.account.generate_account()
        mnemonic = algosdk.mnemonic.from_private_key(private_key)
        with open(".env", "a") as f:
            f.write(f'DEPLOYER_MNEMONIC="{mnemonic}"\n')
        print(f"\n[!] New Testnet account created: {address}")
        print("Please fund this account using the Algorand Testnet Dispenser:")
        print("    https://bank.testnet.algorand.network/")
        print("\nAfter funding, run this script again.")
        sys.exit(0)
    
    return algosdk.mnemonic.to_private_key(mnemonic)

def main():
    # 1. Setup Deployer
    private_key = ensure_deployer()
    address = algosdk.account.address_from_private_key(private_key)
    signer = AccountTransactionSigner(private_key)
    
    # 2. Connect to Testnet
    algorand = AlgorandClient.testnet()
    
    try:
        acct_info = algorand.account.get_information(address)
        balance = acct_info.amount.micro_algo
        if balance < 2_000_000:  # Need ~2 ALGO for contract deployments
            print(f"Account {address} has only {balance/1e6} ALGO.")
            print("Please fund it with at least 2 ALGO using https://bank.testnet.algorand.network/")
            sys.exit(1)
        print(f"Deploying with account {address} (Balance: {balance/1e6} ALGO)")
    except Exception as e:
        print(f"Error fetching account info (perhaps it is unfunded?): {e}")
        print(f"Please fund {address} at https://bank.testnet.algorand.network/")
        sys.exit(1)

    # 3. Generate a 1-of-1 Falcon-1024 Committee for testing
    # Note: A single Falcon PK is 1793 bytes. AVM app args limit is 2048 bytes.
    # To deploy an M-of-N vault in production, we would add members one by one.
    print("\nGenerating 1 Falcon-1024 account for the DAO committee (due to 2KB txn limit)...")
    members = [FalconAccount.generate() for _ in range(1)]
    for i, m in enumerate(members):
        m.save(f"artifacts/test_committee_{i}.json")
    print("Keys saved to artifacts/test_committee_*.json")

    pubkeys_abi = [m.public_key for m in members]

    # 4. Deploy PQCDao
    print("\nDeploying PQCDao...")
    dao_app_spec_str = Path("contracts/build/PQCDao.arc32.json").read_text()
    
    dao_client = ApplicationClient(
        algod_client=algorand.client.algod,
        app_spec=ApplicationSpecification.from_json(dao_app_spec_str),
        signer=signer,
        sender=address,
    )
    
    dao_create_response = dao_client.create(
        call_abi_method="create",
        dao_name="PQC Demo DAO",
        threshold=1,
        public_keys=pubkeys_abi,
    )
    dao_app_id = dao_client.app_id
    dao_app_address = algosdk.logic.get_application_address(dao_app_id)
    print(f"PQCDao deployed! App ID: {dao_app_id}")

    print("Funding PQCDao for box storage...")
    algorand.send.payment(
        PaymentParams(
            sender=address,
            receiver=dao_app_address,
            amount=AlgoAmount(micro_algo=2000000),
            signer=signer,
        )
    )

    print("Bootstrapping PQCDao boxes...")
    dao_client.call(
        call_abi_method="bootstrap",
        public_keys=pubkeys_abi,
        transaction_parameters=TransactionParameters(
            boxes=[(dao_app_id, b"pk_\x00\x00\x00\x00\x00\x00\x00\x00")]
        )
    )

    # 5. Deploy FalconVault
    print("\nDeploying FalconVault...")
    vault_app_spec_str = Path("contracts/build/FalconVault.arc32.json").read_text()
    
    vault_client = ApplicationClient(
        algod_client=algorand.client.algod,
        app_spec=ApplicationSpecification.from_json(vault_app_spec_str),
        signer=signer,
        sender=address,
    )
    
    vault_create_response = vault_client.create(
        call_abi_method="create",
        threshold=1,
        public_keys=pubkeys_abi,
        asset_id=0,
    )
    vault_app_id = vault_client.app_id
    vault_app_address = algosdk.logic.get_application_address(vault_app_id)
    print(f"FalconVault deployed! App ID: {vault_app_id}")

    print("Funding FalconVault for box storage...")
    algorand.send.payment(
        PaymentParams(
            sender=address,
            receiver=vault_app_address,
            amount=AlgoAmount(micro_algo=2000000),
            signer=signer,
        )
    )

    print("Bootstrapping FalconVault boxes...")
    vault_client.call(
        call_abi_method="bootstrap",
        public_keys=pubkeys_abi,
        transaction_parameters=TransactionParameters(
            boxes=[(vault_app_id, b"pk_\x00\x00\x00\x00\x00\x00\x00\x00")]
        )
    )

    print("\n==============================================")
    print("DEPLOYMENT SUCCESSFUL")
    print(f"PQCDao App ID: {dao_app_id}")
    print(f"FalconVault App ID: {vault_app_id}")
    print("==============================================")
    print("Commit the code, add these App IDs to your Forum post, and you're good to go!")

if __name__ == "__main__":
    main()
