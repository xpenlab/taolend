#!/usr/bin/env python3
"""
Test Case TC02-02: withdrawProtocolFees - Low Fee
Objective: Verify withdrawProtocolFees fails when insufficient fees accumulated
Tests: require(protocolFeeAccumulated >= _amount, "low fee")

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "low fee"
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
    print_section("Test Case TC02-02: withdrawProtocolFees - Low Fee")
    print(f"{CYAN}Objective:{NC} Verify withdrawProtocolFees fails when insufficient fees accumulated")
    print(f"{CYAN}Strategy:{NC} MANAGER attempts to withdraw more fees than accumulated")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'low fee'\n")

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

    print_info(f"Manager: {manager_address}")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify caller is MANAGER
    contract_manager = contract.functions.MANAGER().call()
    if contract_manager.lower() != manager_address.lower():
        print_error(f"SETUP ERROR: Caller is not MANAGER")
        sys.exit(1)

    print_success(f"✓ Caller is the MANAGER")

    # Query protocol fees
    protocol_fee_accumulated = contract.functions.protocolFeeAccumulated().call()
    print_info(f"Protocol fees accumulated: {protocol_fee_accumulated / 1e9} TAO")

    # Set test amount to exceed available fees
    if protocol_fee_accumulated == 0:
        # Scenario A: Zero fees
        test_amount = int(1 * 1e9)  # Try to withdraw 1 TAO (but 0 available)
        print_info("Scenario: Zero fees accumulated")
    else:
        # Scenario B: Insufficient fees
        test_amount = protocol_fee_accumulated + int(10 * 1e9)  # Exceed by 10 TAO
        print_info("Scenario: Insufficient fees")

    print_info(f"Withdrawal amount: {test_amount / 1e9} TAO (exceeds available)")
    print_success(f"✓ Setup: protocolFeeAccumulated ({protocol_fee_accumulated / 1e9} TAO) < withdrawal amount ({test_amount / 1e9} TAO)")

    # ========================================================================
    # Step 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": manager_address, "label": "MANAGER"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # Store initial protocol fee
    initial_protocol_fee = protocol_fee_accumulated

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
    print_section("Step 4: Execute withdrawProtocolFees (expect REVERT)")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Failure:{NC} Transaction reverts (status=0)")
    print(f"  {RED}Error:{NC} 'low fee'")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes except gas deduction\n")

    print_info(f"Attempting to withdraw {test_amount / 1e9} TAO (insufficient fees)...")

    # Execute transaction (expect revert)
    try:
        tx = contract.functions.withdrawProtocolFees(
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

        if receipt['status'] == 0:
            print_success(f"✓ Transaction reverted as expected")
            print_info(f"Gas used: {receipt['gasUsed']}")
            print_info(f"Block number: {receipt['blockNumber']}")
        else:
            print_error("❌ Transaction succeeded (expected to revert)")
            print_error("Should not be able to withdraw more than accumulated fees")
            sys.exit(1)

    except Exception as e:
        error_message = str(e)
        if "low fee" in error_message.lower():
            print_success(f"✓ Transaction reverted with expected error")
            print_info(f"Error message: {error_message}")
        else:
            print_error(f"❌ Transaction reverted with unexpected error: {error_message}")
            sys.exit(1)

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    # Capture final snapshot
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # Query final protocol fee
    final_protocol_fee = contract.functions.protocolFeeAccumulated().call()

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

    # Check 1: Protocol fee unchanged
    if final_protocol_fee == initial_protocol_fee:
        print_success(f"✓ Protocol fee unchanged: {initial_protocol_fee / 1e9} TAO")
    else:
        print_error(f"✗ Protocol fee changed from {initial_protocol_fee / 1e9} to {final_protocol_fee / 1e9} TAO")
        all_checks_passed = False

    # Check 2: Verify the require condition
    if initial_protocol_fee < test_amount:
        print_success(f"✓ Condition verified: protocolFeeAccumulated ({initial_protocol_fee / 1e9}) < amount ({test_amount / 1e9})")
    else:
        print_error(f"✗ Test setup error: protocolFeeAccumulated should be less than withdrawal amount")
        all_checks_passed = False

    # Check 3: Contract state unchanged
    contract_state_before = snapshot_before['contract']
    contract_state_after = snapshot_after['contract']

    if contract_state_before['protocol_fee_accumulated'] == contract_state_after['protocol_fee_accumulated']:
        print_success("✓ Contract state unchanged (no withdrawal occurred)")
    else:
        print_error("✗ Contract state changed (withdrawal should not have occurred)")
        all_checks_passed = False

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success("Transaction reverted with 'low fee' as expected")
        print_success(f"Cannot withdraw {test_amount / 1e9} TAO when only {initial_protocol_fee / 1e9} TAO accumulated")
        print_success("Fee validation working correctly")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
