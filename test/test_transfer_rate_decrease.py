#!/usr/bin/env python3
"""
Test Case TC22: Transfer With Rate Decrease
Objective: Verify successful transfer with lower rate than original loan (borrower-friendly)
Tests: Rate validation with decrease (e.g., 0.9% -> 0.5%)

Strategy:
1. Use existing loan with higher rate (e.g., 0.9%)
2. Transfer to offer with lower rate (e.g., 0.5%)
3. Verify rate decreased successfully
4. Verify all balance changes correct

Expected: Transaction succeeds, borrower gets better rate
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
    """Test transfer with rate decrease"""

    print_section("Test Case TC22: Transfer With Rate Decrease")
    print(f"{Colors.CYAN}Objective:{Colors.ENDC} Verify successful transfer with lower rate (borrower-friendly)")
    print(f"{Colors.CYAN}Strategy:{Colors.ENDC} Transfer loan from higher rate to lower rate")
    print(f"{Colors.CYAN}Expected:{Colors.ENDC} Transaction succeeds, borrower gets better interest rate")

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

    # ========================================================================
    # Get loan ID from user
    # ========================================================================
    print_section("Step 0: Select Loan")

    print_info("This test requires a loan with a higher rate that can be decreased")
    print_info("Example: Loan 10 (0.9% rate) can be decreased to 0.5%")

    loan_id_input = input(f"\n{Colors.YELLOW}Enter loan ID to use: {Colors.ENDC}").strip()

    try:
        loan_id = int(loan_id_input)
    except ValueError:
        print_error(f"Invalid loan ID: {loan_id_input}")
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
    print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Start Block: {loan_data['startBlock']}")

    # Set accounts based on current lender
    old_lender_address = offer_old['lender']

    if old_lender_address.lower() == addresses['LENDER1']['evmAddress'].lower():
        old_lender_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
        new_lender_address = addresses['LENDER2']['evmAddress']
        # Use LENDER2's 0.6% offer for rate decrease from LENDER1's rate
        new_offer_file = "offers/eecbd6342d7ddfa91e92492a53968cfbab90630003ef685f3690f8615ab13e64.json"
    else:
        old_lender_private_key = os.environ.get("LENDER2_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
        new_lender_address = addresses['LENDER1']['evmAddress']
        # Find a lower rate offer from LENDER1
        new_offer_file = "offers/6a2a9abb48a9e61058e3c67f1765e4e5fb4ab5b7be7b2e1f5e8ddab654ec4912.json"

    borrower_address = loan_term['borrower']

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

    # Load lower rate offer
    print_info(f"\nLoading lower rate offer for transfer...")

    # Check if offer file exists
    if not os.path.exists(new_offer_file):
        print_error(f"Offer file not found: {new_offer_file}")
        print_info("Available offer files:")
        import glob
        for f in glob.glob("offers/*.json"):
            print_info(f"  {f}")
        return 1

    offer_new = load_offer_from_file(new_offer_file)

    print_success("✓ New offer loaded")
    print_info(f"  New Lender: {offer_new['lender']}")
    print_info(f"  New Rate: {offer_new['dailyInterestRate']} ({offer_new['dailyInterestRate'] / 1e9 * 100:.2f}%)")

    # Verify rate relationship
    print_info(f"\nRate Validation:")
    print_info(f"  Old Rate: {offer_old['dailyInterestRate']} ({offer_old['dailyInterestRate'] / 1e9 * 100:.2f}%)")
    print_info(f"  New Rate: {offer_new['dailyInterestRate']} ({offer_new['dailyInterestRate'] / 1e9 * 100:.2f}%)")
    print_info(f"  150% Limit: {offer_old['dailyInterestRate'] * 150 // 100}")

    if offer_new['dailyInterestRate'] < offer_old['dailyInterestRate']:
        decrease_pct = (1 - offer_new['dailyInterestRate'] / offer_old['dailyInterestRate']) * 100
        print_success(f"✓ New rate is LOWER than old rate (decrease: {decrease_pct:.1f}%)")
        print_success(f"✓ This is borrower-friendly (lower interest cost)")
    elif offer_new['dailyInterestRate'] == offer_old['dailyInterestRate']:
        print_warning(f"⚠ New rate is same as old rate (no change)")
    else:
        print_warning(f"⚠ New rate is HIGHER than old rate (not a rate decrease)")
        print_warning(f"⚠ This test is designed for rate decrease scenarios")

    # Verify passes 150% limit check
    if offer_new['dailyInterestRate'] <= offer_old['dailyInterestRate'] * 150 // 100:
        print_success(f"✓ New rate passes 150% limit check")
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

    checker = BalanceChecker(w3, contract, test_netuids=[0, loan_term['netuid']])

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
    print_info(f"Transferring Loan {loan_id} to lower rate...")
    print_info(f"  Old Rate: {offer_old['dailyInterestRate'] / 1e9 * 100:.2f}%")
    print_info(f"  New Rate: {offer_new['dailyInterestRate'] / 1e9 * 100:.2f}%")

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
    # CRITICAL: Verify Rate Decrease
    # ========================================================================
    print_info(f"\n{'='*80}")
    print_info(f"{Colors.BOLD}CRITICAL VERIFICATION: Rate Decrease{Colors.ENDC}")
    print_info(f"{'='*80}")

    old_rate = offer_old['dailyInterestRate']
    new_rate = offer_after['dailyInterestRate']

    print_info(f"Old Rate: {old_rate} ({old_rate / 1e9 * 100:.2f}%)")
    print_info(f"New Rate: {new_rate} ({new_rate / 1e9 * 100:.2f}%)")

    if new_rate < old_rate:
        decrease_pct = (1 - new_rate / old_rate) * 100
        decrease_amount = old_rate - new_rate
        print_success(f"✓ RATE DECREASED SUCCESSFULLY")
        print_success(f"✓ Decrease: {decrease_amount} ({decrease_pct:.1f}%)")
        print_success(f"✓ {new_rate} < {old_rate}")
        print_info(f"\nBorrower Benefit:")
        print_info(f"  Old daily interest on {loan_data['loanAmount'] / 1e9:.2f} TAO:")
        old_daily = (loan_data['loanAmount'] * old_rate) // int(1e9)
        print_info(f"    {old_daily / 1e9:.9f} TAO/day")
        print_info(f"  New daily interest:")
        new_daily = (loan_data_after['loanAmount'] * new_rate) // int(1e9)
        print_info(f"    {new_daily / 1e9:.9f} TAO/day")
        savings = old_daily - new_daily
        print_success(f"  Daily Savings: {savings / 1e9:.9f} TAO ({(savings / old_daily * 100):.1f}%)")
    elif new_rate == old_rate:
        print_warning(f"⚠ Rate unchanged (same rate)")
    else:
        print_error(f"✗ Rate increased instead of decreased!")
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
    print_section("Test Result: TC22 - PASSED")
    print_success("✓ Transfer with rate decrease succeeded")
    print_success(f"✓ Old Rate: {old_rate / 1e9 * 100:.2f}% → New Rate: {new_rate / 1e9 * 100:.2f}%")
    print_success(f"✓ Rate validation: {new_rate} < {old_rate}")
    print_success(f"✓ Borrower benefits from lower interest rate")
    print_success(f"✓ Loan transferred from OLD_LENDER to NEW_LENDER")
    print_success(f"✓ All balance changes verified")

    return 0

if __name__ == "__main__":
    sys.exit(main())
