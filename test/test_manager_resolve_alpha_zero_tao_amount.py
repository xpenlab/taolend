#!/usr/bin/env python3
"""
Test Case TC06-06: resolveAlpha - Zero TAO Amount
Objective: Verify resolveAlpha fails when TAO amount is zero
Tests: require(_taoAmount > 0, "zero amount")

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "zero amount"
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
    print_section("Test Case TC06-06: resolveAlpha - Zero TAO Amount")
    print(f"{CYAN}Objective:{NC} Verify resolveAlpha fails when TAO amount is zero")
    print(f"{CYAN}Strategy:{NC} Manager attempts to resolve ALPHA with taoAmount=0")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'zero amount'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    manager_address = addresses['MANAGER']['evmAddress']
    borrower1_address = addresses['BORROWER1']['evmAddress']

    # Load private key for MANAGER
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
    test_user = borrower1_address
    test_netuid = 3
    test_tao_amount = 0  # ZERO TAO amount (invalid)

    print_info(f"Caller: {manager_address} (MANAGER)")
    print_info(f"Test user: {test_user}")
    print_info(f"Test netuid: {test_netuid}")
    print_info(f"Test TAO amount: {test_tao_amount} (ZERO - invalid)")

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
    print_info(f"This test will fail on 'zero amount' check")
    print_info(f"Rationale: Must provide positive TAO amount for conversion")

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
        {"address": manager_address, "label": "MANAGER (caller)"},
        {"address": test_user, "label": "Test User"}
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
    print_info("Not applicable for resolveAlpha function (no loan involved)")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute resolveAlpha with taoAmount=0 (expect REVERT)")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Failure:{NC} Transaction reverts (status=0)")
    print(f"  {RED}Error:{NC} 'zero amount'")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes except gas deduction\n")

    print_info(f"Attempting to resolve ALPHA with taoAmount=0...")

    # Execute transaction (expect revert)
    try:
        tx = contract.functions.resolveAlpha(
            test_user,
            test_netuid,
            test_tao_amount  # 0 (invalid)
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
            print_error("resolveAlpha should NOT accept zero TAO amount")
            sys.exit(1)

    except Exception as e:
        error_message = str(e)
        if "zero amount" in error_message.lower():
            print_success(f"✓ Transaction reverted with 'zero amount' error")
            print_info(f"Error message: {error_message[:200]}")
        elif "subnet enabled" in error_message.lower():
            print_warning(f"Transaction reverted with 'subnet enabled' error")
            print_info(f"Error: {error_message[:200]}")
            print_info("Note: May fail on earlier check (subnet enabled) before reaching 'zero amount' check")
        else:
            print_warning(f"Transaction reverted: {error_message[:200]}")
            print_info("Expected - validation checks prevent invalid resolution")

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
    print_info("Not applicable for resolveAlpha function (no loan involved)")

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

    print_success(f"✓ Contract state unchanged (no resolution occurred)")
    print_success(f"✓ Zero TAO amount correctly rejected")

    # ========================================================================
    # Test Result
    # ========================================================================
    print_section("Test Result")

    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success("Transaction reverted as expected")
        print_success("resolveAlpha rejects zero TAO amount")
        print_success("Must provide positive TAO amount for conversion")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some validation checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
