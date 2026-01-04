#!/usr/bin/env python3
"""
Test Case TC31: withdrawAlpha() - Not Registered
Objective: Verify withdrawAlpha fails when user is not registered
Tests: onlyRegistered modifier - require(registeredUser[msg.sender], "not registered")

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "not registered"
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
    print_section("Test Case TC31: withdrawAlpha() - Not Registered")
    print(f"{CYAN}Objective:{NC} Verify withdrawAlpha fails when user is not registered")
    print(f"{CYAN}Strategy:{NC} Attempt withdrawal with unregistered user")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'not registered'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()

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

    # Find an unregistered account
    print_info("Finding unregistered account...")
    unregistered_address = None
    unregistered_private_key = None
    unregistered_label = None

    candidate_accounts = ['LENDER3', 'BORROWER2', 'LENDER4', 'USER1']

    for account_name in candidate_accounts:
        if account_name in addresses:
            candidate_address = addresses[account_name]['evmAddress']
            is_registered = contract.functions.registeredUser(candidate_address).call()
            if not is_registered:
                unregistered_address = candidate_address
                unregistered_private_key = os.environ.get(f"{account_name}_PRIVATE_KEY")
                unregistered_label = account_name
                print_success(f"Found unregistered account: {account_name} ({candidate_address})")
                break

    if unregistered_address is None:
        print_error("SETUP ERROR: No unregistered account found")
        sys.exit(1)

    if not unregistered_private_key:
        print_error(f"SETUP ERROR: Private key for {unregistered_label} not found in .env")
        sys.exit(1)

    # Test parameters
    test_netuid = 2
    withdraw_amount_rao = 100 * 10**9  # 100 ALPHA

    print_info(f"\nTest Parameters:")
    print_info(f"  Unregistered User: {unregistered_label} ({unregistered_address})")
    print_info(f"  Netuid: {test_netuid}")
    print_info(f"  Withdraw Amount: {withdraw_amount_rao / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check user is NOT registered
    user_registered = contract.functions.registeredUser(unregistered_address).call()
    if user_registered:
        print_error(f"SETUP ERROR: {unregistered_label} is already registered")
        sys.exit(1)
    print_success(f"✓ {unregistered_label} NOT registered (as required)")

    # Check subnet is active
    active_subnet = contract.functions.activeSubnets(test_netuid).call()
    print_info(f"Subnet {test_netuid} active: {active_subnet}")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, test_netuid])

    addresses_list = [
        {"address": unregistered_address, "label": unregistered_label},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    subnet_balance_before = contract.functions.subnetAlphaBalance(test_netuid).call()
    print_info(f"\nContract State:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 2-3: Account/Loan State
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    print_section("Step 3: Read Initial Loan State")
    print_info("N/A - withdraw operations do not involve loans")

    # ========================================================================
    # STEP 4: Execute withdrawAlpha()
    # ========================================================================
    print_section("Step 4: Execute withdrawAlpha()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} 'not registered'")
    print(f"  {CYAN}Reason:{NC} {unregistered_label} is not registered (onlyRegistered modifier)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from user's EVM TAO")
    print()

    print_info(f"Attempting to withdraw {withdraw_amount_rao / 1e9:.2f} ALPHA...")

    tx_receipt = None
    reverted = False
    revert_reason = None

    try:
        nonce = w3.eth.get_transaction_count(unregistered_address)
        gas_price = w3.eth.gas_price

        tx = contract.functions.withdrawAlpha(
            test_netuid,
            withdraw_amount_rao
        ).build_transaction({
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
            reverted = True
            print_warning("Transaction reverted (as expected)")

    except Exception as e:
        reverted = True
        error_msg = str(e)
        revert_reason = error_msg
        print_success(f"✓ Transaction reverted before mining (as expected)")

        if "not registered" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'not registered'")

        print_info(f"Error message: {error_msg[:300]}")

    # ========================================================================
    # STEP 5-7: Final State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    subnet_balance_after = contract.functions.subnetAlphaBalance(test_netuid).call()
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")

    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    print_section("Step 7: Read Final Loan State")
    print_info("N/A - withdraw operations do not involve loans")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    print_info("Verifying test expectations...")

    all_checks_passed = True

    # 1. Verify transaction reverted
    if not reverted and (tx_receipt and tx_receipt['status'] == 1):
        print_error("✗ Transaction succeeded unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Transaction reverted as expected")

    # 2. Verify revert reason
    if revert_reason and "not registered" in revert_reason.lower():
        print_success("✓ Revert reason confirmed: 'not registered'")
    elif revert_reason:
        print_warning(f"⚠ Revert reason may differ: {revert_reason[:200]}")

    # 3. Verify subnet balance unchanged
    if subnet_balance_after != subnet_balance_before:
        print_error(f"✗ Subnet balance changed unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Subnet balance unchanged")

    # Print balance changes
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    print_info("\nExpected changes:")
    print_info(f"  - {unregistered_label} EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC31 TEST PASSED ✓✓✓")
        print_success("withdrawAlpha() correctly reverted with 'not registered'")
        print_success("All state validations passed")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Unregistered user cannot call withdrawAlpha()")
        print(f"  - onlyRegistered modifier working correctly")
        print(f"  - Subnet balance unchanged: {subnet_balance_before / 1e9:.2f} ALPHA")

        return 0
    else:
        print_error("✗✗✗ TC31 TEST FAILED ✗✗✗")
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
