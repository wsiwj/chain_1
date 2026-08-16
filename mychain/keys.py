"""Signatures: proving WHO wrote a record.

Hash-linking (block.py) proves history wasn't EDITED — but not who wrote
it. For that, each record is signed with a private key:

  - private key: a secret number only the agent knows
  - signature:   made from (private key + record fingerprint); it is
                 mathematically impossible to forge without the secret
  - address:     derived from the key pair; acts as the signer's identity

We use the exact same cryptography as Ethereum (secp256k1, via the
eth_keys library that ships with web3.py). Nice consequence: your agent
has THE SAME address on this chain as on the EVM chain — 0xf39F...

Ethereum-style trick: the signature alone lets you RECOVER the signer's
address. So records don't need to carry a public key — verify by
recovering the address from the signature and checking it's authorized.
"""

from eth_keys import keys


def address_of(private_key_hex: str) -> str:
    """Derive the public address from a private key."""
    pk = keys.PrivateKey(bytes.fromhex(private_key_hex.removeprefix("0x")))
    return pk.public_key.to_checksum_address()


def sign(private_key_hex: str, msg_hash: bytes) -> str:
    """Sign a 32-byte fingerprint. Returns the signature as hex."""
    pk = keys.PrivateKey(bytes.fromhex(private_key_hex.removeprefix("0x")))
    return pk.sign_msg_hash(msg_hash).to_hex()


def recover_signer(signature_hex: str, msg_hash: bytes) -> str:
    """Given a signature + the fingerprint it signed, reveal WHO signed.
    A forged or tampered signature yields a garbage address that won't
    match any authorized agent — so forgery simply fails authorization."""
    sig = keys.Signature(bytes.fromhex(signature_hex.removeprefix("0x")))
    return sig.recover_public_key_from_msg_hash(msg_hash).to_checksum_address()
