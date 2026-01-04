#!/usr/bin/env python3
"""
Test that registered users CAN call protected functions
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3
from eth_account import Account

# Add parent directory to path to import const
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from const import LENDING_POOL_V2_ADDRESS
from balance_utils import rao_to_tao, format_tao

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
BITTENSOR_RPC = os.environ.get("RPC_URL", "http://127.0.0.1:9944")

# ANSI Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;36m"
NC = "\033[0m"


def print_info(msg):
    print(f"{BLUE}[INFO]{NC} {msg}")


def print_success(msg):
    print(f"{GREEN}[SUCCESS]{NC} {msg}")


def print_error(msg):
    print(f"{RED}[ERROR]{NC} {msg}")


def print_section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def load_addresses():
    """Load addresses from addresses.json"""
    addresses_path = Path(__file__).parent.parent / "addresses.json"
    if not addresses_path.exists():
        print_error("addresses.json not found")
        return None

    try:
        with open(addresses_path, "r") as f:
            data = json.load(f)
        return data["accounts"]
    except Exception as e:
        print_error(f"Failed to load addresses.json: {e}")
        return None


def load_contract_abi():
    """Load contract ABI"""
    artifacts_path = Path(__file__).parent.parent / "artifacts/contracts/LendingPoolV2.sol/LendingPoolV2.json"

    if not artifacts_path.exists():
        print_error(f"Contract artifacts not found at {artifacts_path}")
        print_info("Please run 'npm run build' first")
        return None

    try:
        with open(artifacts_path, "r") as f:
            artifacts = json.load(f)
        return artifacts["abi"]
    except Exception as e:
        print_error(f"Failed to load ABI: {e}")
        return None


def test_registered_can_call_cancel():
    """Test that registered user CAN call cancel() and verify state changes"""
    print_section("Test: Registered User Calls cancel()")

    # Load addresses
    accounts = load_addresses()
    if not accounts:
        return False

    # Get LENDER1 info
    lender1 = next((acc for acc in accounts if acc["name"] == "LENDER1"), None)
    if not lender1:
        print_error("LENDER1 not found in addresses.json")
        return False

    lender1_address = lender1["evmAddress"]
    print_info(f"LENDER1 address: {lender1_address}")

    # Get private key (prioritize account-specific key)
    private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
    if not private_key:
        print_error("Private key not found in environment variables")
        print_info("Set LENDER1_PRIVATE_KEY or ETH_PRIVATE_KEY in .env file")
        return False

    # Verify private key matches address
    try:
        account = Account.from_key(private_key)
        if account.address.lower() != lender1_address.lower():
            print_error("Private key does not match LENDER1 address!")
            return False
    except Exception as e:
        print_error(f"Invalid private key: {e}")
        return False

    # Connect to Bittensor
    try:
        w3 = Web3(Web3.HTTPProvider(BITTENSOR_RPC))

        if not w3.is_connected():
            print_error("Failed to connect to Bittensor RPC")
            return False

        print_success(f"Connected to Bittensor")
        print_info(f"Chain ID: {w3.eth.chain_id}")

    except Exception as e:
        print_error(f"Connection failed: {e}")
        return False

    # Load contract ABI
    abi = load_contract_abi()
    if not abi:
        return False

    # Create contract instance
    contract = w3.eth.contract(address=LENDING_POOL_V2_ADDRESS, abi=abi)
    print_info(f"Contract address: {LENDING_POOL_V2_ADDRESS}")

    # === BEFORE CANCEL: Read state ===
    print_section("State BEFORE cancel()")
    try:
        is_registered = contract.functions.registeredUser(lender1_address).call()
        print_info(f"LENDER1 registered status: {is_registered}")

        if not is_registered:
            print_error("LENDER1 is not registered! This test requires a registered user.")
            print_info("Run: python3 scripts/cli.py register --account LENDER1")
            return False

        # Read state before cancel
        nonce_before = contract.functions.lenderNonce(lender1_address).call()
        coldkey_before = contract.functions.userColdkey(lender1_address).call()

        print_info(f"lenderNonce BEFORE: {nonce_before}")
        print_info(f"userColdkey BEFORE: 0x{coldkey_before.hex()}")

        # Check if coldkey is zero
        if coldkey_before == b'\x00' * 32:
            print_warning("userColdkey is zero (0x00...00)")
        else:
            print_success(f"userColdkey is non-zero (registered)")

    except Exception as e:
        print_error(f"Failed to read state before cancel: {e}")
        return False

    # === SEND CANCEL TRANSACTION ===
    print_section("Sending cancel() Transaction")
    print_info("Building and sending cancel() transaction...")

    try:
        # Get nonce for transaction
        tx_nonce = w3.eth.get_transaction_count(lender1_address)
        print_info(f"Transaction nonce: {tx_nonce}")

        # Get gas price
        gas_price = w3.eth.gas_price
        print_info(f"Gas price: {w3.from_wei(gas_price, 'gwei')} Gwei")

        # Build transaction
        tx = contract.functions.cancel().build_transaction({
            'from': lender1_address,
            'nonce': tx_nonce,
            'gas': 100000,
            'gasPrice': gas_price,
        })

        # Sign transaction
        print_info("Signing transaction...")
        signed_txn = w3.eth.account.sign_transaction(tx, private_key)

        # Send transaction
        print_info("Sending transaction...")
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        print_info(f"Transaction hash: 0x{tx_hash.hex()}")

        # Wait for receipt
        print_info("Waiting for confirmation...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if tx_receipt['status'] == 1:
            print_success("Transaction successful!")
            print_info(f"Block number: {tx_receipt['blockNumber']}")
            print_info(f"Gas used: {tx_receipt['gasUsed']:,}")
        else:
            print_error("Transaction failed!")
            return False

    except Exception as e:
        error_msg = str(e)
        if "user not registered" in error_msg.lower():
            print_error("FAIL: cancel() reverted with 'user not registered'")
            return False
        elif "contract is paused" in error_msg.lower():
            print_error("Contract is paused. Cannot complete test.")
            return None
        else:
            print_error(f"Transaction failed: {error_msg}")
            import traceback
            traceback.print_exc()
            return False

    # === AFTER CANCEL: Read state ===
    print_section("State AFTER cancel()")
    try:
        # Read state after cancel
        nonce_after = contract.functions.lenderNonce(lender1_address).call()
        coldkey_after = contract.functions.userColdkey(lender1_address).call()

        print_info(f"lenderNonce AFTER:  {nonce_after}")
        print_info(f"userColdkey AFTER:  0x{coldkey_after.hex()}")

    except Exception as e:
        print_error(f"Failed to read state after cancel: {e}")
        return False

    # === VERIFY STATE CHANGES ===
    print_section("Verification")

    success = True

    # Check nonce increment
    if nonce_after == nonce_before + 1:
        print_success(f"✓ lenderNonce incremented: {nonce_before} → {nonce_after}")
    else:
        print_error(f"✗ lenderNonce NOT incremented: {nonce_before} → {nonce_after}")
        print_error(f"  Expected: {nonce_before + 1}, Got: {nonce_after}")
        success = False

    # Check coldkey unchanged (should remain the same before and after cancel)
    if coldkey_after == coldkey_before:
        print_success(f"✓ userColdkey unchanged (expected behavior)")
        if coldkey_after != b'\x00' * 32:
            print_success(f"✓ userColdkey is non-zero (0x{coldkey_after.hex()})")
        else:
            print_warning(f"⚠ userColdkey is still zero")
    else:
        print_warning(f"⚠ userColdkey changed (unexpected)")
        print_info(f"  Before: 0x{coldkey_before.hex()}")
        print_info(f"  After:  0x{coldkey_after.hex()}")

    return success


def main():
    print_section("Registered User Function Tests")
    print("Testing that registered users CAN call protected functions")

    # Run the test
    result = test_registered_can_call_cancel()

    print_section("Test Result")
    if result is True:
        print_success("✓ Test PASSED: Registered user can call cancel()")
        print_info("This confirms that the registration process works correctly")
    elif result is False:
        print_error("✗ Test FAILED: Registered user cannot call cancel()")
    else:
        print_error("⚠ Test INCONCLUSIVE: See details above")

    print("\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_info("\nTest cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
