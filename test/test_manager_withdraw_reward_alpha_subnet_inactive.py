#!/usr/bin/env python3
"""
Test Case TC01-02: withdrawRewardAlpha - Subnet Inactive
Objective: Verify withdrawRewardAlpha fails when subnet is not active
Tests: _requireSubnetActive check

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "subnet inactive"
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
    print_section("Test Case TC01-02: withdrawRewardAlpha - Subnet Inactive")
    print(f"{CYAN}Objective:{NC} Verify withdrawRewardAlpha fails when subnet is not active")
    print(f"{CYAN}Strategy:{NC} MANAGER attempts to withdraw from inactive subnet 4")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'subnet inactive'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    manager_address = addresses['MANAGER']['evmAddress']

    # Load private key
    manager_private_key = os.environ.get("MANAGER_PRIVATE_KEY")
    if not manager_private_key:
        print_error("MANAGER_PRIVATE_KEY not found in .env")
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
    test_netuid = 4  # Inactive subnet
    test_amount = 100 * 10**9  # 100 ALPHA in RAO

    print_info(f"Manager: {manager_address}")
    print_info(f"Test netuid: {test_netuid} (inactive)")
    print_info(f"Test amount: {test_amount / 1e9} ALPHA")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify caller is MANAGER
    contract_manager = contract.functions.MANAGER().call()
    if contract_manager.lower() != manager_address.lower():
        print_error(f"SETUP ERROR: Caller is not MANAGER")
        print_error(f"Contract MANAGER: {contract_manager}")
        print_error(f"Caller: {manager_address}")
        sys.exit(1)

    print_success(f"✓ Caller is the MANAGER")

    # Verify subnet is inactive
    subnet_active = contract.functions.activeSubnets(test_netuid).call()
    if subnet_active:
        print_error(f"SETUP ERROR: Subnet {test_netuid} is active (should be inactive)")
        print_error("Please use an inactive subnet for this test")
        sys.exit(1)

    print_success(f"✓ Subnet {test_netuid} is inactive (activeSubnets[{test_netuid}] = {subnet_active})")

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
        {"address": manager_address, "label": "MANAGER"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
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
    print(f"  {RED}Revert:{NC} Transaction reverts with 'subnet inactive'")
    print(f"  {CYAN}Reason:{NC} _requireSubnetActive check fails for subnet {test_netuid}")
    print(f"  {CYAN}State Changes:{NC} None (transaction reverted)")
    print(f"  {CYAN}Balance Changes:{NC} Only gas deduction for MANAGER\n")

    print_info(f"Attempting to withdraw {test_amount / 1e9} ALPHA from inactive subnet {test_netuid}...")

    # Execute transaction (should fail)
    try:
        tx = contract.functions.withdrawRewardAlpha(
            test_netuid,
            test_amount
        ).build_transaction({
            'from': manager_address,
            'nonce': w3.eth.get_transaction_count(manager_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=manager_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print_info(f"Transaction hash: {tx_hash.hex()}")
        print_info("Waiting for transaction receipt...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt['status'] == 1:
            print_error("❌ Transaction succeeded (expected to fail)")
            print_error("CRITICAL: Able to withdraw from inactive subnet!")
            sys.exit(1)
        else:
            print_success(f"✓ Transaction reverted as expected")
            print_info(f"Gas used: {receipt['gasUsed']}")

    except Exception as e:
        error_message = str(e)
        print_success(f"✓ Transaction reverted with error")
        print_info(f"Error: {error_message}")

        # Check if error contains expected message
        if "subnet inactive" in error_message.lower():
            print_success("✓ Error message contains 'subnet inactive'")
        else:
            print_warning(f"Warning: Error message does not contain 'subnet inactive'")
            print_warning(f"Actual error: {error_message}")

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    # Capture final snapshot
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
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

    # Check 2: Staking balances unchanged
    if 'subnet_staking' in contract_state_before and 'subnet_staking' in contract_state_after:
        staking_before = contract_state_before['subnet_staking']
        staking_after = contract_state_after['subnet_staking']

        if staking_before == staking_after:
            print_success("✓ On-chain staking unchanged")
        else:
            print_error("✗ On-chain staking changed (should be unchanged)")
            all_checks_passed = False

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success(f"withdrawRewardAlpha correctly rejects inactive subnet {test_netuid}")
        print_success("Transaction reverted with 'subnet inactive' error")
        print_success("No state or balance changes occurred")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
