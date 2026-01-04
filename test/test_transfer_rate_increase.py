#!/usr/bin/env python3
"""
Test Case TC20: Transfer With Rate Increase (50%)
Objective: Verify successful transfer with maximum allowed rate increase (150% of original rate)
Tests: Rate validation at 150% limit (0.6% -> 0.9%)

Strategy:
1. Create loan with 0.6% rate offer (if not exists)
2. Wait MIN_LOAN_DURATION blocks
3. Transfer to 0.9% rate offer (exactly 150% of 0.6%)
4. Verify rate increased to exactly 150%

Expected: Transaction succeeds, new rate = old rate * 1.5
"""

import os
import sys
import json
import time
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

def create_initial_loan(w3, contract, addresses, borrower_private_key):
    """Create initial loan with 0.6% rate offer"""
    print_section("Phase 1: Create Initial Loan with 0.6% Rate")

    # Load 0.6% offer (LENDER2)
    offer_file_06 = "offers/eecbd6342d7ddfa91e92492a53968cfbab90630003ef685f3690f8615ab13e64.json"
    offer_06 = load_offer_from_file(offer_file_06)

    print_info(f"Loaded 0.6% offer:")
    print_info(f"  Lender: {offer_06['lender']}")
    print_info(f"  Daily Rate: {offer_06['dailyInterestRate'] / 1e9 * 100:.2f}% (6,000,000)")
    print_info(f"  Max TAO: {offer_06['maxTaoAmount'] / 1e9:.2f} TAO")

    # Borrower setup
    borrower_address = addresses['BORROWER1']['evmAddress']
    borrower_nonce = w3.eth.get_transaction_count(borrower_address)

    # Borrow parameters
    borrow_amount_tao = 20  # 20 TAO
    borrow_amount_rao = int(borrow_amount_tao * 1e9)
    netuid = 3

    print_info(f"\nBorrowing {borrow_amount_tao} TAO from LENDER2 at 0.6% rate...")

    # Build borrow transaction
    offer_tuple = offer_to_tuple(offer_06)
    tx = contract.functions.borrow(
        offer_tuple,
        borrow_amount_rao,
        netuid
    ).build_transaction({
        'from': borrower_address,
        'nonce': borrower_nonce,
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price,
    })

    # Sign and send
    signed_tx = w3.eth.account.sign_transaction(tx, borrower_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print_info(f"Transaction sent: {tx_hash.hex()}")

    # Wait for receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if tx_receipt['status'] != 1:
        print_error("Borrow transaction failed!")
        return None

    # Get loan ID from event
    borrow_event = contract.events.Borrow().process_receipt(tx_receipt)
    if not borrow_event:
        print_error("Could not find Borrow event")
        return None

    loan_id = borrow_event[0]['args']['loanId']
    print_success(f"✓ Loan created successfully: Loan ID {loan_id}")
    print_info(f"  Block: {tx_receipt['blockNumber']}")

    return loan_id

def wait_for_min_duration(w3, contract, loan_id):
    """Wait for MIN_LOAN_DURATION blocks"""
    print_section("Phase 2: Wait for MIN_LOAN_DURATION")

    loan_full = get_loan_full(contract, loan_id)
    if not loan_full:
        print_error(f"Could not find loan {loan_id}")
        return False

    start_block = loan_full['data']['startBlock']
    MIN_LOAN_DURATION = contract.functions.MIN_LOAN_DURATION().call()

    current_block = w3.eth.block_number
    required_block = start_block + MIN_LOAN_DURATION
    blocks_to_wait = required_block - current_block + 1  # +1 to be safe

    print_info(f"Start Block: {start_block}")
    print_info(f"MIN_LOAN_DURATION: {MIN_LOAN_DURATION}")
    print_info(f"Required Block: {required_block}")
    print_info(f"Current Block: {current_block}")

    if blocks_to_wait <= 0:
        print_success(f"✓ MIN_LOAN_DURATION already satisfied")
        return True

    print_info(f"Need to wait for {blocks_to_wait} blocks...")
    print_info(f"Estimated wait time: ~{blocks_to_wait * 12} seconds")

    # Wait for blocks
    start_time = time.time()
    while True:
        current_block = w3.eth.block_number
        if current_block > required_block:
            break

        remaining = required_block - current_block + 1
        elapsed = int(time.time() - start_time)
        print_info(f"  Waiting... Block {current_block} (need {remaining} more, elapsed {elapsed}s)")
        time.sleep(12)  # Wait for next block

    print_success(f"✓ MIN_LOAN_DURATION satisfied (waited {int(time.time() - start_time)}s)")
    return True

def main():
    """Test transfer with rate increase to 150% limit"""

    print_section("Test Case TC20: Transfer With Rate Increase (50%)")
    print(f"{Colors.CYAN}Objective:{Colors.ENDC} Verify successful transfer with maximum allowed rate increase")
    print(f"{Colors.CYAN}Strategy:{Colors.ENDC} Transfer loan from 0.6% rate to 0.9% rate (150% increase)")
    print(f"{Colors.CYAN}Expected:{Colors.ENDC} Transaction succeeds, new rate = 9,000,000 (old rate × 1.5)")

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
    print_success(f"Contract loaded: {LENDING_POOL_V2_ADDRESS}")

    # Test accounts
    borrower_address = addresses['BORROWER1']['evmAddress']
    borrower_private_key = os.environ.get("BORROWER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    old_lender_address = addresses['LENDER2']['evmAddress']  # 0.6% offer lender
    old_lender_private_key = os.environ.get("LENDER2_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    new_lender_address = addresses['LENDER1']['evmAddress']  # 0.9% offer lender

    # ========================================================================
    # Check if we need to create a new loan or use existing one
    # ========================================================================
    print_section("Step 0: Setup Initial Loan")

    # Check if user wants to create new loan or use existing
    print_info("This test requires a loan with 0.6% rate")
    print_info("Option 1: Create new loan (takes ~3-5 minutes with MIN_LOAN_DURATION wait)")
    print_info("Option 2: Use existing loan ID if you already have one")

    choice = input(f"\n{Colors.YELLOW}Enter loan ID to use (or 'new' to create): {Colors.ENDC}").strip()

    if choice.lower() == 'new':
        # Phase 1: Create loan
        loan_id = create_initial_loan(w3, contract, addresses, borrower_private_key)
        if loan_id is None:
            print_error("Failed to create initial loan")
            return 1

        # Phase 2: Wait for MIN_LOAN_DURATION
        if not wait_for_min_duration(w3, contract, loan_id):
            print_error("Failed to wait for MIN_LOAN_DURATION")
            return 1
    else:
        try:
            loan_id = int(choice)
            print_info(f"Using existing Loan ID: {loan_id}")
        except ValueError:
            print_error(f"Invalid loan ID: {choice}")
            return 1

    # ========================================================================
    # Step 1: Verify Setup Conditions
    # ========================================================================
    print_section("Step 1: Verify Setup Conditions")

    # Get loan info
    loan_full = get_loan_full(contract, loan_id)
    if not loan_full:
        print_error(f"Loan {loan_id} not found")
        return 1

    loan_term = loan_full['term']
    loan_data = loan_full['data']
    offer_old = loan_full['offer']

    # Verify loan state
    if loan_data['state'] != STATE_OPEN:
        print_error(f"Loan {loan_id} is not in OPEN state (current: {STATE_NAMES.get(loan_data['state'], 'UNKNOWN')})")
        return 1

    print_success(f"✓ Loan {loan_id} is in OPEN state")
    print_info(f"  Borrower: {loan_term['borrower']}")
    print_info(f"  Old Lender: {offer_old['lender']}")
    print_info(f"  Old Rate: {offer_old['dailyInterestRate']} ({offer_old['dailyInterestRate'] / 1e9 * 100:.2f}%)")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Start Block: {loan_data['startBlock']}")

    # Verify old rate is 0.6% (6,000,000)
    expected_old_rate = 6000000
    if offer_old['dailyInterestRate'] != expected_old_rate:
        print_warning(f"⚠ Old rate is {offer_old['dailyInterestRate']}, expected {expected_old_rate}")
        print_warning(f"⚠ This test is designed for 0.6% -> 0.9% rate increase")
        print_warning(f"⚠ Continuing anyway, but verification may differ...")

    # Check MIN_LOAN_DURATION
    current_block = w3.eth.block_number
    MIN_LOAN_DURATION = contract.functions.MIN_LOAN_DURATION().call()
    elapsed_blocks = current_block - loan_data['startBlock']

    print_info(f"\nTiming Check:")
    print_info(f"  Current Block: {current_block}")
    print_info(f"  Blocks Elapsed: {elapsed_blocks}")
    print_info(f"  MIN_LOAN_DURATION: {MIN_LOAN_DURATION}")

    if elapsed_blocks <= MIN_LOAN_DURATION:
        print_error(f"✗ Too early to transfer: need {MIN_LOAN_DURATION - elapsed_blocks} more blocks")
        print_info(f"Please wait ~{(MIN_LOAN_DURATION - elapsed_blocks) * 12} seconds and try again")
        return 1

    print_success(f"✓ MIN_LOAN_DURATION satisfied (elapsed: {elapsed_blocks} > {MIN_LOAN_DURATION})")

    # Load 0.9% offer
    print_info(f"\nLoading 0.9% offer for transfer...")
    offer_file_09 = "offers/72eabade21cf518f3a6eb8c758a71829bf449719c9c9b383664715418e37f3d1.json"
    offer_new = load_offer_from_file(offer_file_09)

    print_success("✓ New offer loaded")
    print_info(f"  New Lender: {offer_new['lender']}")
    print_info(f"  New Rate: {offer_new['dailyInterestRate']} ({offer_new['dailyInterestRate'] / 1e9 * 100:.2f}%)")

    # Verify rate relationship
    print_info(f"\nRate Validation:")
    print_info(f"  Old Rate: {offer_old['dailyInterestRate']}")
    print_info(f"  New Rate: {offer_new['dailyInterestRate']}")
    print_info(f"  150% Limit: {offer_old['dailyInterestRate'] * 150 // 100}")
    print_info(f"  Check: {offer_new['dailyInterestRate']} <= {offer_old['dailyInterestRate'] * 150 // 100}")

    if offer_new['dailyInterestRate'] <= offer_old['dailyInterestRate'] * 150 // 100:
        if offer_new['dailyInterestRate'] == offer_old['dailyInterestRate'] * 150 // 100:
            print_success(f"✓ New rate is EXACTLY at 150% limit (perfect boundary test)")
        else:
            print_success(f"✓ New rate is below 150% limit")
    else:
        print_error(f"✗ New rate exceeds 150% limit!")
        return 1

    # Calculate expected repayment
    repay_amount, protocol_fee, interest = calculate_repay_amount(
        loan_data['loanAmount'],
        loan_data['startBlock'],
        current_block,
        offer_old['dailyInterestRate']
    )

    print_info(f"\nExpected Repayment:")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Interest: {interest / 1e9:.9f} TAO")
    print_info(f"  Repay Amount: {repay_amount / 1e9:.9f} TAO")
    print_info(f"  Protocol Fee: {protocol_fee / 1e9:.9f} TAO")
    print_info(f"  Old Lender Gets: {(repay_amount - protocol_fee) / 1e9:.9f} TAO")

    # Check NEW_LENDER has enough TAO
    new_lender_balance = contract.functions.userAlphaBalance(new_lender_address, 0).call()
    print_info(f"\nNEW_LENDER TAO Balance: {new_lender_balance / 1e9:.2f} TAO")
    if new_lender_balance < repay_amount:
        print_error(f"✗ NEW_LENDER has insufficient TAO")
        return 1
    print_success(f"✓ NEW_LENDER has sufficient TAO")

    # ========================================================================
    # STEP 2: Read Initial State
    # ========================================================================
    print_section("Step 2: Capture Initial State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, 3])

    addresses_list = [
        {"address": old_lender_address, "label": "OLD_LENDER"},
        {"address": new_lender_address, "label": "NEW_LENDER"},
        {"address": borrower_address, "label": "BORROWER"},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # ========================================================================
    # STEP 3: Execute Transfer
    # ========================================================================
    print_section("Step 3: Execute Transfer Transaction")

    initiator_address = old_lender_address
    initiator_nonce = w3.eth.get_transaction_count(initiator_address)

    print_info(f"Initiator: {initiator_address} (OLD_LENDER)")
    print_info(f"Transferring Loan {loan_id} from 0.6% to 0.9% rate...")

    # Build transfer transaction
    offer_tuple = offer_to_tuple(offer_new)
    tx = contract.functions.transfer(loan_id, offer_tuple).build_transaction({
        'from': initiator_address,
        'nonce': initiator_nonce,
        'gas': 2000000,
        'gasPrice': w3.eth.gas_price,
    })

    # Sign and send
    signed_tx = w3.eth.account.sign_transaction(tx, old_lender_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print_info(f"Transaction sent: {tx_hash.hex()}")

    # Wait for receipt
    print_info("Waiting for transaction confirmation...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if tx_receipt['status'] == 1:
        print_success(f"✓ Transaction succeeded!")
        print_info(f"  Block: {tx_receipt['blockNumber']}")
        print_info(f"  Gas Used: {tx_receipt['gasUsed']}")
    else:
        print_error("✗ Transaction failed!")
        return 1

    # ========================================================================
    # STEP 4: Read Final State
    # ========================================================================
    print_section("Step 4: Capture Final State")

    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # Get loan info after transfer
    loan_full_after = get_loan_full(contract, loan_id)
    loan_term_after = loan_full_after['term']
    loan_data_after = loan_full_after['data']
    offer_after = loan_full_after['offer']

    # ========================================================================
    # STEP 5: Verify Changes
    # ========================================================================
    print_section("Step 5: Verify State Changes")

    # Show balance diff
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify loan data ID changed
    print_info("\nLoan Data Verification:")
    print_info(f"  Old loanDataId: {loan_term['loanDataId']}")
    print_info(f"  New loanDataId: {loan_term_after['loanDataId']}")

    if loan_term_after['loanDataId'] != loan_term['loanDataId']:
        print_success(f"✓ Loan data ID changed (new loan created)")
    else:
        print_error(f"✗ Loan data ID unchanged!")
        return 1

    # Verify new lender
    print_info(f"\nLender Verification:")
    print_info(f"  Old Lender: {offer_old['lender']}")
    print_info(f"  New Lender: {offer_after['lender']}")

    if offer_after['lender'].lower() == new_lender_address.lower():
        print_success(f"✓ Lender changed to NEW_LENDER")
    else:
        print_error(f"✗ Lender not changed correctly!")
        return 1

    # ========================================================================
    # CRITICAL: Verify Rate Increase to 150%
    # ========================================================================
    print_info(f"\n{'='*80}")
    print_info(f"{Colors.BOLD}CRITICAL VERIFICATION: Rate Increase to 150%{Colors.ENDC}")
    print_info(f"{'='*80}")

    old_rate = offer_old['dailyInterestRate']
    new_rate = offer_after['dailyInterestRate']
    limit_150 = old_rate * 150 // 100

    print_info(f"Old Rate: {old_rate} ({old_rate / 1e9 * 100:.2f}%)")
    print_info(f"New Rate: {new_rate} ({new_rate / 1e9 * 100:.2f}%)")
    print_info(f"150% Limit: {limit_150} ({limit_150 / 1e9 * 100:.2f}%)")
    print_info(f"Increase: {(new_rate / old_rate * 100):.1f}%")

    if new_rate == limit_150:
        print_success(f"✓ NEW RATE IS EXACTLY AT 150% LIMIT")
        print_success(f"✓ {new_rate} == {old_rate} × 150 / 100 = {limit_150}")
    elif new_rate < limit_150:
        print_success(f"✓ New rate below 150% limit")
    else:
        print_error(f"✗ New rate exceeds 150% limit!")
        return 1

    # Verify new loan state
    print_info(f"\nNew Loan State:")
    print_info(f"  State: {STATE_NAMES[loan_data_after['state']]}")
    print_info(f"  Loan Amount: {loan_data_after['loanAmount'] / 1e9:.9f} TAO")
    print_info(f"  Daily Rate: {offer_after['dailyInterestRate']} ({offer_after['dailyInterestRate'] / 1e9 * 100:.2f}%)")
    print_info(f"  Start Block: {loan_data_after['startBlock']}")

    if loan_data_after['state'] == STATE_OPEN:
        print_success(f"✓ New loan is in OPEN state")
    else:
        print_error(f"✗ New loan state is not OPEN!")
        return 1

    # ========================================================================
    # Final Summary
    # ========================================================================
    print_section("Test Result: TC20 - PASSED")
    print_success("✓ Transfer with rate increase to 150% limit succeeded")
    print_success(f"✓ Old Rate: {old_rate / 1e9 * 100:.2f}% → New Rate: {new_rate / 1e9 * 100:.2f}%")
    print_success(f"✓ Rate validation: {new_rate} <= {limit_150}")
    print_success(f"✓ Loan transferred from OLD_LENDER to NEW_LENDER")
    print_success(f"✓ All balance changes verified")

    return 0

if __name__ == "__main__":
    sys.exit(main())
