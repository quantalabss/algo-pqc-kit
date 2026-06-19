"""
Example 01: Generate and Save a Falcon-1024 Account.
Shows how to generate a keypair, derive the AVM Logic Signature address,
sign a dummy transaction, and persist the account to disk safely.
"""

from sdk.account import FalconAccount

def main():
    print("--- algo-pqc-kit: Falcon-1024 Account Lifecycle ---\n")

    print("1. Generating new Falcon-1024 account...")
    account = FalconAccount.generate()
    
    print(f"Public Key ({len(account.public_key)} bytes): {account.public_key[:16].hex()}...")
    print(f"Algorand Address: {account.address}")
    
    # Sign a dummy transaction ID (32 bytes)
    dummy_txid = b"A" * 32
    print("\n2. Signing a dummy 32-byte transaction ID...")
    sig = account.sign_transaction(dummy_txid)
    print(f"Signature length: {len(sig)} bytes")
    print(f"Signature prefix: {sig[:16].hex()}...")

    print("\n3. Saving account to disk...")
    save_path = "demo_account.json"
    account.save(save_path)
    print(f"Saved to {save_path} (DO NOT SHARE THIS FILE in production)")

    print("\n4. Loading account from disk...")
    loaded_account = FalconAccount.load(save_path)
    print(f"Loaded Algorand Address: {loaded_account.address}")
    
    if account.address == loaded_account.address:
        print("Success! Addresses match.")

if __name__ == "__main__":
    main()
