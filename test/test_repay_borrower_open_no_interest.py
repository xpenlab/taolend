#!/usr/bin/env python3
"""
Test Case TC09: Success - Borrower Repays OPEN Loan (No Interest)
Objective: Verify successful repayment by borrower immediately after borrowing (minimal interest)
Tests: Successful repay() execution with minimal or zero interest
Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction succeeds, loan state → REPAID, collateral returned
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
    print_section("Test Case TC09: Success - Borrower Repays OPEN Loan (No Interest)")
    print(f"{CYAN}Objective:{NC} Verify successful repayment by borrower with minimal interest")
    print(f"{CYAN}Strategy:{NC} Find OPEN loan, ensure sufficient TAO, repay immediately")
    print(f"{CYAN}Expected:{NC} Success, loan state → REPAID, collateral returned\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender_address = addresses['LENDER1']['evmAddress']
    borrower_address = addresses['BORROWER1']['evmAddress']
    borrower_private_key = os.environ.get("BORROWER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    if not borrower_private_key:
        print_error("Borrower private key not found in .env")
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

    # Find an OPEN loan with minimal elapsed time
    print_info("\nSearching for OPEN loan with minimal elapsed time...")
    next_loan_id = contract.functions.nextLoanId().call()
    current_block = w3.eth.block_number
    print_info(f"Current block: {current_block}")

    best_loan_id = None
    min_elapsed = float('inf')

    for loan_id in range(next_loan_id):
        try:
            loan_info = get_loan_full(contract, loan_id)
            if loan_info is None:
                continue

            loan_term = loan_info['term']
            loan_data = loan_info['data']

            # Check if loan is OPEN and belongs to BORROWER1
            if (loan_data['state'] == STATE_OPEN and
                loan_term['borrower'].lower() == borrower_address.lower()):

                elapsed = current_block - loan_data['startBlock']
                if elapsed < min_elapsed:
                    min_elapsed = elapsed
                    best_loan_id = loan_id

        except Exception as e:
            continue

    if best_loan_id is None:
        print_error("SETUP ERROR: No OPEN loan found for BORROWER1")
        print_info("Please create a loan first")
        sys.exit(1)

    test_loan_id = best_loan_id
    print_success(f"✓ Found OPEN loan: Loan ID {test_loan_id}")
    print_info(f"  Elapsed blocks since start: {min_elapsed}")

    # Get loan details
    loan_info_initial = get_loan_full(contract, test_loan_id)
    loan_term_initial = loan_info_initial['term']
    loan_data_initial = loan_info_initial['data']
    offer_initial = loan_info_initial['offer']
    netuid = loan_term_initial['netuid']

    print_info(f"  Borrower: {loan_term_initial['borrower']}")
    print_info(f"  Loan Amount: {loan_data_initial['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term_initial['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Netuid: {netuid}")

    # Calculate repay amount
    elapsed_blocks = current_block - loan_data_initial['startBlock']
    interest = (loan_data_initial['loanAmount'] * elapsed_blocks * offer_initial['dailyInterestRate']) // (7200 * 10**9)
    repay_amount = loan_data_initial['loanAmount'] + interest
    protocol_fee = (interest * 3000) // 10000
    lender_receives = repay_amount - protocol_fee

    print_info(f"\nRepayment Calculation:")
    print_info(f"  Loan Amount: {loan_data_initial['loanAmount'] / 1e9:.9f} TAO")
    print_info(f"  Elapsed Blocks: {elapsed_blocks}")
    print_info(f"  Interest: {interest / 1e9:.9f} TAO")
    print_info(f"  Repay Amount: {repay_amount / 1e9:.9f} TAO")
    print_info(f"  Protocol Fee (30%): {protocol_fee / 1e9:.9f} TAO")
    print_info(f"  Lender Receives (70%): {lender_receives / 1e9:.9f} TAO")

    # Check borrower has sufficient TAO
    borrower_tao = contract.functions.userAlphaBalance(borrower_address, 0).call()
    print_info(f"\nBORROWER1 TAO balance: {borrower_tao / 1e9:.9f} TAO")

    if borrower_tao < repay_amount:
        print_error(f"SETUP ERROR: Insufficient TAO balance")
        print_error(f"  Required: {repay_amount / 1e9:.9f} TAO")
        print_error(f"  Available: {borrower_tao / 1e9:.9f} TAO")
        print_info("Please deposit more TAO first")
        sys.exit(1)

    print_success(f"✓ BORROWER1 has sufficient TAO for repayment")

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
    print_info(f"  userLendBalance[lender][offerId]: {lend_balance_before / 1e9:.9f} TAO")

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
    print_info(f"  Loan Amount: {loan_data_before['loanAmount'] / 1e9:.9f} TAO")
    print_info(f"  Collateral: {loan_term_before['collateralAmount'] / 1e9:.9f} ALPHA")
    print_info(f"  Start Block: {loan_data_before['startBlock']}")

    # Verify state is OPEN
    if loan_data_before['state'] != STATE_OPEN:
        print_error(f"ERROR: Loan state is not OPEN!")
        sys.exit(1)
    print_success(f"✓ Loan state confirmed: OPEN")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute repay()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds")
    print(f"  {CYAN}Loan State:{NC} OPEN → REPAID")
    print(f"  {CYAN}Collateral:{NC} Returned to borrower")
    print(f"  {CYAN}TAO Flow:{NC}")
    print(f"    - Borrower pays: {repay_amount / 1e9:.9f} TAO")
    print(f"    - Lender receives: {lender_receives / 1e9:.9f} TAO")
    print(f"    - Protocol fee: {protocol_fee / 1e9:.9f} TAO")
    print(f"  {CYAN}Collateral Return:{NC}")
    print(f"    - Borrower receives: {loan_term_before['collateralAmount'] / 1e9:.9f} ALPHA")
    print()

    print_info(f"Repaying loan {test_loan_id}...")
    print_info(f"Borrower: {borrower_address} (BORROWER1)")

    # Execute transaction
    tx_receipt = None
    succeeded = False

    try:
        tx = contract.functions.repay(test_loan_id).build_transaction({
            'from': borrower_address,
            'nonce': w3.eth.get_transaction_count(borrower_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
        })

        signed_tx = w3.eth.account.sign_transaction(tx, borrower_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        if tx_receipt['status'] == 1:
            succeeded = True
            print_success("✓ Transaction succeeded!")
        else:
            print_error("✗ Transaction reverted (unexpected)")

    except Exception as e:
        print_error(f"✗ Transaction failed: {str(e)[:300]}")
        sys.exit(1)

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
    print_info(f"  userLendBalance: {lend_balance_before / 1e9:.9f} → {lend_balance_after / 1e9:.9f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")

    print_info(f"Reading loan state for loan ID {test_loan_id}...")
    loan_info_after = get_loan_full(contract, test_loan_id)
    loan_term_after = loan_info_after['term']
    loan_data_after = loan_info_after['data']
    offer_after = loan_info_after['offer']

    print_info(f"Loan State After:")
    print_info(f"  State: {['OPEN', 'IN_COLLECTION', 'REPAID', 'CLAIMED', 'RESOLVED'][loan_data_after['state']]}")
    print_info(f"  Last Update Block: {loan_data_after['lastUpdateBlock']}")
    print_info(f"  Initiator (Repayer): {loan_data_after['initiator']}")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction succeeded
    if not succeeded:
        print_error("✗ Transaction did not succeed!")
        sys.exit(1)
    print_success("✓ Transaction succeeded")

    # Verify loan state changed to REPAID
    if loan_data_after['state'] != STATE_REPAID:
        print_error(f"✗ Loan state is not REPAID! Current: {loan_data_after['state']}")
        sys.exit(1)
    print_success("✓ Loan state: OPEN → REPAID")

    # Verify initiator is borrower
    if loan_data_after['initiator'].lower() != borrower_address.lower():
        print_error(f"✗ Loan initiator is not borrower!")
        sys.exit(1)
    print_success("✓ Loan initiator: BORROWER1 (repayer)")

    # Recalculate expected values using actual repay block
    print_info("\nRecalculating expected values with actual repay block...")
    repay_block = loan_data_after['lastUpdateBlock']
    actual_elapsed = repay_block - loan_data_before['startBlock']
    actual_interest = (loan_data_before['loanAmount'] * actual_elapsed * offer_before['dailyInterestRate']) // (7200 * 10**9)
    actual_repay_amount = loan_data_before['loanAmount'] + actual_interest
    actual_protocol_fee = (actual_interest * 3000) // 10000
    actual_lender_receives = actual_repay_amount - actual_protocol_fee

    print_info(f"  Repay Block: {repay_block}")
    print_info(f"  Actual Elapsed Blocks: {actual_elapsed}")
    print_info(f"  Actual Interest: {actual_interest / 1e9:.9f} TAO")
    print_info(f"  Actual Repay Amount: {actual_repay_amount / 1e9:.9f} TAO")
    print_info(f"  Actual Protocol Fee: {actual_protocol_fee / 1e9:.9f} TAO")
    print_info(f"  Actual Lender Receives: {actual_lender_receives / 1e9:.9f} TAO")

    # Verify protocol fee increased
    protocol_fee_increase = protocol_fee_after - protocol_fee_before
    if abs(protocol_fee_increase - actual_protocol_fee) > 1:  # Allow 1 RAO tolerance
        print_error(f"✗ Protocol fee increase mismatch!")
        print_error(f"  Expected: {actual_protocol_fee / 1e9:.9f} TAO")
        print_error(f"  Actual: {protocol_fee_increase / 1e9:.9f} TAO")
        sys.exit(1)
    print_success(f"✓ Protocol fee increased by {protocol_fee_increase / 1e9:.9f} TAO")

    # Verify lend balance decreased
    lend_balance_decrease = lend_balance_before - lend_balance_after
    if abs(lend_balance_decrease - loan_data_before['loanAmount']) > 1:
        print_error(f"✗ Lend balance decrease mismatch!")
        sys.exit(1)
    print_success(f"✓ Lend balance decreased by {lend_balance_decrease / 1e9:.9f} TAO")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify balance changes (using actual values)
    print_info("\nVerifying balance changes...")

    # Borrower TAO: should decrease by actual_repay_amount
    borrower_tao_before = snapshot_before['balances']['BORROWER1']['contract']['netuid_0']['balance_rao']
    borrower_tao_after = snapshot_after['balances']['BORROWER1']['contract']['netuid_0']['balance_rao']
    borrower_tao_change = borrower_tao_after - borrower_tao_before

    if abs(borrower_tao_change + actual_repay_amount) > 1:
        print_error(f"✗ Borrower TAO change mismatch!")
        print_error(f"  Expected: -{actual_repay_amount / 1e9:.9f} TAO")
        print_error(f"  Actual: {borrower_tao_change / 1e9:.9f} TAO")
        sys.exit(1)
    print_success(f"✓ Borrower TAO decreased: {abs(borrower_tao_change) / 1e9:.9f} TAO")

    # Borrower ALPHA: should increase by collateral amount
    borrower_alpha_before = snapshot_before['balances']['BORROWER1']['contract'][f'netuid_{netuid}']['balance_rao']
    borrower_alpha_after = snapshot_after['balances']['BORROWER1']['contract'][f'netuid_{netuid}']['balance_rao']
    borrower_alpha_change = borrower_alpha_after - borrower_alpha_before

    if abs(borrower_alpha_change - loan_term_before['collateralAmount']) > 1:
        print_error(f"✗ Borrower ALPHA change mismatch!")
        print_error(f"  Expected: +{loan_term_before['collateralAmount'] / 1e9:.9f} ALPHA")
        print_error(f"  Actual: {borrower_alpha_change / 1e9:.9f} ALPHA")
        sys.exit(1)
    print_success(f"✓ Borrower ALPHA increased (collateral returned): {borrower_alpha_change / 1e9:.9f} ALPHA")

    # Lender TAO: should increase by actual_lender_receives
    lender_tao_before = snapshot_before['balances']['LENDER1']['contract']['netuid_0']['balance_rao']
    lender_tao_after = snapshot_after['balances']['LENDER1']['contract']['netuid_0']['balance_rao']
    lender_tao_change = lender_tao_after - lender_tao_before

    if abs(lender_tao_change - actual_lender_receives) > 1:
        print_error(f"✗ Lender TAO change mismatch!")
        print_error(f"  Expected: +{actual_lender_receives / 1e9:.9f} TAO")
        print_error(f"  Actual: {lender_tao_change / 1e9:.9f} TAO")
        sys.exit(1)
    print_success(f"✓ Lender TAO increased: {lender_tao_change / 1e9:.9f} TAO")

    # Report results
    print_section("Test Result")

    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC09: Success - Borrower Repays OPEN Loan (No Interest)")
    print_success("Repayment completed successfully")
    print_success("All state validations passed")
    print_success("All balance changes verified")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - Loan successfully repaid by borrower")
    print(f"  - Loan state: OPEN → REPAID")
    print(f"  - Borrower paid: {actual_repay_amount / 1e9:.9f} TAO")
    print(f"  - Lender received: {actual_lender_receives / 1e9:.9f} TAO")
    print(f"  - Protocol fee: {actual_protocol_fee / 1e9:.9f} TAO")
    print(f"  - Collateral returned: {loan_term_before['collateralAmount'] / 1e9:.9f} ALPHA")
    print(f"  - Interest accrued: {actual_interest / 1e9:.9f} TAO")
    print(f"  - Elapsed blocks: {actual_elapsed}")

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
