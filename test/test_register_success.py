#!/usr/bin/env python3
"""
Test Case TC03: Successful Registration Flow

Test that an unregistered user can successfully register with the contract
by providing valid coldkey and signature.

Test Pattern (8 steps):
1. Read initial contract state
2. Read initial account balances (N/A for register)
3. Read initial registration state
4. Execute registration operation
5. Read final contract state
6. Read final account balances (N/A for register)
7. Read final registration state
8. Verify state changes and event emission
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
    bytes32_to_ss58,
)
from address_utils import convert_h160_to_ss58

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
BITTENSOR_RPC = os.environ.get("RPC_URL", "http://127.0.0.1:9944")
TEST_ACCOUNT = "BORROWER1"  # Use BORROWER1 for this test


def main():
    """Main test function following 8-step pattern"""
    print_section("TC03: Successful Registration Flow Test")
    print_info("Testing that unregistered user can successfully register")
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
    print_section("Step 1-3: Read State BEFORE Registration")

    try:
        # Step 3: Read initial registration state
        is_registered_before = contract.functions.registeredUser(evm_address).call()
        coldkey_before = contract.functions.userColdkey(evm_address).call()

        print_info(f"registeredUser BEFORE: {is_registered_before}")
        print_info(f"userColdkey BEFORE:    0x{coldkey_before.hex()}")

        # Check precondition: user must NOT be registered
        if is_registered_before:
            print_error(f"PRECONDITION FAILED: {TEST_ACCOUNT} is already registered!")
            print_error("This test requires an unregistered account")
            print_info("To fix: Use a different account or reset the contract")
            return False

        print_success("✓ Precondition met: User is not registered")

        # Verify coldkey is zero
        zero_bytes = b'\x00' * 32
        if coldkey_before == zero_bytes:
            print_success("✓ userColdkey is zero (expected for unregistered user)")
        else:
            print_warning(f"⚠ userColdkey is non-zero for unregistered user (unexpected)")
            print_warning(f"  Value: 0x{coldkey_before.hex()}")

    except Exception as e:
        print_error(f"Failed to read initial state: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # Prepare Registration Data
    # ==========================================
    print_section("Prepare Registration Data")

    try:
        # Convert SS58 to bytes32
        coldkey_bytes32_str = ss58_to_bytes32(ss58_address)
        coldkey_bytes = Web3.to_bytes(hexstr=coldkey_bytes32_str)
        print_info(f"Coldkey (bytes32): {coldkey_bytes32_str}")

        # Create signature using EIP-191
        print_info("Creating signature...")
        message = encode_defunct(coldkey_bytes)
        signature = Account.sign_message(message, private_key=private_key)
        signature_bytes = signature.signature

        print_success(f"Signature created: 0x{signature_bytes.hex()}")
        print_info(f"Signature length: {len(signature_bytes)} bytes")

    except Exception as e:
        print_error(f"Failed to prepare registration data: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # STEP 4: Execute Registration
    # ==========================================
    print_section("Step 4: Execute Registration Transaction")

    try:
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
        if tx_receipt['status'] != 1:
            print_error("✗ Transaction FAILED!")
            print_error(f"Status: {tx_receipt['status']}")
            return False

        print_success("✓ Transaction succeeded (status=1)")
        print_info(f"Block number: {tx_receipt['blockNumber']:,}")
        print_info(f"Gas used: {tx_receipt['gasUsed']:,}")

        # Store transaction details for verification
        tx_details = {
            'hash': tx_hash.hex(),
            'block': tx_receipt['blockNumber'],
            'gas_used': tx_receipt['gasUsed'],
        }

    except Exception as e:
        print_error(f"Transaction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # Parse RegisterUser Event
    # ==========================================
    print_section("Step 5: Parse RegisterUser Event")

    try:
        register_user_logs = contract.events.RegisterUser().process_receipt(tx_receipt)

        if len(register_user_logs) == 0:
            print_error("✗ No RegisterUser event found!")
            print_error("Expected RegisterUser event to be emitted")
            return False

        if len(register_user_logs) > 1:
            print_warning(f"⚠ Multiple RegisterUser events found: {len(register_user_logs)}")

        # Parse first event
        event = register_user_logs[0]['args']
        event_user = event['user']
        event_coldkey = event['coldkey']

        print_success("✓ RegisterUser event emitted")
        print_info(f"  Event: RegisterUser(")
        print_info(f"    user:    {event_user}")
        print_info(f"    coldkey: 0x{event_coldkey.hex()}")
        print_info(f"  )")

        # Verify event parameters
        event_valid = True

        if event_user.lower() != evm_address.lower():
            print_error(f"✗ Event 'user' mismatch!")
            print_error(f"  Expected: {evm_address}")
            print_error(f"  Got:      {event_user}")
            event_valid = False
        else:
            print_success(f"✓ Event 'user' matches: {event_user}")

        if event_coldkey != coldkey_bytes:
            print_error(f"✗ Event 'coldkey' mismatch!")
            print_error(f"  Expected: 0x{coldkey_bytes.hex()}")
            print_error(f"  Got:      0x{event_coldkey.hex()}")
            event_valid = False
        else:
            print_success(f"✓ Event 'coldkey' matches")

        if not event_valid:
            print_error("✗ Event validation failed")
            return False

    except Exception as e:
        print_error(f"Failed to parse RegisterUser event: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ==========================================
    # STEP 6-7: Read AFTER state
    # ==========================================
    print_section("Step 6-7: Read State AFTER Registration")

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
    # STEP 8: Verify State Changes
    # ==========================================
    print_section("Step 8: Verify State Changes")

    success = True

    # Verify registeredUser changed from false to true
    if is_registered_before == False and is_registered_after == True:
        print_success(f"✓ registeredUser changed: {is_registered_before} → {is_registered_after}")
    else:
        print_error(f"✗ registeredUser NOT changed correctly!")
        print_error(f"  Before: {is_registered_before}")
        print_error(f"  After:  {is_registered_after}")
        print_error(f"  Expected: False → True")
        success = False

    # Verify userColdkey changed from zero to coldkey_bytes
    zero_bytes = b'\x00' * 32
    if coldkey_before == zero_bytes and coldkey_after == coldkey_bytes:
        print_success(f"✓ userColdkey changed from zero to coldkey")
        print_info(f"  Before: 0x{coldkey_before.hex()}")
        print_info(f"  After:  0x{coldkey_after.hex()}")
    else:
        print_error(f"✗ userColdkey NOT changed correctly!")
        print_error(f"  Before: 0x{coldkey_before.hex()}")
        print_error(f"  After:  0x{coldkey_after.hex()}")
        print_error(f"  Expected: 0x{coldkey_bytes.hex()}")
        success = False

    # ==========================================
    # Additional Verification: SS58 Address
    # ==========================================
    print_section("Additional Verification: SS58 Address")

    try:
        # Convert stored coldkey back to SS58
        stored_ss58 = bytes32_to_ss58(coldkey_after)
        if stored_ss58:
            print_info(f"Stored coldkey as SS58: {stored_ss58}")

            # Compare with original SS58
            if stored_ss58 == ss58_address:
                print_success(f"✓ Stored SS58 matches original: {ss58_address}")
            else:
                print_error(f"✗ Stored SS58 does NOT match original!")
                print_error(f"  Expected: {ss58_address}")
                print_error(f"  Got:      {stored_ss58}")
                success = False
        else:
            print_warning("⚠ Could not convert stored coldkey to SS58")

        # Verify derived SS58 from EVM address
        derived_ss58 = convert_h160_to_ss58(evm_address)
        print_info(f"Derived SS58 from EVM: {derived_ss58}")

        if derived_ss58 == ss58_address:
            print_success(f"✓ Derived SS58 matches original")
        else:
            print_warning(f"⚠ Derived SS58 does NOT match original")
            print_warning(f"  This is OK if addresses.json uses a different derivation method")

    except Exception as e:
        print_warning(f"⚠ Address verification failed: {e}")

    # ==========================================
    # Test Summary
    # ==========================================
    print_section("Test Summary")

    if success:
        print_success("✓✓✓ TEST PASSED ✓✓✓")
        print_info("")
        print_info("Summary of successful registration:")
        print_info(f"  • Account: {TEST_ACCOUNT}")
        print_info(f"  • EVM Address: {evm_address}")
        print_info(f"  • SS58 Address: {ss58_address}")
        print_info(f"  • registeredUser: False → True")
        print_info(f"  • userColdkey: Set to coldkey")
        print_info(f"  • RegisterUser event: Emitted")
        print_info(f"  • Transaction hash: {tx_details['hash']}")
        print_info(f"  • Block: {tx_details['block']:,}")
        print_info(f"  • Gas used: {tx_details['gas_used']:,}")
        print_info("")
        print_success(f"{TEST_ACCOUNT} is now registered and can use protected functions")
    else:
        print_error("✗✗✗ TEST FAILED ✗✗✗")
        print_error("One or more verification checks failed")

    print("")
    return success


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
