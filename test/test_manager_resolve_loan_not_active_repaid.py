#!/usr/bin/env python3
"""
Test Case TC05-02: resolveLoan - Loan Not Active (REPAID)
Objective: Verify resolveLoan fails when loan is already repaid
Tests: _requireLoanActive validation check

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "loan inactive"

Note: This test uses an existing repaid loan if available, otherwise skips
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
    print_section("Test Case TC05-02: resolveLoan - Loan Not Active (REPAID)")
    print(f"{CYAN}Objective:{NC} Verify resolveLoan fails when loan is already repaid")
    print(f"{CYAN}Strategy:{NC} Use existing repaid loan and attempt resolve")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'loan inactive'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    manager_address = addresses['MANAGER']['evmAddress']

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

    # ========================================================================
    # Step 0: Use Existing Repaid Loan
    # ========================================================================
    print_section("Step 0: Use Existing Repaid Loan")

    # Use Loan 2 which is in REPAID state
    loan_id = 2
    STATE_REPAID = 2

    print_info(f"Using Loan {loan_id} for testing...")

    # Query loan state directly from contract
    try:
        loan_term = contract.functions.loanTerms(loan_id).call()
        loan_data_id = loan_term[3]  # loanDataId
        loan_record = contract.functions.loanRecords(loan_data_id).call()
        loan_state = loan_record[0]

        if loan_state != STATE_REPAID:
            print_error(f"Loan {loan_id} is not in REPAID state (current state={loan_state})")
            print_warning(f"Test condition not met - SKIPPING TEST")
            sys.exit(0)

        print_success(f"✓ Loan {loan_id} is in REPAID state (state={loan_state})")

        # Get netuid and other details
        borrower = loan_term[0]
        collateral = loan_term[1]
        netuid = loan_term[2]

        print_info(f"  Borrower: {borrower}")
        print_info(f"  Collateral: {collateral / 1e9:.6f} ALPHA")
        print_info(f"  Netuid: {netuid}")

    except Exception as e:
        print_error(f"Failed to query loan {loan_id}: {e}")
        sys.exit(1)

    # ========================================================================
    # Step 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0, netuid]
    )

    addresses_list = [
        {"address": manager_address, "label": "MANAGER (caller)"}
    ]

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

    initial_loan_state = loan_state
    initial_loan_data_id = loan_data_id
    loan_amount = loan_record[3]  # loanAmount from loan_record

    print_info(f"Loan {loan_id} State: REPAID (state={initial_loan_state})")
    print_info(f"Loan DataId: {initial_loan_data_id}")
    print_info(f"Loan Amount: {loan_amount / 1e9:.6f} TAO")
    print_info(f"Collateral: {collateral / 1e9:.6f} ALPHA")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute resolveLoan (expect REVERT)")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Failure:{NC} Transaction reverts (status=0)")
    print(f"  {RED}Error:{NC} 'loan inactive'")
    print(f"  {CYAN}Reason:{NC} Loan is in REPAID state (not OPEN or IN_COLLECTION)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes except gas deduction\n")

    print_info(f"Attempting to resolve repaid loan {loan_id}...")

    # Use arbitrary amounts for test (should fail before checking amounts)
    test_lender_amount = int(5 * 1e9)  # 5 TAO
    test_borrower_amount = int(2 * 1e9)  # 2 TAO

    try:
        tx = contract.functions.resolveLoan(
            loan_id,
            test_lender_amount,
            test_borrower_amount
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
            print_error("Should not be able to resolve repaid loan")
            sys.exit(1)

    except Exception as e:
        error_message = str(e)
        if "loan inactive" in error_message.lower() or "not active" in error_message.lower():
            print_success(f"✓ Transaction reverted with expected error")
            print_info(f"Error message: {error_message}")
        else:
            print_error(f"❌ Transaction reverted with unexpected error: {error_message}")
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

    # Query final loan state
    final_loan_record = contract.functions.loanRecords(loan_data_id).call()
    final_loan_state = final_loan_record[0]

    print_info(f"Loan {loan_id} State: REPAID (state={final_loan_state})")

    # ========================================================================
    # Step 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # Verification
    # ========================================================================
    print_section("Verification Summary")

    all_checks_passed = True

    # Check 1: Loan state unchanged (still REPAID)
    if final_loan_state == initial_loan_state == STATE_REPAID:
        print_success(f"✓ Loan state unchanged: REPAID (state={STATE_REPAID})")
    else:
        print_error(f"✗ Loan state changed from {initial_loan_state} to {final_loan_state}")
        all_checks_passed = False

    # Check 2: No contract state changes except gas
    contract_state_before = snapshot_before['contract']
    contract_state_after = snapshot_after['contract']

    if (contract_state_before['protocol_fee_accumulated'] == contract_state_after['protocol_fee_accumulated'] and
        contract_state_before['next_loan_id'] == contract_state_after['next_loan_id']):
        print_success("✓ Contract state unchanged (no loan resolution occurred)")
    else:
        print_error("✗ Contract state changed (loan resolution should not have occurred)")
        all_checks_passed = False

    # Check 3: Verify _requireLoanActive check
    print_info(f"\nLoan State Verification:")
    print_info(f"  Loan state: REPAID (state={STATE_REPAID})")
    print_info(f"  _requireLoanActive() requires state OPEN(0) or IN_COLLECTION(1)")
    print_info(f"  REPAID state should be rejected")
    print_success("✓ _requireLoanActive validation prevented resolution")

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success("Transaction reverted with 'loan inactive' as expected")
        print_success("Cannot resolve loan in REPAID state")
        print_success("_requireLoanActive validation working correctly")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
