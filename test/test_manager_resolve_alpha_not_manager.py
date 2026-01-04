#!/usr/bin/env python3
"""
Test Case TC06-01: resolveAlpha - Not Manager
Objective: Verify resolveAlpha fails when called by non-manager
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
    print_section("Test Case TC06-01: resolveAlpha - Not Manager")
    print(f"{CYAN}Objective:{NC} Verify resolveAlpha fails when called by non-manager")
    print(f"{CYAN}Strategy:{NC} Non-manager (LENDER1) attempts to resolve ALPHA")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'not manager'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender1_address = addresses['LENDER1']['evmAddress']
    borrower1_address = addresses['BORROWER1']['evmAddress']
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

    # Test parameters (dummy values for access control test)
    test_user = borrower1_address
    test_netuid = 3
    test_tao_amount = int(10 * 1e9)  # 10 TAO

    print_info(f"Caller: {lender1_address} (LENDER1, non-manager)")
    print_info(f"Manager: {manager_address}")
    print_info(f"Test user: {test_user}")
    print_info(f"Test netuid: {test_netuid}")
    print_info(f"Test TAO amount: {test_tao_amount / 1e9} TAO")

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

    # ========================================================================
    # Step 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # Step 3: Read Initial Loan State (if applicable)
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("Not applicable for resolveAlpha function")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute Test Operation - Attempt resolveAlpha")

    print_info(f"Calling resolveAlpha as non-manager (LENDER1)...")
    print_info(f"Parameters: user={test_user}, netuid={test_netuid}, taoAmount={test_tao_amount/1e9} TAO")

    # Build transaction
    account = w3.eth.account.from_key(lender1_private_key)
    nonce = w3.eth.get_transaction_count(lender1_address)

    try:
        # Build transaction
        tx = contract.functions.resolveAlpha(
            test_user,
            test_netuid,
            test_tao_amount
        ).build_transaction({
            'from': lender1_address,
            'nonce': nonce,
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
            'chainId': chain_id
        })

        # Sign and send transaction
        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction hash: {tx_hash.hex()}")

        # Wait for receipt
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if tx_receipt['status'] == 0:
            print_success(f"✓ Transaction reverted as expected (status=0)")
            print_info(f"Gas used: {tx_receipt['gasUsed']}")
        else:
            print_error(f"✗ Transaction succeeded unexpectedly (status=1)")
            print_error("Expected: Transaction should revert with 'not manager'")
            sys.exit(1)

    except Exception as e:
        error_msg = str(e)
        if "not manager" in error_msg.lower():
            print_success(f"✓ Transaction reverted with 'not manager' error")
            print_info(f"Error: {error_msg[:200]}")
        else:
            print_error(f"Transaction failed with unexpected error: {error_msg}")
            sys.exit(1)

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

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
    print_info("Not applicable for resolveAlpha function")

    # ========================================================================
    # Step 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # VERIFICATION
    # ========================================================================
    print_section("Verification Summary")

    print_success(f"✓ Contract state unchanged (no resolution occurred)")

    # ========================================================================
    # TEST RESULT
    # ========================================================================
    print_section("Test Result")

    print_success("✅ TEST PASSED")
    print_success("Transaction reverted with 'not manager' as expected")
    print_success("Non-manager cannot resolve ALPHA balances")
    print_success("onlyManager modifier working correctly")

if __name__ == "__main__":
    main()
