import pytest
import algokit_utils
from algosdk.atomic_transaction_composer import AccountTransactionSigner
from algosdk.transaction import PaymentTxn
from pathlib import Path
import json

import sys
sys.path.append(str(Path(__file__).parent.parent))

# Assuming algo-pqc-kit SDK provides FalconAccount
from sdk.account import FalconAccount
from sdk.multisig import FalconMultisig

@pytest.fixture
def algod_client():
    return algokit_utils.get_algod_client(algokit_utils.get_default_localnet_config("algod"))

@pytest.fixture
def indexer_client():
    return algokit_utils.get_indexer_client(algokit_utils.get_default_localnet_config("indexer"))

@pytest.fixture
def creator(algod_client):
    acct = algokit_utils.get_localnet_default_account(algod_client)
    return acct

def test_falcon_vault_v2_box_aggregation(algod_client, creator):
    """
    Test the V2 FalconVault using the Multi-Transaction Box Storage Pattern.
    Proves that we can bypass the 2048B limit for M-of-N Falcon-1024 verification.
    """
    # 1. Generate 3 Falcon-1024 accounts for a 2-of-3 threshold
    f_accounts = [FalconAccount.generate() for _ in range(3)]
    threshold = 2
    
    # 2. Load ARC-56/ARC-32 Application Specification
    spec_path = Path(__file__).parent.parent / "contracts" / "FalconVault.arc56.json"
    with open(spec_path) as f:
        spec = json.load(f)
        
    signer = AccountTransactionSigner(creator.private_key)
    
    client = algokit_utils.ApplicationClient(
        algod_client=algod_client,
        app_spec=spec,
        signer=signer,
    )
    
    # 3. Create the Vault (No array limit hit, just threshold and count)
    client.create(
        threshold=threshold,
        num_signers=len(f_accounts),
        asset_id=0,
    )
    
    # Fund the app account for Box Storage MBRs
    algokit_utils.transfer(
        algod_client,
        algokit_utils.TransferParameters(
            from_account=creator,
            to_address=client.app_address,
            micro_algos=10_000_000, # 10 ALGO for boxes
        )
    )
    
    # 4. Add Signers sequentially into Box Storage (Bypasses 2048B limit)
    for idx, f_acc in enumerate(f_accounts):
        client.call(
            "add_signer",
            index=idx,
            public_key=f_acc.get_public_key_bytes(),
            boxes=[(client.app_id, b"pk_" + idx.to_bytes(8, "big"))]
        )
        
    # 5. Propose a Release
    proposal_id = client.call(
        "propose_release",
        recipient=creator.address,
        amount=1_000_000, # 1 ALGO
        boxes=[(client.app_id, b"prop_0" * 8)] # Mock box ref
    ).return_value
    
    # Message to sign: itob(proposal_id) || recipient || itob(amount)
    # The SDK handles this internally, but we simulate the payload:
    payload = proposal_id.to_bytes(8, "big") + algokit_utils.get_account_address(creator.private_key) + (1_000_000).to_bytes(8, "big")
    
    # 6. Signers submit their 1220B signatures individually
    for i in range(threshold):
        signature = f_accounts[i].sign(payload)
        
        client.call(
            "submit_signature",
            proposal_id=proposal_id,
            signer_index=i,
            signature=signature,
            boxes=[
                (client.app_id, b"prop_" + proposal_id.to_bytes(8, "big")),
                (client.app_id, b"sig_" + proposal_id.to_bytes(8, "big") + b"_" + i.to_bytes(8, "big")),
                (client.app_id, b"pk_" + i.to_bytes(8, "big")),
            ]
        )
        
    # 7. Execute the transaction (Quorum reached!)
    client.call(
        "execute_release",
        proposal_id=proposal_id,
        boxes=[(client.app_id, b"prop_" + proposal_id.to_bytes(8, "big"))]
    )
    
    print("V2 Box Aggregation test passed. M-of-N threshold executed successfully.")
