#!/usr/bin/env python3
"""
Print addresses script - Python version
Generates addresses.json and addresses.md from environment variables
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
from eth_account import Account
from address_utils import convert_h160_to_ss58, ss58_to_public_key, public_key_to_hex


def get_wallet_addresses(private_key: str) -> tuple[str, str, str]:
    """
    Get EVM address, SS58 address, and public key from private key.

    Args:
        private_key: Private key hex string (with or without 0x prefix)

    Returns:
        Tuple of (evm_address, ss58_address, public_key_hex)
    """
    # Create account from private key
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    account = Account.from_key(private_key)
    evm_address = account.address

    # Convert to SS58
    ss58_address = convert_h160_to_ss58(evm_address)

    # Get public key
    public_key_bytes = ss58_to_public_key(ss58_address)
    public_key = public_key_to_hex(public_key_bytes)

    return evm_address, ss58_address, public_key


def main():
    # Load environment variables
    load_dotenv()

    accounts = [
        {"name": "ADMIN", "key": os.getenv("ADMIN_PRIVATE_KEY")},
        {"name": "MANAGER", "key": os.getenv("MANAGER_PRIVATE_KEY")},
        {"name": "TREASURY", "key": os.getenv("TREASURY_PRIVATE_KEY")},
        {"name": "RECEIVER", "key": os.getenv("RECEIVER_PRIVATE_KEY")},
        {"name": "LENDER1", "key": os.getenv("LENDER1_PRIVATE_KEY")},
        {"name": "LENDER2", "key": os.getenv("LENDER2_PRIVATE_KEY")},
        {"name": "LENDER3", "key": os.getenv("LENDER3_PRIVATE_KEY")},
        {"name": "BORROWER1", "key": os.getenv("BORROWER1_PRIVATE_KEY")},
        {"name": "BORROWER2", "key": os.getenv("BORROWER2_PRIVATE_KEY")},
        {"name": "BORROWER3", "key": os.getenv("BORROWER3_PRIVATE_KEY")},
    ]

    print("\n=== Account Addresses ===\n")

    results: List[Dict[str, str]] = []

    for account in accounts:
        name = account["name"]
        key = account["key"]

        if not key:
            print(f"{name}: Private key not found in .env")
            continue

        try:
            evm_address, ss58_address, public_key = get_wallet_addresses(key)

            results.append({
                "name": name,
                "evmAddress": evm_address,
                "ss58Address": ss58_address,
                "publicKey": public_key,
            })

            print(f"{name}:")
            print(f"  EVM:  {evm_address}")
            print(f"  SS58: {ss58_address}")
            print(f"  PK:   {public_key}")
            print()

        except Exception as e:
            print(f"{name}: Error processing private key - {e}")
            continue

    # Save to JSON
    json_output = {
        "generated_at": datetime.now().isoformat(),
        "accounts": results,
    }

    with open("addresses.json", "w") as f:
        json.dump(json_output, f, indent=2)

    print("✅ Saved to addresses.json")


if __name__ == "__main__":
    main()
