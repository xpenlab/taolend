#!/usr/bin/env python3
"""
Test Case TC18: Third Party, IN_COLLECTION State, Success
Objective: Verify successful transfer by third party from IN_COLLECTION state
Tests: Third party (not original lender) can transfer IN_COLLECTION loans

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction succeeds, third party initiates transfer to new lender
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
    offer_to_tuple, load_offer_from_file,
    STATE_OPEN, STATE_IN_COLLECTION, STATE_REPAID, STATE_NAMES
)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Color codes for output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_section(title):
    print(f"\n{'='*80}")
    print(f"{Colors.BOLD}{title}{Colors.ENDC}")
    print(f"{'='*80}")

def print_info(msg):
    print(f"{Colors.CYAN}[INFO]{Colors.ENDC} {msg}")

def print_success(msg):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.ENDC} {msg}")

def print_error(msg):
    print(f"{Colors.RED}[ERROR]{Colors.ENDC} {msg}")

def print_warning(msg):
    print(f"{Colors.BOLD}{Colors.YELLOW}[WARNING]{Colors.ENDC} {msg}")

def calculate_repay_amount(loan_amount_rao, start_block, current_block, daily_rate):
    """Calculate expected repay amount and protocol fee"""
    BLOCKS_PER_DAY = 7200
    PRICE_BASE = int(1e9)
    FEE_RATE = 3000  # 30%
    RATE_BASE = 10000

    elapsed_blocks = current_block - start_block
    interest = (loan_amount_rao * elapsed_blocks * daily_rate) // (BLOCKS_PER_DAY * PRICE_BASE)
    repay_amount = loan_amount_rao + interest
    protocol_fee = (interest * FEE_RATE) // RATE_BASE

    return repay_amount, protocol_fee, interest

def main():
    """Test successful transfer by third party from IN_COLLECTION state"""

    print_section("Test Case TC18: Third Party, IN_COLLECTION State, Success")
    print(f"{Colors.CYAN}Objective:{Colors.ENDC} Verify successful transfer by third party from IN_COLLECTION state")
    print(f"{Colors.CYAN}Strategy:{Colors.ENDC} THIRD_PARTY (not old lender) transfers IN_COLLECTION loan to NEW_LENDER")
    print(f"{Colors.CYAN}Expected:{Colors.ENDC} Transaction succeeds, anyone can transfer IN_COLLECTION loans")

    # Load configuration
    print_info("\nSetting up test environment...")
    addresses = load_addresses()

    # Connect to network
    rpc_url = os.environ.get('RPC_URL', 'http://127.0.0.1:9945')
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print_error("Failed to connect to network")
        return 1

    print_success(f"Connected to Bittensor EVM (Chain ID: {w3.eth.chain_id})")

    # Load contract
    contract_abi = load_contract_abi()
    contract = w3.eth.contract(address=LENDING_POOL_V2_ADDRESS, abi=contract_abi)

    # Test accounts - Use loan ID 9
    loan_id = 9

    print_info(f"Using Loan ID {loan_id} (netuid 3)")

    # ========================================================================
    # Step 0: Verify Setup Conditions & Move to IN_COLLECTION
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions & Move to IN_COLLECTION")

    # Find loan first to determine current lender
    loan_full = get_loan_full(contract, loan_id)

    if loan_full is None:
        print_error(f"Loan {loan_id} not found")
        return 1

    loan_term = loan_full['term']
    loan_data = loan_full['data']
    offer_data = loan_full['offer']

    loan_netuid = loan_term['netuid']
    old_lender_from_loan = offer_data['lender']

    # Set accounts - THIRD_PARTY is BORROWER1 (the borrower, different from lenders)
    if old_lender_from_loan.lower() == addresses['LENDER1']['evmAddress'].lower():
        old_lender_address = addresses['LENDER1']['evmAddress']
        old_lender_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
        new_lender_address = addresses['LENDER2']['evmAddress']
        new_offer_file = "offers/290f8994967f7a9cb583843fe0933d91dfa02ea3bfc4a9b3c6509bd4ca03bc39.json"
    else:
        old_lender_address = addresses['LENDER2']['evmAddress']
        old_lender_private_key = os.environ.get("LENDER2_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
        new_lender_address = addresses['LENDER1']['evmAddress']
        new_offer_file = "offers/959ef93720143532e0192a296ede97d4377c39e68a49865638382a6b8575295d.json"

    borrower_address = addresses['BORROWER1']['evmAddress']

    # Third party is the borrower (interesting case: borrower can transfer IN_COLLECTION loans)
    third_party_address = borrower_address
    third_party_private_key = os.environ.get("BORROWER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    # Verify third party is different from old lender
    if third_party_address.lower() == old_lender_from_loan.lower():
        print_error(f"⚠ Test setup error: Third party is same as old lender")
        return 1

    # Verify accounts are registered
    is_registered_tp = contract.functions.registeredUser(third_party_address).call()
    if not is_registered_tp:
        print_error(f"THIRD_PARTY must be registered for this test")
        return 1
    print_success(f"✓ THIRD_PARTY registered: {third_party_address}")

    is_registered_new = contract.functions.registeredUser(new_lender_address).call()
    if not is_registered_new:
        print_error(f"NEW_LENDER must be registered for this test")
        return 1
    print_success(f"✓ NEW_LENDER registered: {new_lender_address}")

    current_state = loan_data['state']
    print_info(f"\nCurrent Loan State: {STATE_NAMES[current_state]}")
    print_info(f"  Loan Netuid: {loan_netuid}")
    print_info(f"  Borrower: {loan_term['borrower']}")
    print_info(f"  Old Lender: {old_lender_from_loan}")
    print_info(f"  Third Party (Initiator): {third_party_address}")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Start Block: {loan_data['startBlock']}")

    # If loan is OPEN, need old lender to collect first
    if current_state == STATE_OPEN:
        print_warning("Loan is in OPEN state, OLD_LENDER needs to call collect() first")

        # Check MIN_LOAN_DURATION for collect
        current_block = w3.eth.block_number
        MIN_LOAN_DURATION = contract.functions.MIN_LOAN_DURATION().call()
        elapsed_blocks = current_block - loan_data['startBlock']

        print_info(f"\nTiming Check for collect():")
        print_info(f"  Current Block: {current_block}")
        print_info(f"  Blocks Elapsed: {elapsed_blocks}")
        print_info(f"  MIN_LOAN_DURATION: {MIN_LOAN_DURATION}")

        if elapsed_blocks <= MIN_LOAN_DURATION:
            print_error(f"✗ Too early to collect: need {MIN_LOAN_DURATION - elapsed_blocks} more blocks")
            return 1

        print_success(f"✓ MIN_LOAN_DURATION satisfied (elapsed: {elapsed_blocks} > {MIN_LOAN_DURATION})")

        # OLD_LENDER calls collect()
        print_info(f"\nOLD_LENDER calling collect() to move loan to IN_COLLECTION state...")
        nonce = w3.eth.get_transaction_count(old_lender_address)

        tx = contract.functions.collect(loan_id).build_transaction({
            'from': old_lender_address,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, old_lender_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Collect transaction sent: {tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print_info(f"Collect transaction mined in block {receipt['blockNumber']}")

        if receipt['status'] == 1:
            print_success("✓ collect() succeeded")
        else:
            print_error("❌ collect() failed")
            return 1

        # Re-read loan state
        loan_full = get_loan_full(contract, loan_id)
        loan_data = loan_full['data']
        current_state = loan_data['state']
        print_success(f"✓ Loan state now: {STATE_NAMES[current_state]}")

    # Verify loan is now in IN_COLLECTION
    if current_state != STATE_IN_COLLECTION:
        print_error(f"Loan is not in IN_COLLECTION state (current: {STATE_NAMES[current_state]})")
        return 1

    print_success(f"✓ Loan in IN_COLLECTION state")

    # Load new offer
    print_info(f"\nLoading new offer...")
    new_offer = load_offer_from_file(new_offer_file)

    offer_netuid = new_offer['netuid']
    new_offer_lender = new_offer['lender']
    new_offer_id = new_offer['offerId']

    print_success("✓ New offer loaded from file")
    print_info(f"  Offer ID: {new_offer_id}")
    print_info(f"  Offer Netuid: {offer_netuid}")
    print_info(f"  Offer Lender: {new_offer_lender}")
    print_info(f"  Daily Rate: {new_offer['dailyInterestRate'] / 1e9 * 100:.4f}%")
    print_info(f"  Max Alpha Price: {new_offer['maxAlphaPrice'] / 1e9:.9f} TAO/ALPHA")

    # Verify netuid matches
    if offer_netuid != loan_netuid:
        print_error(f"⚠ Test setup error: Offer netuid ({offer_netuid}) doesn't match loan netuid ({loan_netuid})")
        return 1

    # Verify lender is different
    if new_offer_lender.lower() == old_lender_from_loan.lower():
        print_error(f"⚠ Test setup error: New lender is same as old lender")
        return 1

    print_success("✓ All setup conditions satisfied")

    # Calculate expected repay amount
    current_block = w3.eth.block_number
    repay_amount, protocol_fee, interest = calculate_repay_amount(
        loan_data['loanAmount'],
        loan_data['startBlock'],
        current_block,
        offer_data['dailyInterestRate']
    )

    elapsed_blocks = current_block - loan_data['startBlock']
    print_info(f"\nExpected Repayment Calculation:")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Blocks Elapsed: {elapsed_blocks}")
    print_info(f"  Daily Rate: {offer_data['dailyInterestRate'] / 1e9 * 100:.4f}%")
    print_info(f"  Interest Accrued: {interest / 1e9:.9f} TAO")
    print_info(f"  Repay Amount: {repay_amount / 1e9:.9f} TAO")
    print_info(f"  Protocol Fee (30%): {protocol_fee / 1e9:.9f} TAO")
    print_info(f"  Old Lender Receives: {(repay_amount - protocol_fee) / 1e9:.9f} TAO")

    # Check NEW_LENDER has enough TAO
    new_lender_balance = contract.functions.userAlphaBalance(new_lender_address, 0).call()
    print_info(f"\nNEW_LENDER TAO Balance: {new_lender_balance / 1e9:.2f} TAO")
    if new_lender_balance < repay_amount:
        print_error(f"✗ NEW_LENDER has insufficient TAO ({new_lender_balance / 1e9:.2f} < {repay_amount / 1e9:.2f})")
        return 1
    print_success(f"✓ NEW_LENDER has sufficient TAO")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")
    print_info("Capturing initial state snapshot...")

    # Setup BalanceChecker
    test_netuids = [0, loan_netuid]
    checker = BalanceChecker(w3, contract, test_netuids)

    # Capture initial snapshot
    snapshot_accounts = [
        {'label': 'OLD_LENDER', 'address': old_lender_address},
        {'label': 'NEW_LENDER', 'address': new_lender_address},
        {'label': 'THIRD_PARTY', 'address': third_party_address},
        {'label': 'BORROWER1', 'address': borrower_address},
        {'label': 'CONTRACT', 'address': contract.address}
    ]

    before_snapshot = checker.capture_snapshot(snapshot_accounts, include_staking=False)
    checker.print_snapshot(before_snapshot)

    # Query specific contract state
    protocol_fee_before = contract.functions.protocolFeeAccumulated().call()
    old_lender_lend_balance_before = contract.functions.userLendBalance(old_lender_address, offer_data['offerId']).call()
    new_lender_lend_balance_before = contract.functions.userLendBalance(new_lender_address, new_offer_id).call()

    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance[{offer_data['offerId'][:10]}...]: {old_lender_lend_balance_before / 1e9:.2f} TAO")
    print_info(f"  NEW_LENDER userLendBalance[{new_offer_id[:10]}...]: {new_lender_lend_balance_before / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info(f"Reading loan state for loan ID {loan_id}...")

    loan_before = get_loan_full(contract, loan_id)
    loan_term_before = loan_before['term']
    loan_data_before = loan_before['data']
    offer_before = loan_before['offer']

    print_info(f"Loan State Before:")
    print_info(f"  Loan Data ID: {loan_term_before['loanDataId']}")
    print_info(f"  State: {STATE_NAMES[loan_data_before['state']]}")
    print_info(f"  Netuid: {loan_term_before['netuid']}")
    print_info(f"  Lender: {offer_before['lender']}")
    print_info(f"  Borrower: {loan_term_before['borrower']}")
    print_info(f"  Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Old Offer ID: {offer_before['offerId'][:10]}...")

    # ========================================================================
    # STEP 4: Execute transfer() by THIRD_PARTY
    # ========================================================================
    print_section("Step 4: Execute transfer() by THIRD_PARTY")

    print(f"\n{Colors.BOLD}Expected Result:{Colors.ENDC}")
    print(f"  {Colors.GREEN}Success:{Colors.ENDC} Transfer completes successfully by THIRD_PARTY")
    print(f"  {Colors.CYAN}Note:{Colors.ENDC} Anyone can transfer IN_COLLECTION loans")
    print(f"  {Colors.CYAN}State Changes:{Colors.ENDC}")
    print(f"    - Old loan data: state → REPAID")
    print(f"    - New loan data created: state = OPEN")
    print(f"    - loanTerm.loanDataId updated to new loan data ID")

    print_info(f"\nAttempting to transfer loan {loan_id}...")
    print_info(f"Initiator: {third_party_address} (THIRD_PARTY, NOT old lender)")
    print_info(f"Old Lender: {old_lender_from_loan}")
    print_info(f"New Lender: {new_offer_lender}")
    print_info(f"Loan State: {STATE_NAMES[loan_data_before['state']]} (IN_COLLECTION)")

    # Build transaction
    nonce = w3.eth.get_transaction_count(third_party_address)

    # Convert offer to tuple format (includes signature)
    offer_tuple = offer_to_tuple(new_offer)

    tx = contract.functions.transfer(
        loan_id,
        offer_tuple
    ).build_transaction({
        'from': third_party_address,
        'nonce': nonce,
        'gas': 1000000,
        'gasPrice': w3.eth.gas_price
    })

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, third_party_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print_info(f"Transaction sent: {tx_hash.hex()}")

    # Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print_info(f"Transaction mined in block {receipt['blockNumber']}")

    # Check transaction status
    if receipt['status'] == 1:
        print_success("✓ Transaction succeeded")
    else:
        print_error("❌ Transaction failed - UNEXPECTED!")
        return 1

    # Recalculate expected repay amount using actual transaction block
    actual_elapsed_blocks = receipt['blockNumber'] - loan_data_before['startBlock']
    actual_repay_amount, actual_protocol_fee, actual_interest = calculate_repay_amount(
        loan_data_before['loanAmount'],
        loan_data_before['startBlock'],
        receipt['blockNumber'],
        offer_before['dailyInterestRate']
    )

    print_info(f"\nActual Repayment (at block {receipt['blockNumber']}):")
    print_info(f"  Blocks Elapsed: {actual_elapsed_blocks}")
    print_info(f"  Interest Accrued: {actual_interest / 1e9:.9f} TAO")
    print_info(f"  Repay Amount: {actual_repay_amount / 1e9:.9f} TAO")
    print_info(f"  Protocol Fee (30%): {actual_protocol_fee / 1e9:.9f} TAO")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")
    print_info("Capturing final state snapshot...")

    after_snapshot = checker.capture_snapshot(snapshot_accounts, include_staking=False)
    checker.print_snapshot(after_snapshot)

    # Query contract state after
    protocol_fee_after = contract.functions.protocolFeeAccumulated().call()
    old_lender_lend_balance_after = contract.functions.userLendBalance(old_lender_address, offer_data['offerId']).call()
    new_lender_lend_balance_after = contract.functions.userLendBalance(new_lender_address, new_offer_id).call()

    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} → {protocol_fee_after / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance: {old_lender_lend_balance_before / 1e9:.2f} → {old_lender_lend_balance_after / 1e9:.2f} TAO")
    print_info(f"  NEW_LENDER userLendBalance: {new_lender_lend_balance_before / 1e9:.2f} → {new_lender_lend_balance_after / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info(f"Reading loan state for loan ID {loan_id}...")

    loan_after = get_loan_full(contract, loan_id)
    loan_term_after = loan_after['term']
    loan_data_after = loan_after['data']
    offer_after = loan_after['offer']

    print_info(f"Loan State After:")
    print_info(f"  Loan Data ID: {loan_term_after['loanDataId']} (was: {loan_term_before['loanDataId']})")
    print_info(f"  State: {STATE_NAMES[loan_data_after['state']]}")
    print_info(f"  Netuid: {loan_term_after['netuid']}")
    print_info(f"  Lender: {offer_after['lender']}")
    print_info(f"  Borrower: {loan_term_after['borrower']}")
    print_info(f"  Loan Amount: {loan_data_after['loanAmount'] / 1e9:.9f} TAO")
    print_info(f"  Collateral: {loan_term_after['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  New Offer ID: {offer_after['offerId'][:10]}...")

    # Query old loan data
    old_loan_data_id = loan_term_before['loanDataId']
    old_loan_data_raw = contract.functions.loanRecords(old_loan_data_id).call()
    old_loan_data_state = old_loan_data_raw[5]  # state is at index 5
    print_info(f"\nOld Loan Data (ID {old_loan_data_id}):")
    print_info(f"  State: {STATE_NAMES[old_loan_data_state]}")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction succeeded
    if receipt['status'] == 1:
        print_success("✓ Transaction succeeded")
    else:
        print_error("❌ Transaction did not succeed")
        return 1

    # Verify initiator is third party (not old lender)
    if third_party_address.lower() != old_lender_from_loan.lower():
        print_success(f"✓ Initiator is THIRD_PARTY (not old lender)")
    else:
        print_error(f"❌ Test setup error: Initiator should be third party")
        return 1

    # Verify loan data ID changed (new loan data created)
    if loan_term_after['loanDataId'] != loan_term_before['loanDataId']:
        print_success(f"✓ Loan Data ID changed: {loan_term_before['loanDataId']} → {loan_term_after['loanDataId']}")
    else:
        print_error(f"❌ Loan Data ID unchanged")
        return 1

    # Verify old loan data state is REPAID
    if old_loan_data_state == STATE_REPAID:
        print_success(f"✓ Old loan data state = REPAID")
    else:
        print_error(f"❌ Old loan data state = {STATE_NAMES.get(old_loan_data_state, 'UNKNOWN')} (expected REPAID)")
        return 1

    # Verify new loan data state is OPEN
    if loan_data_after['state'] == STATE_OPEN:
        print_success(f"✓ New loan data state = OPEN")
    else:
        print_error(f"❌ New loan data state = {STATE_NAMES[loan_data_after['state']]} (expected OPEN)")
        return 1

    # Verify lender changed
    if offer_after['lender'].lower() == new_offer_lender.lower():
        print_success(f"✓ Lender changed to NEW_LENDER")
    else:
        print_error(f"❌ Lender not changed correctly")
        return 1

    # Verify borrower unchanged
    if loan_term_after['borrower'].lower() == loan_term_before['borrower'].lower():
        print_success(f"✓ Borrower unchanged")
    else:
        print_error(f"❌ Borrower changed")
        return 1

    # Verify collateral unchanged
    if loan_term_after['collateralAmount'] == loan_term_before['collateralAmount']:
        print_success(f"✓ Collateral unchanged")
    else:
        print_error(f"❌ Collateral changed")
        return 1

    # Verify new loan amount equals actual repay amount
    if loan_data_after['loanAmount'] == actual_repay_amount:
        print_success(f"✓ New loan amount = repay amount ({actual_repay_amount / 1e9:.9f} TAO)")
    else:
        print_error(f"❌ New loan amount ({loan_data_after['loanAmount'] / 1e9:.9f}) != repay amount ({actual_repay_amount / 1e9:.9f})")
        return 1

    # Verify protocol fee increased
    expected_protocol_fee_increase = actual_protocol_fee
    actual_protocol_fee_increase = protocol_fee_after - protocol_fee_before
    if actual_protocol_fee_increase == expected_protocol_fee_increase:
        print_success(f"✓ Protocol fee increased by {actual_protocol_fee / 1e9:.9f} TAO")
    else:
        print_error(f"❌ Protocol fee increase mismatch: {actual_protocol_fee_increase / 1e9:.9f} != {expected_protocol_fee_increase / 1e9:.9f}")
        return 1

    # Verify OLD_LENDER lend balance decreased
    expected_old_decrease = loan_data_before['loanAmount']
    actual_old_decrease = old_lender_lend_balance_before - old_lender_lend_balance_after
    if actual_old_decrease == expected_old_decrease:
        print_success(f"✓ OLD_LENDER lend balance decreased by {expected_old_decrease / 1e9:.2f} TAO")
    else:
        print_error(f"❌ OLD_LENDER lend balance change mismatch")
        return 1

    # Verify NEW_LENDER lend balance increased
    expected_new_increase = actual_repay_amount
    actual_new_increase = new_lender_lend_balance_after - new_lender_lend_balance_before
    if actual_new_increase == expected_new_increase:
        print_success(f"✓ NEW_LENDER lend balance increased by {expected_new_increase / 1e9:.9f} TAO")
    else:
        print_error(f"❌ NEW_LENDER lend balance change mismatch")
        return 1

    # ========================================================================
    # Balance Changes
    # ========================================================================
    print_section("Balance Changes")

    diff = checker.diff_snapshots(before_snapshot, after_snapshot)
    checker.print_diff(diff)

    # ========================================================================
    # Test Result
    # ========================================================================
    print_section("Test Result")
    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC18: Third Party, IN_COLLECTION State, Success")
    print_success("Transfer by third party completed successfully")
    print_success("All state validations passed")
    print_success("All balance changes verified")

    print(f"\n{Colors.CYAN}Summary:{Colors.ENDC}")
    print(f"  - Loan successfully transferred by THIRD_PARTY (not old lender)")
    print(f"  - Initial state: IN_COLLECTION")
    print(f"  - Old loan data marked as REPAID")
    print(f"  - New loan data created with state OPEN")
    print(f"  - Loan amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO → {loan_data_after['loanAmount'] / 1e9:.9f} TAO (repay amount)")
    print(f"  - Blocks elapsed: {actual_elapsed_blocks}")
    print(f"  - Interest accrued: {actual_interest / 1e9:.9f} TAO")
    print(f"  - Protocol fee collected: {actual_protocol_fee / 1e9:.9f} TAO")
    print(f"  - Anyone can transfer IN_COLLECTION loans ✓")

    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
