"""
Example 03: DAO Proposal Lifecycle with Post-Quantum Accounts.
Demonstrates proposing and voting using Falcon-1024 accounts.
"""

from sdk.account import FalconAccount

def main():
    print("--- algo-pqc-kit: PQC DAO Lifecycle ---\n")

    print("1. Participant Generation...")
    proposer = FalconAccount.generate()
    voter = FalconAccount.generate()

    print(f"Proposer: {proposer.address}")
    print(f"Voter:    {voter.address}")

    proposal_id = 42
    print(f"\n2. Proposer creates proposal #{proposal_id}...")
    
    # In a real DAO, the proposer signs the proposal creation payload
    payload = b"create_proposal" + proposal_id.to_bytes(8, "big")
    sig = proposer.sign(payload)
    print(f"Proposer Signature: {sig[:16].hex()}...")

    print(f"\n3. Voter casts vote for proposal #{proposal_id}...")
    # Voter signs the vote payload
    vote_payload = b"vote" + proposal_id.to_bytes(8, "big") + b"\x01" # 0x01 for YES
    vote_sig = voter.sign(vote_payload)
    print(f"Voter Signature: {vote_sig[:16].hex()}...")

    print("\n[NOTE] To execute this on-chain, the signatures and public keys")
    print("are submitted to the PQCDao smart contract via Application calls,")
    print("which internally uses AVM's `falcon_verify` opcode.")

if __name__ == "__main__":
    main()
