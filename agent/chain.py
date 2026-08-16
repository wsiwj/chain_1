"""The hand that writes in the notebook: talks to the EventLedger contract.

Uses web3.py to sign transactions with the agent's key and send them to
whatever chain RPC_URL points at (anvil now, the Pi's chain later).
"""

import hashlib
import json

from web3 import Web3

from config import RPC_URL, AGENT_KEY, CONTRACT_ADDRESS, ABI_PATH


def sha256_of(data: bytes) -> bytes:
    """Fingerprint of the raw evidence. 32 bytes, matches bytes32 on-chain."""
    return hashlib.sha256(data).digest()


class Ledger:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise ConnectionError(f"No blockchain at {RPC_URL} — is anvil running?")

        if not CONTRACT_ADDRESS:
            raise ValueError("CONTRACT_ADDRESS not set — deploy first, then export it.")

        # The ABI (the contract's "menu of functions") comes straight from
        # Foundry's build output, so it can never drift from the Solidity.
        artifact = json.loads(ABI_PATH.read_text())
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=artifact["abi"],
        )
        self.account = self.w3.eth.account.from_key(AGENT_KEY)

    def _send(self, fn) -> str:
        """Sign a contract call with the agent key, send it, wait for receipt."""
        tx = fn.build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt.status != 1:
            raise RuntimeError(f"transaction reverted: {tx_hash.hex()}")
        return tx_hash.hex()

    # --- the only three things the agent can do on-chain ---

    def log_event(self, evidence: bytes, label: str) -> str:
        h = sha256_of(evidence)
        return self._send(self.contract.functions.logEvent(h, label))

    def decide_access(self, subject: str, allowed: bool, evidence: bytes, label: str) -> str:
        h = sha256_of(evidence)
        return self._send(
            self.contract.functions.decideAccess(
                Web3.to_checksum_address(subject), allowed, h, label
            )
        )

    # --- reading back (free) ---

    def event_count(self) -> int:
        return self.contract.functions.eventCount().call()

    def get_event(self, event_id: int):
        return self.contract.functions.getEvent(event_id).call()

    def is_allowed(self, subject: str) -> bool:
        return self.contract.functions.isAllowed(Web3.to_checksum_address(subject)).call()
