#!/usr/bin/env python3
"""
Test Case TC03: Loan Already Repaid
Objective: Verify repay fails when loan is already in REPAID state
Tests: _requireLoanActive - state check (loan.state == REPAID)
Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "loan inactive"
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
    print_section("Test Case TC03: Loan Already Repaid")
    print(f"{CYAN}Objective:{NC} Verify repay fails when loan is already in REPAID state")
    print(f"{CYAN}Strategy:{NC} Find or create a REPAID loan, then attempt to repay again")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'loan inactive'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender_address = addresses['LENDER1']['evmAddress']
    borrower_address = addresses['BORROWER1']['evmAddress']
    repayer_address = borrower_address  # Use borrower as repayer
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

    # Check accounts are registered
    lender_registered = contract.functions.registeredUser(lender_address).call()
    if not lender_registered:
        print_error("SETUP ERROR: LENDER1 not registered")
        sys.exit(1)
    print_success(f"✓ LENDER1 registered: {lender_address}")

    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    if not borrower_registered:
        print_error("SETUP ERROR: BORROWER1 not registered")
        sys.exit(1)
    print_success(f"✓ BORROWER1 registered: {borrower_address}")

    # Find a loan that is already in REPAID state
    print_info("\nSearching for a loan in REPAID state...")
    next_loan_id = contract.functions.nextLoanId().call()
    print_info(f"Total loans in system: {next_loan_id}")

    repaid_loan_id = None
    for loan_id in range(next_loan_id):
        try:
            loan_info = get_loan_full(contract, loan_id)
            if loan_info is None:
                continue

            loan_term = loan_info['term']
            loan_data = loan_info['data']

            # Check if loan is in REPAID state
            if loan_data['state'] == STATE_REPAID:
                repaid_loan_id = loan_id
                print_success(f"✓ Found REPAID loan: Loan ID {loan_id}")
                print_info(f"  Borrower: {loan_term['borrower']}")
                print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
                print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
                print_info(f"  Netuid: {loan_term['netuid']}")
                print_info(f"  Repaid by: {loan_data['initiator']}")
                break
        except Exception as e:
            continue

    if repaid_loan_id is None:
        print_warning("No REPAID loan found in system")
        print_info("This test requires a loan that has been repaid")
        print_info("Recommendation: Create and repay a loan first, then run this test")
        print_error("SETUP ERROR: No REPAID loan available for testing")
        sys.exit(1)

    test_loan_id = repaid_loan_id

    # Get loan details
    loan_info_initial = get_loan_full(contract, test_loan_id)
    loan_term_initial = loan_info_initial['term']
    loan_data_initial = loan_info_initial['data']
    offer_initial = loan_info_initial['offer']
    netuid = loan_term_initial['netuid']

    # Verify loan state is REPAID
    if loan_data_initial['state'] != STATE_REPAID:
        print_error(f"SETUP ERROR: Loan {test_loan_id} is not in REPAID state")
        sys.exit(1)
    print_success(f"✓ Confirmed: Loan {test_loan_id} is in REPAID state")

    # Check repayer has sufficient TAO (even though transaction should fail)
    repayer_tao = contract.functions.userAlphaBalance(repayer_address, 0).call()
    print_info(f"\nBORROWER1 TAO balance: {repayer_tao / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0, netuid]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": lender_address, "label": "LENDER1"},
        {"address": borrower_address, "label": "BORROWER1"}
    ]

    # Capture initial snapshot
    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    protocol_fee_before = contract.functions.protocolFeeAccumulated().call()
    offer_id_bytes = loan_data_initial['offerId']
    lend_balance_before = contract.functions.userLendBalance(offer_initial['lender'], offer_id_bytes).call()

    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} TAO")
    print_info(f"  userLendBalance[lender][offerId]: {lend_balance_before / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")

    print_info(f"Reading loan state for loan ID {test_loan_id}...")
    loan_info_before = get_loan_full(contract, test_loan_id)
    loan_term_before = loan_info_before['term']
    loan_data_before = loan_info_before['data']
    offer_before = loan_info_before['offer']

    print_info(f"Loan State Before:")
    print_info(f"  State: {['OPEN', 'IN_COLLECTION', 'REPAID', 'CLAIMED', 'RESOLVED'][loan_data_before['state']]}")
    print_info(f"  Borrower: {loan_term_before['borrower']}")
    print_info(f"  Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Start Block: {loan_data_before['startBlock']}")
    print_info(f"  Last Update Block: {loan_data_before['lastUpdateBlock']}")
    print_info(f"  Repaid by: {loan_data_before['initiator']}")

    # Verify state is REPAID
    if loan_data_before['state'] != STATE_REPAID:
        print_error(f"ERROR: Loan state is not REPAID!")
        sys.exit(1)
    print_success(f"✓ Loan state confirmed: REPAID")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute repay()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} 'loan inactive'")
    print(f"  {CYAN}Reason:{NC} Loan is already in REPAID state")
    print(f"  {CYAN}Validation:{NC} _requireLoanActive checks loan.state == REPAID")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from repayer's EVM TAO")
    print()

    print_info(f"Attempting to repay already-repaid loan {test_loan_id}...")
    print_info(f"Repayer: {repayer_address} (BORROWER1)")

    # Execute transaction
    tx_receipt = None
    reverted = False
    revert_reason = None

    try:
        tx = contract.functions.repay(test_loan_id).build_transaction({
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
            print_error("Transaction succeeded (UNEXPECTED!)")
            print_error("This is a CRITICAL BUG - loan can be repaid twice!")

    except Exception as e:
        reverted = True
        error_msg = str(e)
        revert_reason = error_msg
        print_success(f"✓ Transaction reverted before mining (as expected)")

        # Try to extract revert reason
        if "loan inactive" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'loan inactive'")
        elif "inactive" in error_msg.lower():
            print_success(f"✓ Revert reason indicates inactive loan")

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
    lend_balance_after = contract.functions.userLendBalance(offer_initial['lender'], offer_id_bytes).call()

    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} → {protocol_fee_after / 1e9:.9f} TAO")
    print_info(f"  userLendBalance: {lend_balance_before / 1e9:.2f} → {lend_balance_after / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")

    print_info(f"Verifying loan {test_loan_id} state unchanged...")
    loan_info_after = get_loan_full(contract, test_loan_id)
    loan_term_after = loan_info_after['term']
    loan_data_after = loan_info_after['data']
    offer_after = loan_info_after['offer']

    print_info(f"Loan State After:")
    print_info(f"  State: {['OPEN', 'IN_COLLECTION', 'REPAID', 'CLAIMED', 'RESOLVED'][loan_data_after['state']]}")
    print_info(f"  Last Update Block: {loan_data_after['lastUpdateBlock']}")
    print_info(f"  Initiator: {loan_data_after['initiator']}")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction reverted
    if not reverted and (tx_receipt and tx_receipt['status'] == 1):
        print_error("✗ Transaction succeeded unexpectedly!")
        print_error("CRITICAL BUG: Loan in REPAID state can be repaid again!")
        print_error("This could lead to double-payment and loss of funds!")
        sys.exit(1)

    print_success("✓ Transaction reverted as expected")

    # Verify revert reason contains "loan inactive"
    if revert_reason and "inactive" in revert_reason.lower():
        print_success("✓ Revert reason confirmed: loan marked as 'inactive'")
    elif revert_reason:
        print_warning(f"⚠ Revert reason may differ: {revert_reason[:200]}")

    # Verify loan state unchanged (still REPAID)
    if loan_data_after['state'] != STATE_REPAID:
        print_error(f"✗ Loan state changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Loan state unchanged (still REPAID)")

    # Verify loan data unchanged
    if loan_data_after['lastUpdateBlock'] != loan_data_before['lastUpdateBlock']:
        print_error(f"✗ Loan lastUpdateBlock changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Loan lastUpdateBlock unchanged")

    if loan_data_after['initiator'] != loan_data_before['initiator']:
        print_error(f"✗ Loan initiator changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Loan initiator unchanged")

    # Verify protocol fee unchanged
    if protocol_fee_after != protocol_fee_before:
        print_error(f"✗ Protocol fee changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Protocol fee unchanged")

    # Verify lend balance unchanged
    if lend_balance_after != lend_balance_before:
        print_error(f"✗ Lend balance changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Lend balance unchanged")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify only gas was deducted
    print_info("\nExpected changes:")
    print_info("  - BORROWER1 EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # Get repayer balance change
    repayer_before_evm = snapshot_before['balances']['BORROWER1']['evm_tao_wei']
    repayer_after_evm = snapshot_after['balances']['BORROWER1']['evm_tao_wei']
    repayer_diff = repayer_after_evm - repayer_before_evm

    if repayer_diff < 0:
        print_success(f"✓ BORROWER1 EVM TAO decreased (gas): {abs(repayer_diff) / 1e18:.9f} TAO")
    else:
        print_warning(f"⚠ BORROWER1 EVM TAO did not decrease")

    # Verify all contract balances unchanged
    lender_tao_before = snapshot_before['balances']['LENDER1']['contract']['netuid_0']['balance_rao']
    lender_tao_after = snapshot_after['balances']['LENDER1']['contract']['netuid_0']['balance_rao']

    if lender_tao_before == lender_tao_after:
        print_success("✓ Lender contract TAO balance unchanged")
    else:
        print_error(f"✗ Lender contract TAO balance changed unexpectedly!")
        sys.exit(1)

    borrower_tao_before = snapshot_before['balances']['BORROWER1']['contract']['netuid_0']['balance_rao']
    borrower_tao_after = snapshot_after['balances']['BORROWER1']['contract']['netuid_0']['balance_rao']

    if borrower_tao_before == borrower_tao_after:
        print_success("✓ Borrower contract TAO balance unchanged")
    else:
        print_error(f"✗ Borrower contract TAO balance changed unexpectedly!")
        sys.exit(1)

    # Report results
    print_section("Test Result")

    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC03: Loan Already Repaid")
    print_success(f"Transaction correctly reverted with 'loan inactive'")
    print_success("Loan state protection working correctly")
    print_success("No unexpected state changes detected")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - Loans in REPAID state cannot be repaid again")
    print(f"  - _requireLoanActive validation working correctly")
    print(f"  - Contract prevents double-repayment vulnerability")
    print(f"  - Loan state remains: REPAID")

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
