# algo-pqc-kit

**The first complete Algorand-native post-quantum cryptography developer toolkit.**

[![PyPI](https://img.shields.io/pypi/v/algo-pqc-kit)](https://pypi.org/project/algo-pqc-kit/0.3.1/)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue)](LICENSE-MIT)
[![AVM](https://img.shields.io/badge/AVM-v12-green)](https://developer.algorand.org)
[![PQC](https://img.shields.io/badge/crypto-Falcon--1024%20%7C%20FN--DSA-purple)](https://csrc.nist.gov/pubs/fips/206/final)

---

## What Is This?

Algorand's AVM v12 (deployed November 2025) introduced the `falcon_verify` opcode, enabling **on-chain Falcon-1024 post-quantum signature verification**. But there was no developer toolkit to make it usable.

`algo-pqc-kit` fills that gap:

| Layer | What It Does |
|---|---|
| **Puya Smart Contracts** | `FalconVault` (M-of-N PQC treasury with arbitrary transactions and dynamic membership), `FalconLsig` (PQC account), `PQCDao` (PQC governance with timelocks and voting periods) |
| **Python SDK** | `FalconAccount`, `FalconMultisig`, `PQCVault` -- generate keys, derive addresses, sign, co-sign, deploy |
| **Deployment Scripts** | `scripts/deploy.py` -- deploy contracts to LocalNet, TestNet, or MainNet |

---

## Install

```bash
pip install algo-pqc-kit
```

---

## Quick Start

```python
from algo_pqc_kit import FalconAccount, FalconMultisig

# Generate a Falcon-1024 PQC account (Algorand address derived via lsig)
account = FalconAccount.generate()
print(f"PQC Address: {account.address}")
print(f"Public key:  {account.public_key.hex()[:32]}...")

# Create a 2-of-3 quantum-resistant multisig committee
members = [FalconAccount.generate() for _ in range(3)]
committee = FalconMultisig.create(
    threshold=2,
    members=[m.public_key for m in members]
)
print(f"Committee ID: {committee.address}")

# Build and sign a vault release message
message = committee.build_release_message(
    nonce=0,
    recipient="RECIPIENT_ALGORAND_ADDRESS",
    amount=1_000_000,  # microALGO
)

session = committee.start_session(message)
session.add_signature(index=0, sig=members[0].sign(message))
session.add_signature(index=2, sig=members[2].sign(message))

payload = session.finalize()
print(f"Ready for on-chain submission: {payload.is_complete()}")
```

---

## Smart Contracts

Three ARC-4 contracts compiled with PuyaPy, all using the AVM v12 `falcon_verify` opcode:

### `FalconVault` -- M-of-N Post-Quantum Treasury

```bash
puyapy --target-avm-version 12 contracts/falcon_vault.py
```

A generalized multisig treasury supporting five proposal types:

| Type | Description |
|---|---|
| 0 - Payment | Send ALGO to any address |
| 1 - Asset Transfer | Transfer any ASA token |
| 2 - Application Call | Execute arbitrary smart contract calls |
| 3 - Add Signer | Propose adding a new Falcon-1024 guardian |
| 4 - Remove Signer | Propose removing an existing guardian |

All proposals require M-of-N Falcon-1024 signatures verified on-chain before execution. The threshold auto-adjusts when signers are removed to prevent deadlocks.

### `FalconLsig` -- PQC Logic Signature Account

The foundational primitive: a Logic Signature that embeds a Falcon-1024 public key and gates all spending via `falcon_verify`. This is how Algorand PQC accounts work.

### `PQCDao` -- Post-Quantum DAO Governance

A structured governance contract with production-grade controls:

- **Voting Periods**: Proposals define a `start_time` and `end_time`. Votes outside the window are rejected.
- **Execution Delays (Timelocks)**: A mandatory delay between the voting period closing and when the proposal can be executed, preventing flash-governance attacks.
- **Yes/No Voting**: Members explicitly vote Yes (1) or No (2) with their Falcon-1024 signatures. Proposals must reach quorum AND have more Yes than No votes to pass.
- **Replay Protection**: Each vote is bound to a specific proposal and signer index.

No Ed25519 anywhere in the governance flow.

---

## Contract Compilation

Requires [PuyaPy](https://github.com/algorandfoundation/puya) and AVM v12 target:

```bash
puyapy --target-avm-version 12 contracts/falcon_vault.py contracts/pqc_dao.py
```

This generates ARC-56 app spec files (`.arc56.json`), TEAL approval/clear programs, and source maps in the `contracts/` directory.

---

## Deployment

```bash
# LocalNet (requires Docker + AlgoKit)
python scripts/deploy.py --network localnet

# TestNet
python scripts/deploy.py --network testnet

# MainNet
python scripts/deploy.py --network mainnet
```

For TestNet/MainNet deployments, configure your `.env` file (see `.env.example`).

---

## How It Works

### The AVM `falcon_verify` Opcode

```
falcon_verify(data: []byte, sig: [1232]byte, pubkey: [1793]byte) -> bool
```

- **Cost:** 1700 opcodes per verification
- **AVM version:** 12+ (Algorand mainnet since Nov 2025)
- **Algorithm:** Falcon-1024 / FN-DSA (NIST FIPS 206, deterministic variant)

This opcode is the foundation of all algo-pqc-kit contracts.

### Address Derivation

Algorand PQC accounts are Logic Signatures. The address is:

```
lsig_program = TEAL_v12 [ arg 0; txn TxID; pushbytes <pubkey>; falcon_verify ]
address      = base32( sha512_256("Program" || lsig_program) + checksum )
```

Every Falcon-1024 public key has a unique, deterministic Algorand address.

### Box Storage Multi-Transaction Pattern

Falcon-1024 public keys are 1793 bytes and signatures are up to 1280 bytes, exceeding the AVM's 2048-byte ApplicationArgs limit. The contracts use a multi-transaction session pattern where keys and signatures are written sequentially into Box Storage, enabling theoretically infinite M-of-N threshold sizes.

---

## Security

- **Quantum-resistant:** Falcon-1024 (NIST FN-DSA) -- secure against Shor's algorithm
- **Replay protection:** All vault/DAO messages include bound proposal IDs and signer indices
- **Checks-Effects-Interactions:** State is updated before any external calls to prevent reentrancy
- **Dynamic threshold safety:** Removing signers auto-adjusts the threshold downward to prevent lockouts
- **Misuse-resistant SDK:** Signatures verified at collection time in co-signing sessions
- **No C FFI:** Pure Python SDK (wraps Algorand's deterministic Falcon implementation)

---

## Project Structure

```
algo-pqc-kit/
  algo_pqc_kit/          # PyPI package (import algo_pqc_kit)
    account.py           # FalconAccount -- keypair generation, signing, address derivation
    multisig.py          # FalconMultisig -- M-of-N co-signing sessions
    vault.py             # PQCVault -- deploy and interact with FalconVault
  contracts/             # Puya smart contracts (AVM v12)
    falcon_vault.py      # Enterprise multisig vault
    pqc_dao.py           # DAO governance with timelocks
  scripts/
    deploy.py            # Deployment automation (LocalNet/TestNet/MainNet)
  tests/                 # PyTest suite
  examples/              # Usage examples
```

---

## Relationship to `falcon-multisig`

The cryptographic engine is extracted from [`falcon-multisig`](https://crates.io/crates/falcon-multisig), a production Rust library battle-tested in [QuantaChain](https://github.com/quantachain/quanta) across 80,000+ Falcon-512 consensus blocks. `algo-pqc-kit` is the Algorand integration layer on top of that proven foundation.

---

## License

MIT OR Apache-2.0

---

## Links

| Resource | URL |
|---|---|
| PyPI | https://pypi.org/project/algo-pqc-kit/0.3.1/ |
| crates.io (engine) | https://crates.io/crates/falcon-multisig |
| NIST FIPS 206 | https://csrc.nist.gov/pubs/fips/206/final |
| Algorand PQC Brief | https://algorand.co/blog/technical-brief-quantum-resistant-transactions-on-algorand-with-falcon-signatures |
| AVM v12 opcodes | https://developer.algorand.org/docs/get-details/dapps/avm/teal/opcodes/v12/ |
