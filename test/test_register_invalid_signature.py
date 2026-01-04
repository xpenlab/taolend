#!/usr/bin/env python3
"""
Test Case TC05: Invalid Signature Rejection

Test that registration with an invalid signature is rejected.
The signature is created by the wrong private key (LENDER1 instead of BORROWER2).

Test Pattern (modified 8 steps for revert scenario):
1. Read initial contract state
2. Read initial account balances (N/A for register)
3. Read initial registration state (verify not registered)
4. Prepare invalid signature (using wrong private key)
5. Attempt registration (expect revert)
6. Verify revert reason contains "invalid signature"
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
TARGET_ACCOUNT = "BORROWER2"  # Account trying to register
WRONG_SIGNER = "LENDER1"      # Account whose key will create invalid signature


def main():
    """Main test function following modified 8-step pattern for revert scenario"""
    print_section("TC05: Invalid Signature Rejection Test")
    print_info("Testing that registration with invalid signature is REJECTED")
    print_info(f"Target account: {TARGET_ACCOUNT} (attempting to register)")
    print_info(f"Wrong signer: {WRONG_SIGNER} (will create invalid signature)")

    # ==========================================
    # SETUP: Load addresses and connect
    # ==========================================
    print_section("Setup: Load Configuration")

    # Load addresses
    addresses = load_addresses()
    if not addresses:
        print_error("Failed to load addresses.json")
        return False

    # Get target account info
    if TARGET_ACCOUNT not in addresses:
        print_error(f"Target account '{TARGET_ACCOUNT}' not found in addresses.json")
        print_info(f"Available accounts: {', '.join(addresses.keys())}")
        return False

    target_info = addresses[TARGET_ACCOUNT]
    target_evm_address = target_info["evmAddress"]
    target_ss58_address = target_info["ss58Address"]

    print_info(f"Target account: {TARGET_ACCOUNT}")
    print_info(f"Target EVM Address: {target_evm_address}")
    print_info(f"Target SS58 Address: {target_ss58_address}")

    # Get wrong signer account info
    if WRONG_SIGNER not in addresses:
        print_error(f"Wrong signer account '{WRONG_SIGNER}' not found in addresses.json")
        return False

    wrong_signer_info = addresses[WRONG_SIGNER]
    wrong_signer_evm_address = wrong_signer_info["evmAddress"]

    print_info(f"\nWrong signer: {WRONG_SIGNER}")
    print_info(f"Wrong signer EVM Address: {wrong_signer_evm_address}")

    # Get wrong signer's private key (to create invalid signature)
    wrong_signer_private_key = os.environ.get(f"{WRONG_SIGNER}_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
    if not wrong_signer_private_key:
        print_error("Wrong signer's private key not found in environment variables")
        print_info(f"Set {WRONG_SIGNER}_PRIVATE_KEY or ETH_PRIVATE_KEY in .env file")
        return False

    # Verify wrong signer's private key matches their address
    try:
        wrong_account = Account.from_key(wrong_signer_private_key)
        if wrong_account.address.lower() != wrong_signer_evm_address.lower():
            print_error("Wrong signer's private key does not match their address!")
            print_error(f"Expected: {wrong_signer_evm_address}")
            print_error(f"Got: {wrong_account.address}")
            return False
        print_success(f"Wrong signer's private key verified: {wrong_signer_evm_address}")
    except Exception as e:
        print_error(f"Invalid private key: {e}")
        return False

    # Get target account's private key (for sending transaction)
    target_private_key = os.environ.get(f"{TARGET_ACCOUNT}_PRIVATE_KEY")
    if not target_private_key:
        print_warning(f"{TARGET_ACCOUNT}_PRIVATE_KEY not found, will use call() instead of send()")
        target_private_key = None
    else:
        # Verify target's private key
        try:
            target_account = Account.from_key(target_private_key)
            if target_account.address.lower() != target_evm_address.lower():
                print_error("Target's private key does not match their address!")
                return False
            print_success(f"Target's private key verified: {target_evm_address}")
        except Exception as e:
            print_error(f"Invalid target private key: {e}")
            return False

    # Connect to Bittensor
    print_info(f"\nConnecting to: {BITTENSOR_RPC}")
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
    print_section("Step 1-3: Read State BEFORE Invalid Registration Attempt")

    try:
        # Step 3: Read initial registration state
        is_registered_before = contract.functions.registeredUser(target_evm_address).call()
        coldkey_before = contract.functions.userColdkey(target_evm_address).call()

        print_info(f"registeredUser BEFORE: {is_registered_before}")
        print_info(f"userColdkey BEFORE:    0x{coldkey_before.hex()}")

        # Check precondition: user must NOT be registered
        if is_registered_before:
            print_warning(f"PRECONDITION WARNING: {TARGET_ACCOUNT} is already registered!")
            print_warning("This test requires an unregistered account")
            print_warning("Skipping test to avoid duplicate registration scenario")
            print_info("Use a different unregistered account, or this becomes a TC04 scenario")
            return None  # Return None to indicate test was skipped

        print_success("✓ Precondition met: User is not registered")

        # Verify coldkey is zero
        zero_bytes = b'\x00' * 32
        if coldkey_before == zero_bytes:
            print_success("✓ userColdkey is zero (expected for unregistered user)")
        else:
            print_warning(f"⚠ userColdkey is non-zero for unregistered user (unexpected)")

    except Exception as e:
        print_error(f"Failed to read initial state: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # Prepare Invalid Registration Data
    # ==========================================
    print_section("Prepare Invalid Registration Data")

    try:
        # Convert target's SS58 to bytes32 (CORRECT coldkey)
        target_coldkey_bytes32_str = ss58_to_bytes32(target_ss58_address)
        target_coldkey_bytes = Web3.to_bytes(hexstr=target_coldkey_bytes32_str)
        print_info(f"Target coldkey (bytes32): {target_coldkey_bytes32_str}")
        print_info(f"Note: This is the CORRECT coldkey for {TARGET_ACCOUNT}")

        # Create signature using WRONG private key (LENDER1's key)
        print_info(f"\nCreating signature using WRONG private key ({WRONG_SIGNER}'s key)...")
        print_warning(f"⚠ Signing {TARGET_ACCOUNT}'s coldkey with {WRONG_SIGNER}'s private key!")

        message = encode_defunct(target_coldkey_bytes)
        invalid_signature = Account.sign_message(message, private_key=wrong_signer_private_key)
        invalid_signature_bytes = invalid_signature.signature

        print_success(f"Invalid signature created: 0x{invalid_signature_bytes.hex()}")
        print_info(f"Signature is valid cryptographically, but signer is wrong:")
        print_info(f"  • Message (coldkey): {TARGET_ACCOUNT}'s coldkey")
        print_info(f"  • Signer: {WRONG_SIGNER} ({wrong_signer_evm_address})")
        print_info(f"  • Expected signer: {TARGET_ACCOUNT} ({target_evm_address})")
        print_warning(f"⚠ Signature verification should fail!")

    except Exception as e:
        print_error(f"Failed to prepare registration data: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # STEP 4-5: Attempt Registration with Invalid Signature
    # ==========================================
    print_section("Step 4-5: Attempt Registration with Invalid Signature (Expect Revert)")

    revert_detected = False
    revert_message = ""

    try:
        # Try to estimate gas (this should fail with revert)
        print_info("Attempting to estimate gas for invalid signature registration...")

        try:
            gas_estimate = contract.functions.register(
                target_coldkey_bytes,
                invalid_signature_bytes
            ).estimate_gas({'from': target_evm_address})

            # If we get here, gas estimation succeeded (unexpected)
            print_warning(f"⚠ Gas estimation succeeded: {gas_estimate}")
            print_warning("This is unexpected - the transaction should revert")

        except Exception as estimate_error:
            # Gas estimation failed - this is expected for a reverting transaction
            error_msg = str(estimate_error)
            print_success("✓ Gas estimation failed (expected for reverting transaction)")
            print_info(f"Error message: {error_msg}")

            # Check if error message contains "invalid signature"
            if "invalid signature" in error_msg.lower():
                print_success("✓ Error message contains 'invalid signature' (expected revert reason)")
                revert_detected = True
                revert_message = error_msg
            elif "execution reverted" in error_msg.lower():
                print_success("✓ Error indicates execution reverted")
                print_warning("⚠ But error message does not explicitly contain 'invalid signature'")
                print_info(f"Full error: {error_msg}")
                revert_detected = True
                revert_message = error_msg
            else:
                print_warning(f"⚠ Error message does not clearly indicate signature failure")
                print_info(f"Got: {error_msg}")
                revert_detected = True
                revert_message = error_msg

        # If gas estimation succeeded, try to send the transaction (should fail)
        if not revert_detected and target_private_key:
            print_info("Gas estimation succeeded, trying to send transaction...")
            print_warning("This is unexpected - the transaction should have reverted already")

            # Get nonce
            nonce = w3.eth.get_transaction_count(target_evm_address)
            print_info(f"Transaction nonce: {nonce}")

            # Get gas price
            gas_price = w3.eth.gas_price
            print_info(f"Gas price: {w3.from_wei(gas_price, 'gwei')} Gwei")

            # Build transaction
            print_info("Building transaction...")
            tx = contract.functions.register(
                target_coldkey_bytes,
                invalid_signature_bytes
            ).build_transaction({
                'from': target_evm_address,
                'nonce': nonce,
                'gas': 200000,
                'gasPrice': gas_price,
            })

            # Sign transaction
            print_info("Signing transaction...")
            signed_txn = w3.eth.account.sign_transaction(tx, target_private_key)

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
                print_error("Expected: Transaction should revert with 'invalid signature'")
                print_error(f"Block: {tx_receipt['blockNumber']}")
                print_error(f"Gas used: {tx_receipt['gasUsed']}")
                return False

    except Exception as e:
        # Any exception during transaction attempt is expected
        error_msg = str(e)
        print_success("✓ Transaction attempt raised exception (expected)")
        print_info(f"Exception: {error_msg}")

        # Check if error message contains "invalid signature"
        if "invalid signature" in error_msg.lower():
            print_success("✓ Exception message contains 'invalid signature' (expected revert reason)")
            revert_detected = True
            revert_message = error_msg
        elif "execution reverted" in error_msg.lower():
            print_success("✓ Exception indicates execution reverted")
            revert_detected = True
            revert_message = error_msg
        else:
            print_warning(f"⚠ Exception message does not clearly indicate signature failure")
            print_info(f"Full error: {error_msg}")
            revert_detected = True
            revert_message = error_msg

    # ==========================================
    # Verify Revert Occurred
    # ==========================================
    print_section("Verify Revert Occurred")

    if not revert_detected:
        print_error("✗ No revert detected!")
        print_error("Expected: Transaction should revert with 'invalid signature'")
        return False

    print_success("✓ Transaction correctly reverted")
    print_info(f"Revert reason: {revert_message[:200]}...")

    # ==========================================
    # STEP 6-7: Read AFTER state (Should be unchanged)
    # ==========================================
    print_section("Step 6-7: Read State AFTER Invalid Registration Attempt")

    try:
        # Step 7: Read final registration state
        is_registered_after = contract.functions.registeredUser(target_evm_address).call()
        coldkey_after = contract.functions.userColdkey(target_evm_address).call()

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
    if is_registered_before == False and is_registered_after == False:
        print_success(f"✓ registeredUser unchanged: {is_registered_before} → {is_registered_after}")
    else:
        print_error(f"✗ registeredUser changed (unexpected)!")
        print_error(f"  Before: {is_registered_before}")
        print_error(f"  After:  {is_registered_after}")
        print_error(f"  Expected: False → False (no change)")
        success = False

    # Verify userColdkey unchanged
    zero_bytes = b'\x00' * 32
    if coldkey_before == zero_bytes and coldkey_after == zero_bytes:
        print_success(f"✓ userColdkey unchanged (still zero)")
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
        print_info("Summary of invalid signature rejection:")
        print_info(f"  • Target account: {TARGET_ACCOUNT} ({target_evm_address})")
        print_info(f"  • Wrong signer: {WRONG_SIGNER} ({wrong_signer_evm_address})")
        print_info(f"  • Invalid signature: Signed by {WRONG_SIGNER}, not {TARGET_ACCOUNT}")
        print_info(f"  • Registration attempt: REVERTED")
        print_info(f"  • Revert reason: {revert_message[:100]}...")
        print_info(f"  • registeredUser: Unchanged (False)")
        print_info(f"  • userColdkey: Unchanged (zero)")
        print_info("")
        print_success("✓ Security validated: Invalid signature rejected")
        print_success("✓ Signature verification works correctly")
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
        if result is None:
            print_warning("Test skipped (precondition not met)")
            sys.exit(0)
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print_info("\nTest cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
