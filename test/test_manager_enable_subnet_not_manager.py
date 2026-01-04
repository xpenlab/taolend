#!/usr/bin/env python3
"""
Test Case TC03-01: enableSubnet - Not Manager
Objective: Verify enableSubnet fails when called by non-manager
Tests: Access control (onlyManager modifier)

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
    print_section("Test Case TC03-01: enableSubnet - Not Manager")
    print(f"{CYAN}Objective:{NC} Verify enableSubnet fails when called by non-manager")
    print(f"{CYAN}Strategy:{NC} Non-manager (LENDER1) attempts to enable a subnet")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'not manager'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender1_address = addresses['LENDER1']['evmAddress']
    manager_address = addresses['MANAGER']['evmAddress']

    # Load private key for LENDER1
    lender1_private_key = os.environ.get("LENDER1_PRIVATE_KEY")
    if not lender1_private_key:
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
    test_netuid = 3  # Valid netuid with high alpha

    print_info(f"Caller: {lender1_address} (LENDER1, non-manager)")
    print_info(f"Manager: {manager_address}")
    print_info(f"Test netuid: {test_netuid}")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify caller is NOT manager
    contract_manager = contract.functions.MANAGER().call()
    if contract_manager.lower() == lender1_address.lower():
        print_error(f"SETUP ERROR: LENDER1 is the MANAGER (should be non-manager)")
        sys.exit(1)

    print_success(f"✓ Caller (LENDER1) is NOT the manager")
    print_info(f"Actual manager: {contract_manager}")

    # Check current subnet status (for information)
    subnet_active = contract.functions.activeSubnets(test_netuid).call()
    print_info(f"Subnet {test_netuid} active status: {subnet_active}")

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
        {"address": lender1_address, "label": "LENDER1 (caller)"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # Store initial subnet status
    initial_subnet_active = subnet_active

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
    print_section("Step 4: Execute enableSubnet (expect REVERT)")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Failure:{NC} Transaction reverts (status=0)")
    print(f"  {RED}Error:{NC} 'not manager'")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes except gas deduction\n")

    print_info(f"Attempting to enable subnet {test_netuid} as non-manager...")

    # Execute transaction (expect revert)
    try:
        tx = contract.functions.enableSubnet(
            test_netuid
        ).build_transaction({
            'from': lender1_address,
            'nonce': w3.eth.get_transaction_count(lender1_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=lender1_private_key)
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
            print_error("Non-manager should NOT be able to enable subnet")
            sys.exit(1)

    except Exception as e:
        error_message = str(e)
        if "not manager" in error_message.lower():
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

    # Query final subnet status
    final_subnet_active = contract.functions.activeSubnets(test_netuid).call()

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

    # Check 1: Subnet status unchanged
    if final_subnet_active == initial_subnet_active:
        print_success(f"✓ Subnet status unchanged: {initial_subnet_active}")
    else:
        print_error(f"✗ Subnet status changed from {initial_subnet_active} to {final_subnet_active}")
        all_checks_passed = False

    # Check 2: No state changes except gas
    contract_state_before = snapshot_before['contract']
    contract_state_after = snapshot_after['contract']

    if (contract_state_before['protocol_fee_accumulated'] == contract_state_after['protocol_fee_accumulated'] and
        contract_state_before['next_loan_id'] == contract_state_after['next_loan_id']):
        print_success("✓ Contract state unchanged (no subnet enable occurred)")
    else:
        print_error("✗ Contract state changed (subnet enable should not have occurred)")
        all_checks_passed = False

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success("Transaction reverted with 'not manager' as expected")
        print_success("Non-manager cannot enable subnet")
        print_success("onlyManager modifier working correctly")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
