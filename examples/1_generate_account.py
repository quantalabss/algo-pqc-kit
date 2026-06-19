import sys
from pathlib import Path

# Add the parent directory to the path so we can import algo_pqc_kit
sys.path.append(str(Path(__file__).parent.parent))

from sdk import FalconAccount

def main():
    print("Generating a new Falcon-1024 account...")
    # Generate the account
    account = FalconAccount.generate()
    
    print("\n[+] Account Generated Successfully!")
    print(f"    Public Key (hex) : {account.public_key.hex()[:32]}...")
    print(f"    Algorand Address : {account.address}")
    
    # Save the account to a file
    save_path = "artifacts/demo_account.json"
    Path("artifacts").mkdir(exist_ok=True)
    account.save(save_path)
    print(f"\n[+] Account saved to {save_path}")
    print("    Keep this file secure. The private key is stored in plaintext.")
    
    # Reload to verify
    loaded_account = FalconAccount.load(save_path)
    assert account.address == loaded_account.address
    print("    Verified: Account reloaded successfully.")

if __name__ == "__main__":
    main()
