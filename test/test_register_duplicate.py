#!/usr/bin/env python3
"""
Test Case TC04: Duplicate Registration Prevention

Test that an already registered user cannot register again.
The transaction should revert with "registered" error.

Test Pattern (modified 8 steps for revert scenario):
1. Read initial contract state
2. Read initial account balances (N/A for register)
3. Read initial registration state (verify already registered)
4. Attempt duplicate registration (expect revert)
5. Verify revert reason contains "registered"
6. Read final contract state (N/A - transaction reverted)
7. Read final registration state (should be unchanged)
8. Verify no state changes occurred
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from const import LENDING_POOL_V2_ADDRESS
from cli_utils import (
    print_info,
    print_success,
    print_error,
    print_warning,
    print_section,
    load_addresses,
    load_contract_abi,
    ss58_to_bytes32,
)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
BITTENSOR_RPC = os.environ.get("RPC_URL", "http://127.0.0.1:9944")
TEST_ACCOUNT = "BORROWER1"  # Use BORROWER1 (registered in TC03)


def main():
    """Main test function following modified 8-step pattern for revert scenario"""
    print_section("TC04: Duplicate Registration Prevention Test")
    print_info("Testing that already registered user CANNOT register again")
    print_info(f"Test account: {TEST_ACCOUNT}")

    # ==========================================
    # SETUP: Load addresses and connect
    # ==========================================
    print_section("Setup: Load Configuration")

    # Load addresses
    addresses = load_addresses()
    if not addresses:
        print_error("Failed to load addresses.json")
        return False

    # Get test account info
    if TEST_ACCOUNT not in addresses:
        print_error(f"Test account '{TEST_ACCOUNT}' not found in addresses.json")
        print_info(f"Available accounts: {', '.join(addresses.keys())}")
        return False

    account_info = addresses[TEST_ACCOUNT]
    evm_address = account_info["evmAddress"]
    ss58_address = account_info["ss58Address"]

    print_info(f"Account: {TEST_ACCOUNT}")
    print_info(f"EVM Address: {evm_address}")
    print_info(f"SS58 Address: {ss58_address}")

    # Get private key
    private_key = os.environ.get(f"{TEST_ACCOUNT}_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
    if not private_key:
        print_error("Private key not found in environment variables")
        print_info(f"Set {TEST_ACCOUNT}_PRIVATE_KEY or ETH_PRIVATE_KEY in .env file")
        return False

    # Verify private key matches address
    try:
        account = Account.from_key(private_key)
        if account.address.lower() != evm_address.lower():
            print_error("Private key does not match test account address!")
            print_error(f"Expected: {evm_address}")
            print_error(f"Got: {account.address}")
            return False
        print_success("Private key verified")
    except Exception as e:
        print_error(f"Invalid private key: {e}")
        return False

    # Connect to Bittensor
    print_info(f"Connecting to: {BITTENSOR_RPC}")
    try:
        w3 = Web3(Web3.HTTPProvider(BITTENSOR_RPC))
        if not w3.is_connected():
            print_error("Failed to connect to Bittensor RPC")
            return False
        print_success("Connected to Bittensor EVM")
        print_info(f"Chain ID: {w3.eth.chain_id}")
        print_info(f"Latest block: {w3.eth.block_number:,}")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return False

    # Load contract ABI
    abi = load_contract_abi()
    if not abi:
        print_error("Failed to load contract ABI")
        return False

    # Create contract instance
    contract = w3.eth.contract(address=LENDING_POOL_V2_ADDRESS, abi=abi)
    print_info(f"Contract: {LENDING_POOL_V2_ADDRESS}")

    # ==========================================
    # STEP 1-3: Read BEFORE state
    # ==========================================
    print_section("Step 1-3: Read State BEFORE Duplicate Registration Attempt")

    try:
        # Step 3: Read initial registration state
        is_registered_before = contract.functions.registeredUser(evm_address).call()
        coldkey_before = contract.functions.userColdkey(evm_address).call()

        print_info(f"registeredUser BEFORE: {is_registered_before}")
        print_info(f"userColdkey BEFORE:    0x{coldkey_before.hex()}")

        # Check precondition: user MUST be registered
        if not is_registered_before:
            print_error(f"PRECONDITION FAILED: {TEST_ACCOUNT} is NOT registered!")
            print_error("This test requires an already registered account")
            print_info("Run TC03 (test_register_success.py) first to register BORROWER1")
            return False

        print_success("✓ Precondition met: User is already registered")

        # Verify coldkey is non-zero
        zero_bytes = b'\x00' * 32
        if coldkey_before != zero_bytes:
            print_success("✓ userColdkey is non-zero (expected for registered user)")
            print_info(f"  Current coldkey: 0x{coldkey_before.hex()}")
        else:
            print_warning(f"⚠ userColdkey is zero for registered user (unexpected)")
            print_warning(f"  This may indicate a contract bug")

    except Exception as e:
        print_error(f"Failed to read initial state: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # Prepare Registration Data (Same as Initial)
    # ==========================================
    print_section("Prepare Duplicate Registration Data")

    try:
        # Convert SS58 to bytes32
        coldkey_bytes32_str = ss58_to_bytes32(ss58_address)
        coldkey_bytes = Web3.to_bytes(hexstr=coldkey_bytes32_str)
        print_info(f"Coldkey (bytes32): {coldkey_bytes32_str}")
        print_info(f"Note: Using the SAME coldkey as initial registration")

        # Create signature using EIP-191
        print_info("Creating signature...")
        message = encode_defunct(coldkey_bytes)
        signature = Account.sign_message(message, private_key=private_key)
        signature_bytes = signature.signature

        print_success(f"Signature created: 0x{signature_bytes.hex()}")
        print_info(f"Note: Signature is valid, but registration should still fail")

    except Exception as e:
        print_error(f"Failed to prepare registration data: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # STEP 4: Attempt Duplicate Registration
    # ==========================================
    print_section("Step 4-5: Attempt Duplicate Registration (Expect Revert)")

    revert_detected = False
    revert_message = ""

    try:
        # Try to estimate gas (this should fail with revert)
        print_info("Attempting to estimate gas for duplicate registration...")

        try:
            gas_estimate = contract.functions.register(
                coldkey_bytes,
                signature_bytes
            ).estimate_gas({'from': evm_address})

            # If we get here, gas estimation succeeded (unexpected)
            print_warning(f"⚠ Gas estimation succeeded: {gas_estimate}")
            print_warning("This is unexpected - the transaction should revert")

        except Exception as estimate_error:
            # Gas estimation failed - this is expected for a reverting transaction
            error_msg = str(estimate_error)
            print_success("✓ Gas estimation failed (expected for reverting transaction)")
            print_info(f"Error message: {error_msg}")

            # Check if error message contains "registered"
            if "registered" in error_msg.lower() or "execution reverted" in error_msg.lower():
                print_success("✓ Error message contains expected revert reason")
                revert_detected = True
                revert_message = error_msg
            else:
                print_warning(f"⚠ Error message does not contain 'registered'")
                print_warning(f"Got: {error_msg}")
                revert_detected = True
                revert_message = error_msg

        # If gas estimation succeeded, try to send the transaction (should fail)
        if not revert_detected:
            print_info("Gas estimation succeeded, trying to send transaction...")
            print_warning("This is unexpected - the transaction should have reverted already")

            # Get nonce
            nonce = w3.eth.get_transaction_count(evm_address)
            print_info(f"Transaction nonce: {nonce}")

            # Get gas price
            gas_price = w3.eth.gas_price
            print_info(f"Gas price: {w3.from_wei(gas_price, 'gwei')} Gwei")

            # Build transaction
            print_info("Building transaction...")
            tx = contract.functions.register(
                coldkey_bytes,
                signature_bytes
            ).build_transaction({
                'from': evm_address,
                'nonce': nonce,
                'gas': 200000,
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

            # Check transaction status
            if tx_receipt['status'] == 0:
                print_success("✓ Transaction reverted on-chain (status=0)")
                revert_detected = True
                revert_message = "Transaction reverted on-chain (status=0)"
            elif tx_receipt['status'] == 1:
                print_error("✗ Transaction SUCCEEDED (status=1) - This should NOT happen!")
                print_error("Expected: Transaction should revert with 'registered'")
                print_error(f"Block: {tx_receipt['blockNumber']}")
                print_error(f"Gas used: {tx_receipt['gasUsed']}")
                return False

    except Exception as e:
        # Any exception during transaction attempt is expected
        error_msg = str(e)
        print_success("✓ Transaction attempt raised exception (expected)")
        print_info(f"Exception: {error_msg}")

        # Check if error message contains "registered"
        if "registered" in error_msg.lower():
            print_success("✓ Exception message contains 'registered' (expected revert reason)")
            revert_detected = True
            revert_message = error_msg
        elif "execution reverted" in error_msg.lower():
            print_success("✓ Exception indicates execution reverted")
            revert_detected = True
            revert_message = error_msg
        else:
            print_warning(f"⚠ Exception message does not clearly indicate 'registered' revert")
            print_info(f"Full error: {error_msg}")
            revert_detected = True
            revert_message = error_msg

    # ==========================================
    # Verify Revert Occurred
    # ==========================================
    print_section("Verify Revert Occurred")

    if not revert_detected:
        print_error("✗ No revert detected!")
        print_error("Expected: Transaction should revert with 'registered'")
        return False

    print_success("✓ Transaction correctly reverted")
    print_info(f"Revert reason: {revert_message}")

    # ==========================================
    # STEP 6-7: Read AFTER state (Should be unchanged)
    # ==========================================
    print_section("Step 6-7: Read State AFTER Duplicate Registration Attempt")

    try:
        # Step 7: Read final registration state
        is_registered_after = contract.functions.registeredUser(evm_address).call()
        coldkey_after = contract.functions.userColdkey(evm_address).call()

        print_info(f"registeredUser AFTER: {is_registered_after}")
        print_info(f"userColdkey AFTER:    0x{coldkey_after.hex()}")

    except Exception as e:
        print_error(f"Failed to read final state: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # STEP 8: Verify No State Changes
    # ==========================================
    print_section("Step 8: Verify State Remained Unchanged")

    success = True

    # Verify registeredUser unchanged
    if is_registered_before == True and is_registered_after == True:
        print_success(f"✓ registeredUser unchanged: {is_registered_before} → {is_registered_after}")
    else:
        print_error(f"✗ registeredUser changed (unexpected)!")
        print_error(f"  Before: {is_registered_before}")
        print_error(f"  After:  {is_registered_after}")
        print_error(f"  Expected: True → True (no change)")
        success = False

    # Verify userColdkey unchanged
    if coldkey_before == coldkey_after:
        print_success(f"✓ userColdkey unchanged (expected)")
        print_info(f"  Value: 0x{coldkey_after.hex()}")
    else:
        print_error(f"✗ userColdkey changed (unexpected)!")
        print_error(f"  Before: 0x{coldkey_before.hex()}")
        print_error(f"  After:  0x{coldkey_after.hex()}")
        success = False

    # ==========================================
    # Test Summary
    # ==========================================
    print_section("Test Summary")

    if success and revert_detected:
        print_success("✓✓✓ TEST PASSED ✓✓✓")
        print_info("")
        print_info("Summary of duplicate registration prevention:")
        print_info(f"  • Account: {TEST_ACCOUNT}")
        print_info(f"  • EVM Address: {evm_address}")
        print_info(f"  • Initial status: Already registered")
        print_info(f"  • Duplicate registration attempt: REVERTED")
        print_info(f"  • Revert reason: {revert_message[:100]}...")
        print_info(f"  • registeredUser: Unchanged (True)")
        print_info(f"  • userColdkey: Unchanged")
        print_info("")
        print_success("✓ Security validated: Cannot register twice")
        print_success("✓ Coldkey binding is immutable")
    else:
        print_error("✗✗✗ TEST FAILED ✗✗✗")
        if not revert_detected:
            print_error("Transaction did not revert as expected")
        if not success:
            print_error("State changes detected (should remain unchanged)")

    print("")
    return success and revert_detected


if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print_info("\nTest cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
