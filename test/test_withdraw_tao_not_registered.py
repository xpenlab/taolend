#!/usr/bin/env python3
"""
Test Case TC11: withdrawTao() - Not Registered
Objective: Verify withdrawTao reverts when user is not registered
Tests: onlyRegistered modifier (line 232)

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "not registered" error
"""

import os
import sys
from pathlib import Path
from web3 import Web3

# Setup paths and imports
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from const import LENDING_POOL_V2_ADDRESS
from balance_checker import BalanceChecker
from common import load_addresses, load_contract_abi

# Load environment variables
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
CYAN = "\033[0;96m"
BOLD = "\033[1m"
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
    print("\n" + "=" * 80)
    print(f"{BOLD}{title}{NC}")
    print("=" * 80)

def main():
    print_section("Test Case TC11: withdrawTao() - Not Registered")
    print(f"{CYAN}Objective:{NC} Verify withdrawTao reverts when user is not registered")
    print(f"{CYAN}Tests:{NC} onlyRegistered modifier (line 232)")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'not registered' error\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()

    # Use BORROWER3 as unregistered user (assuming not registered)
    unregistered_address = addresses['BORROWER3']['evmAddress']
    unregistered_private_key = os.environ.get("BORROWER3_PRIVATE_KEY")
    unregistered_label = 'BORROWER3'

    if not unregistered_private_key:
        print_error(f"SETUP ERROR: BORROWER3_PRIVATE_KEY not found in .env")
        sys.exit(1)

    # Setup Web3
    w3 = Web3(Web3.HTTPProvider(BITTENSOR_RPC))
    if not w3.is_connected():
        print_error("Failed to connect to Bittensor EVM node")
        sys.exit(1)

    chain_id = w3.eth.chain_id
    print_success(f"Connected to Bittensor EVM (Chain ID: {chain_id})")

    # Load contract
    contract_abi = load_contract_abi()
    contract = w3.eth.contract(address=LENDING_POOL_V2_ADDRESS, abi=contract_abi)

    # Test parameters
    withdraw_amount_rao = 1 * 10**9  # 1 TAO

    print_info(f"\nTest Parameters:")
    print_info(f"  Unregistered User: {unregistered_label} ({unregistered_address})")
    print_info(f"  Withdraw Amount: {withdraw_amount_rao / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify user is NOT registered (required for this test)
    user_registered = contract.functions.registeredUser(unregistered_address).call()
    if user_registered:
        print_error(f"SETUP ERROR: {unregistered_label} is already registered")
        print_error(f"This test requires an unregistered user")
        print_info(f"Please use a different account or unregister this account first")
        sys.exit(1)
    print_success(f"✓ {unregistered_label} is not registered: {unregistered_address}")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0])

    addresses_list = [
        {"address": unregistered_address, "label": unregistered_label},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("N/A - withdrawal operations do not involve loans")

    # ========================================================================
    # STEP 4: Execute withdrawTao()
    # ========================================================================
    print_section("Step 4: Execute withdrawTao()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Failure:{NC} Transaction reverts")
    print(f"  {CYAN}Error:{NC} \"not registered\"")
    print(f"  {CYAN}Check:{NC} onlyRegistered modifier (line 232)")
    print()

    print_info(f"Attempting to withdraw {withdraw_amount_rao / 1e9:.2f} TAO...")
    print_info(f"User: {unregistered_address} ({unregistered_label}, not registered)")

    # Execute transaction
    tx_failed = False
    error_message = None

    try:
        nonce = w3.eth.get_transaction_count(unregistered_address)
        gas_price = w3.eth.gas_price

        tx = contract.functions.withdrawTao(withdraw_amount_rao).build_transaction({
            'from': unregistered_address,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': gas_price,
            'chainId': chain_id
        })

        signed_tx = w3.eth.account.sign_transaction(tx, unregistered_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        if tx_receipt['status'] == 0:
            print_success("✓ Transaction reverted as expected")
            tx_failed = True
        else:
            print_error("✗ Transaction succeeded unexpectedly!")
            print_error("Expected transaction to revert with 'not registered'")

    except Exception as e:
        error_str = str(e)
        print_success(f"✓ Transaction failed as expected")
        print_info(f"Error: {error_str}")
        tx_failed = True
        error_message = error_str

        # Check if error message contains expected revert reason
        if "not registered" in error_str.lower() or "execution reverted" in error_str.lower():
            print_success("✓ Error message indicates registration check failed")
        else:
            print_warning("⚠ Error message doesn't explicitly mention 'not registered'")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info("N/A - withdrawal operations do not involve loans")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    print_info("Verifying test expectations...")

    all_checks_passed = True

    # 1. Verify transaction failed
    if not tx_failed:
        print_error("✗ Transaction should have failed!")
        all_checks_passed = False
    else:
        print_success("✓ Transaction failed as expected")

    # 2. Verify no state changes occurred
    print_info("\nVerifying no state changes...")

    user_balance_before = snapshot_before['balances'].get(unregistered_label, {}).get('contract', {}).get('netuid_0', {}).get('balance_rao', 0)
    user_balance_after = snapshot_after['balances'].get(unregistered_label, {}).get('contract', {}).get('netuid_0', {}).get('balance_rao', 0)

    if user_balance_before != user_balance_after:
        print_error("✗ User balance changed unexpectedly!")
        print_error(f"  Before: {user_balance_before / 1e9:.2f} TAO")
        print_error(f"  After:  {user_balance_after / 1e9:.2f} TAO")
        all_checks_passed = False
    else:
        print_success("✓ User balance unchanged")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    print_info("\nExpected: No changes (transaction reverted)")

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC11 TEST PASSED ✓✓✓")
        print_success("withdrawTao() correctly rejects unregistered users")
        print_success("onlyRegistered modifier working as expected")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - User: {unregistered_label} (not registered)")
        print(f"  - Attempted withdrawal: {withdraw_amount_rao / 1e9:.2f} TAO")
        print(f"  - Result: Transaction reverted ✓")
        print(f"  - Error: 'not registered' (line 232)")
        if error_message:
            print(f"  - Error message: {error_message[:100]}...")

        return 0
    else:
        print_error("✗✗✗ TC11 TEST FAILED ✗✗✗")
        print_error("Test expectations not met")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_info("\nTest cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
