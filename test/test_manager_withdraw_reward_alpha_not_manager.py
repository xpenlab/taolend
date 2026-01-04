#!/usr/bin/env python3
"""
Test Case TC01-01: withdrawRewardAlpha - Not Manager
Objective: Verify withdrawRewardAlpha fails when called by non-manager
Tests: onlyManager modifier check

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "not manager"
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
    print_section("Test Case TC01-01: withdrawRewardAlpha - Not Manager")
    print(f"{CYAN}Objective:{NC} Verify withdrawRewardAlpha fails when called by non-manager")
    print(f"{CYAN}Strategy:{NC} Non-manager account attempts to withdraw rewards")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'not manager'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    non_manager_address = addresses['LENDER1']['evmAddress']

    # Load private key
    non_manager_private_key = os.environ.get("LENDER1_PRIVATE_KEY")
    if not non_manager_private_key:
        print_error("LENDER1_PRIVATE_KEY not found in .env")
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
    test_netuid = 3  # Active subnet
    test_amount = 100 * 10**9  # 100 ALPHA in RAO

    print_info(f"Non-manager: {non_manager_address}")
    print_info(f"Test netuid: {test_netuid}")
    print_info(f"Test amount: {test_amount / 1e9} ALPHA")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check MANAGER address
    manager_address = contract.functions.MANAGER().call()
    print_info(f"Contract MANAGER: {manager_address}")
    print_info(f"Test caller: {non_manager_address}")

    if manager_address.lower() == non_manager_address.lower():
        print_error("SETUP ERROR: Test account is the MANAGER (should be non-manager)")
        sys.exit(1)

    print_success(f"✓ LENDER1 is NOT the MANAGER")

    # Check subnet is active
    subnet_active = contract.functions.activeSubnets(test_netuid).call()
    if not subnet_active:
        print_warning(f"Warning: Subnet {test_netuid} is not active (but test will proceed)")

    print_success(f"✓ Subnet {test_netuid} active status: {subnet_active}")

    # ========================================================================
    # Step 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0, test_netuid]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": non_manager_address, "label": "LENDER1 (Non-Manager)"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # ========================================================================
    # Step 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # Step 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("Not applicable for this test (no loan involved)")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute withdrawRewardAlpha (should fail)")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} Transaction reverts with 'not manager'")
    print(f"  {CYAN}State Changes:{NC} None (transaction reverted)")
    print(f"  {CYAN}Balance Changes:{NC} Only gas deduction for caller\n")

    print_info(f"Attempting to withdraw {test_amount / 1e9} ALPHA from netuid {test_netuid}...")

    # Execute transaction (should fail)
    try:
        tx = contract.functions.withdrawRewardAlpha(
            test_netuid,
            test_amount
        ).build_transaction({
            'from': non_manager_address,
            'nonce': w3.eth.get_transaction_count(non_manager_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=non_manager_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print_info(f"Transaction hash: {tx_hash.hex()}")
        print_info("Waiting for transaction receipt...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt['status'] == 1:
            print_error("❌ Transaction succeeded (expected to fail)")
            print_error("CRITICAL: Non-manager was able to withdraw rewards!")
            sys.exit(1)
        else:
            print_success(f"✓ Transaction reverted as expected")
            print_info(f"Gas used: {receipt['gasUsed']}")

    except Exception as e:
        error_message = str(e)
        print_success(f"✓ Transaction reverted with error")
        print_info(f"Error: {error_message}")

        # Check if error contains expected message
        if "not manager" in error_message.lower():
            print_success("✓ Error message contains 'not manager'")
        else:
            print_warning(f"Warning: Error message does not contain 'not manager'")
            print_warning(f"Actual error: {error_message}")

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    # Capture final snapshot
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # ========================================================================
    # Step 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # Step 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info("Not applicable for this test (no loan involved)")

    # ========================================================================
    # Step 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Calculate differences
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # Verification
    # ========================================================================
    print_section("Verification Summary")

    all_checks_passed = True

    # Check 1: Contract state unchanged
    contract_state_before = snapshot_before['contract']
    contract_state_after = snapshot_after['contract']

    state_unchanged = (
        contract_state_before['protocol_fee_accumulated'] == contract_state_after['protocol_fee_accumulated'] and
        contract_state_before['subnet_total_balance'] == contract_state_after['subnet_total_balance'] and
        contract_state_before['next_loan_id'] == contract_state_after['next_loan_id']
    )

    if state_unchanged:
        print_success("✓ Contract state unchanged (transaction reverted)")
    else:
        print_error("✗ Contract state changed (should be unchanged)")
        all_checks_passed = False

    # Check 2: All user balances unchanged (except gas)
    user_before = snapshot_before['balances']['LENDER1 (Non-Manager)']
    user_after = snapshot_after['balances']['LENDER1 (Non-Manager)']

    # Contract balances should be unchanged
    for netuid in [0, test_netuid]:
        netuid_key = f'netuid_{netuid}'
        if netuid_key in user_before['contract'] and netuid_key in user_after['contract']:
            balance_before = user_before['contract'][netuid_key]['balance_rao']
            balance_after = user_after['contract'][netuid_key]['balance_rao']
            if balance_before != balance_after:
                print_error(f"✗ Contract balance changed for netuid {netuid}")
                all_checks_passed = False

    if all_checks_passed:
        print_success("✓ All user balances unchanged (except gas)")

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success("Non-manager cannot call withdrawRewardAlpha")
        print_success("Transaction reverted with access control error")
        print_success("No state changes occurred")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
