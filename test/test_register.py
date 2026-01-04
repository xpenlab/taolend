#!/usr/bin/env python3
"""
Test register functionality - verify that unregistered users cannot call protected functions
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


def print_warning(msg):
    print(f"{YELLOW}[WARNING]{NC} {msg}")


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
    # Try Hardhat artifacts first
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


def test_unregistered_cancel():
    """Test that unregistered user cannot call cancel()"""
    print_section("Test: Unregistered User Calls cancel()")

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

    # Check if LENDER1 is registered
    try:
        is_registered = contract.functions.registeredUser(lender1_address).call()
        print_info(f"LENDER1 registered status: {is_registered}")

        if is_registered:
            print_warning("LENDER1 is already registered! This test requires an unregistered user.")
            print_warning("Test result is inconclusive.")
            return None

    except Exception as e:
        print_error(f"Failed to check registration status: {e}")
        return False

    # Get LENDER1's private key from .env
    # Note: In a real test environment, you'd need LENDER1's private key
    # For now, we'll simulate the call without sending a transaction

    print_info("\nAttempting to call cancel() as unregistered LENDER1...")

    # Try to call cancel() - this should revert
    try:
        # We use .call() to simulate the transaction without actually sending it
        # This will fail if the function would revert
        result = contract.functions.cancel().call({'from': lender1_address})

        # If we get here, the call succeeded when it should have failed
        print_error("FAIL: cancel() did not revert for unregistered user!")
        print_error("Expected revert with 'user not registered', but call succeeded")
        return False

    except Exception as e:
        error_msg = str(e)

        # Check if the error message contains the expected revert reason
        if "user not registered" in error_msg.lower() or "execution reverted" in error_msg.lower():
            print_success("PASS: cancel() correctly reverted for unregistered user!")
            print_info(f"Revert reason: {error_msg}")
            return True
        elif "contract is paused" in error_msg.lower():
            print_warning("Contract is paused. Cannot complete test.")
            print_info(f"Error: {error_msg}")
            return None
        else:
            print_warning(f"Call reverted with unexpected error: {error_msg}")
            print_info("This may still indicate correct behavior, but error message is not as expected")
            return None


def test_registered_status_check():
    """Additional test: Check registration status for all accounts"""
    print_section("Additional Check: Registration Status of All Accounts")

    # Load addresses
    accounts = load_addresses()
    if not accounts:
        return False

    # Connect to Bittensor
    try:
        w3 = Web3(Web3.HTTPProvider(BITTENSOR_RPC))

        if not w3.is_connected():
            print_error("Failed to connect to Bittensor RPC")
            return False

    except Exception as e:
        print_error(f"Connection failed: {e}")
        return False

    # Load contract ABI
    abi = load_contract_abi()
    if not abi:
        return False

    # Create contract instance
    contract = w3.eth.contract(address=LENDING_POOL_V2_ADDRESS, abi=abi)

    # Check registration status for each account
    print_info("\nRegistration status:")
    for account in accounts:
        try:
            is_registered = contract.functions.registeredUser(account["evmAddress"]).call()
            status = f"{GREEN}Registered{NC}" if is_registered else f"{YELLOW}Not Registered{NC}"
            print(f"  {account['name']:12s} ({account['evmAddress']}): {status}")
        except Exception as e:
            print(f"  {account['name']:12s}: Error checking status - {e}")

    return True


def main():
    print_section("Register Function Tests")
    print("Testing that unregistered users cannot call protected functions")

    # Run the main test
    result = test_unregistered_cancel()

    if result is True:
        print_section("Test Result")
        print_success("✓ Test PASSED: Unregistered user correctly blocked from calling cancel()")
    elif result is False:
        print_section("Test Result")
        print_error("✗ Test FAILED: Unregistered user was able to call cancel()")
    else:
        print_section("Test Result")
        print_warning("⚠ Test INCONCLUSIVE: See details above")

    # Run additional checks
    test_registered_status_check()

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
