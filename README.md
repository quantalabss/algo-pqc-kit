# algo-pqc-kit

**The first complete Algorand-native post-quantum cryptography developer toolkit.**

[![PyPI](https://img.shields.io/pypi/v/algo-pqc-kit)](https://pypi.org/project/algo-pqc-kit)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue)](LICENSE-MIT)
[![AVM](https://img.shields.io/badge/AVM-v12-green)](https://developer.algorand.org)
[![PQC](https://img.shields.io/badge/crypto-Falcon--1024%20%7C%20FN--DSA-purple)](https://csrc.nist.gov/pubs/fips/206/final)

---

## What Is This?

Algorand's AVM v12 (deployed November 2025) introduced the `falcon_verify` opcode — enabling **on-chain Falcon-1024 post-quantum signature verification**. But there was no developer toolkit to make it usable.

`algo-pqc-kit` fills that gap:

| Layer | What It Does |
|---|---|
| **Puya Smart Contracts** | `FalconVault` (M-of-N PQC vault), `FalconLsig` (PQC account), `PQCDao` (PQC governance) |
| **Python SDK** | `FalconAccount`, `FalconMultisig` — generate keys, derive addresses, sign, co-sign |
| **AlgoKit Plugin** | `algokit generate pqc-vault` — scaffold a full PQC vault in one command |

---

## Quick Start

```bash
pip install algo-pqc-kit
```

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

Three ARC-4 contracts, all using the AVM `falcon_verify` opcode:

### `FalconVault` — M-of-N Post-Quantum Treasury

```bash
cd contracts/
puyapy falcon_vault.py  # compiles to TEAL + ABI
algokit deploy          # deploys to Testnet
```

A treasury that releases ALGO or ASAs only when M-of-N Falcon-1024 signatures are verified **on-chain**. Uses replay-protected nonces. Immutable committee — no admin backdoor.

### `FalconLsig` — PQC Logic Signature Account

The foundational primitive: a Logic Signature that embeds a Falcon-1024 public key and gates all spending via `falcon_verify`. This is how Algorand PQC accounts work.

### `PQCDao` — Post-Quantum DAO Governance

A complete DAO where every spending proposal requires M-of-N committee members to sign with their Falcon-1024 keys. No Ed25519 anywhere in the governance flow.

---

## Testnet Deployments

> Contracts verified on Algorand Testnet — check the [deployments](docs/deployments.md) page for live app IDs and transaction links.

---

## AlgoKit Plugin (Coming in v0.2)

```bash
algokit generate pqc-vault
```

Scaffolds a complete PQC vault project: keypairs, contracts, deployment scripts — zero configuration required.

---

## How It Works

### The AVM `falcon_verify` Opcode

```
falcon_verify(data: []byte, sig: [1232]byte, pubkey: [1793]byte) → bool
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

---

## Security

- **Quantum-resistant:** Falcon-1024 (NIST FN-DSA) — secure against Shor's algorithm
- **Replay protection:** All vault/DAO messages include a nonce
- **No admin key:** Contracts are immutable after deployment
- **Misuse-resistant SDK:** Signatures verified at collection time in co-signing sessions
- **No C FFI:** Pure Python SDK (wraps Algorand's deterministic Falcon implementation)

---

## Relationship to `falcon-multisig`

The cryptographic engine is extracted from [`falcon-multisig`](https://crates.io/crates/falcon-multisig) — a production Rust library battle-tested in [QuantaChain](https://github.com/quantachain/quanta) across 80,000+ Falcon-512 consensus blocks. `algo-pqc-kit` is the Algorand integration layer on top of that proven foundation.

---

## License

MIT OR Apache-2.0

---

## Links

| Resource | URL |
|---|---|
| PyPI | https://pypi.org/project/algo-pqc-kit |
| crates.io (engine) | https://crates.io/crates/falcon-multisig |
| NIST FIPS 206 | https://csrc.nist.gov/pubs/fips/206/final |
| Algorand PQC Brief | https://algorand.co/blog/technical-brief-quantum-resistant-transactions-on-algorand-with-falcon-signatures |
| AVM v12 opcodes | https://developer.algorand.org/docs/get-details/dapps/avm/teal/opcodes/v12/ |
