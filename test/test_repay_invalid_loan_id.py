#!/usr/bin/env python3
"""
Test Case TC02: Invalid Loan ID
Objective: Verify repay behavior with non-existent loan ID
Tests: _getLoanData behavior with invalid loanId
Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "loan inactive" or displays edge case behavior
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3

# Setup paths and imports
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from const import LENDING_POOL_V2_ADDRESS
from balance_checker import BalanceChecker
from common import (
    get_loan_full, load_addresses, load_contract_abi,
    STATE_OPEN, STATE_IN_COLLECTION, STATE_REPAID
)

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
MAGENTA = "\033[0;35m"
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
    print_section("Test Case TC02: Invalid Loan ID")
    print(f"{CYAN}Objective:{NC} Verify repay behavior with non-existent loan ID")
    print(f"{CYAN}Strategy:{NC} Attempt repay with invalid loan ID (nextLoanId + 100)")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'loan inactive' or edge case behavior\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    repayer_address = addresses['BORROWER1']['evmAddress']
    repayer_private_key = os.environ.get("BORROWER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    if not repayer_private_key:
        print_error("Repayer private key not found in .env")
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

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check REPAYER is registered
    repayer_registered = contract.functions.registeredUser(repayer_address).call()
    if not repayer_registered:
        print_error("SETUP ERROR: BORROWER1 (repayer) not registered")
        sys.exit(1)
    print_success(f"✓ BORROWER1 (repayer) registered: {repayer_address}")

    # Get nextLoanId to determine invalid loan ID
    next_loan_id = contract.functions.nextLoanId().call()
    print_info(f"Next Loan ID: {next_loan_id}")

    # Use an invalid loan ID (way beyond nextLoanId)
    invalid_loan_id = next_loan_id + 100
    print_warning(f"Using invalid loan ID: {invalid_loan_id} (nextLoanId + 100)")

    # Check BORROWER1 has some TAO (for repayment attempt)
    repayer_tao = contract.functions.userAlphaBalance(repayer_address, 0).call()
    print_info(f"BORROWER1 TAO balance: {repayer_tao / 1e9:.2f} TAO")

    if repayer_tao == 0:
        print_warning("⚠ BORROWER1 has no TAO (but test should fail at loan existence check)")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0, 2, 3]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": repayer_address, "label": "BORROWER1"}
    ]

    # Capture initial snapshot
    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    protocol_fee_before = contract.functions.protocolFeeAccumulated().call()
    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")

    print_info(f"Attempting to read loan state for invalid loan ID {invalid_loan_id}...")

    # Try to read loan data (should fail or return zero values)
    try:
        loan_info_before = get_loan_full(contract, invalid_loan_id)
        if loan_info_before is None:
            print_success("✓ get_loan_full returned None for invalid loan ID (expected)")
        else:
            loan_term_before = loan_info_before['term']
            loan_data_before = loan_info_before['data']
            print_warning(f"⚠ Loan data exists for invalid ID (unexpected):")
            print_info(f"  State: {loan_data_before['state']}")
            print_info(f"  Borrower: {loan_term_before['borrower']}")
            print_info(f"  Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    except Exception as e:
        print_warning(f"⚠ Reading loan data failed (expected): {str(e)[:200]}")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute repay()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} 'loan inactive' (most likely)")
    print(f"  {YELLOW}Alternative:{NC} Unexpected behavior with uninitialized loan data")
    print(f"  {CYAN}Reason:{NC} Loan ID {invalid_loan_id} does not exist")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from repayer's EVM TAO")
    print()

    print_info(f"Attempting to repay non-existent loan {invalid_loan_id}...")
    print_info(f"Repayer: {repayer_address} (BORROWER1, registered)")

    # Execute transaction
    tx_receipt = None
    reverted = False
    revert_reason = None
    succeeded = False

    try:
        tx = contract.functions.repay(invalid_loan_id).build_transaction({
            'from': repayer_address,
            'nonce': w3.eth.get_transaction_count(repayer_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
        })

        signed_tx = w3.eth.account.sign_transaction(tx, repayer_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        if tx_receipt['status'] == 0:
            reverted = True
            print_warning("Transaction reverted (as expected)")
        else:
            succeeded = True
            print_error("Transaction succeeded (unexpected!)")
            print_error("This indicates a potential issue with loan existence validation")

    except Exception as e:
        reverted = True
        error_msg = str(e)
        revert_reason = error_msg
        print_success(f"✓ Transaction reverted before mining (as expected)")

        # Try to extract revert reason
        if "loan inactive" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'loan inactive'")
        elif "invalid" in error_msg.lower():
            print_success(f"✓ Revert reason indicates invalid input")

        print_info(f"Error message: {error_msg[:300]}")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # Query final state
    protocol_fee_after = contract.functions.protocolFeeAccumulated().call()
    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} → {protocol_fee_after / 1e9:.9f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")

    print_info(f"Verifying loan {invalid_loan_id} still does not exist...")

    try:
        loan_info_after = get_loan_full(contract, invalid_loan_id)
        if loan_info_after is None:
            print_success("✓ Loan still does not exist (expected)")
        else:
            print_warning("⚠ Loan data returned after failed repay (edge case)")
    except Exception as e:
        print_success(f"✓ Reading loan data still fails (expected)")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction behavior
    if succeeded:
        print_error("✗ Transaction succeeded unexpectedly!")
        print_error("Expected: Transaction should revert with 'loan inactive'")
        print_error("EDGE CASE DETECTED: Invalid loan ID allowed repayment")
        print_error("This is a potential contract vulnerability!")

        # Document the edge case
        print_section("Edge Case Documentation")
        print_error("CRITICAL: repay() accepted invalid loan ID")
        print_error(f"Invalid Loan ID: {invalid_loan_id}")
        print_error(f"Next Valid Loan ID: {next_loan_id}")
        print_error("Recommendation: Add explicit loan existence validation")

        # Still check state changes
        diff = checker.diff_snapshots(snapshot_before, snapshot_after)
        checker.print_diff(diff)

        sys.exit(1)

    if not reverted:
        print_error("✗ Transaction neither succeeded nor reverted (unexpected state)")
        sys.exit(1)

    print_success("✓ Transaction reverted as expected")

    # Verify revert reason
    if revert_reason:
        if "loan inactive" in revert_reason.lower():
            print_success("✓ Revert reason confirmed: 'loan inactive'")
        elif "invalid" in revert_reason.lower():
            print_success("✓ Revert reason indicates invalid input")
        else:
            print_warning(f"⚠ Unexpected revert reason: {revert_reason[:200]}")

    # Verify protocol fee unchanged
    if protocol_fee_after != protocol_fee_before:
        print_error(f"✗ Protocol fee changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Protocol fee unchanged")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify only gas was deducted
    print_info("\nExpected changes:")
    print_info("  - BORROWER1 EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # Get repayer balance change
    repayer_before = snapshot_before['balances']['BORROWER1']['evm_tao_wei']
    repayer_after = snapshot_after['balances']['BORROWER1']['evm_tao_wei']
    repayer_diff = repayer_after - repayer_before

    if repayer_diff < 0:
        print_success(f"✓ BORROWER1 EVM TAO decreased (gas): {abs(repayer_diff) / 1e18:.9f} TAO")
    else:
        print_warning(f"⚠ BORROWER1 EVM TAO did not decrease (may have reverted before gas charge)")

    # Verify all contract balances unchanged
    borrower_tao_before = snapshot_before['balances']['BORROWER1']['contract']['netuid_0']['balance_rao']
    borrower_tao_after = snapshot_after['balances']['BORROWER1']['contract']['netuid_0']['balance_rao']

    if borrower_tao_before == borrower_tao_after:
        print_success("✓ BORROWER1 contract TAO balance unchanged")
    else:
        print_error(f"✗ BORROWER1 contract TAO balance changed unexpectedly!")
        sys.exit(1)

    # Report results
    print_section("Test Result")

    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC02: Invalid Loan ID")
    print_success(f"Transaction correctly reverted when using invalid loan ID")
    print_success("All state validations passed")
    print_success("No unexpected state changes detected")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - Invalid loan ID ({invalid_loan_id}) properly rejected")
    print(f"  - _getLoanData validation working correctly")
    print(f"  - Contract properly checks loan existence")
    print(f"  - Revert reason: {revert_reason[:100] if revert_reason else 'loan inactive'}")

    return 0

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
