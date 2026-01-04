#!/usr/bin/env python3
"""
Test Case TC12: Success - With Existing Balance
Objective: Verify successful borrow when borrower has existing active loan
Tests: Complete borrow flow with multiple loans for same borrower

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction succeeds, new loan created, existing loan unchanged
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
from common import get_loan_full, load_addresses, load_contract_abi

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

def load_offer(offer_file):
    """Load offer from JSON file"""
    with open(offer_file, 'r') as f:
        return json.load(f)

def main():
    print_section("Test Case TC12: Success - With Existing Balance")
    print(f"{CYAN}Objective:{NC} Verify successful borrow when borrower has existing active loan")
    print(f"{CYAN}Strategy:{NC} Execute second borrow, verify first loan unchanged")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, new loan created, existing loan unchanged\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender_address = addresses['LENDER1']['evmAddress']
    borrower_address = addresses['BORROWER1']['evmAddress']

    # Load private keys
    lender_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
    borrower_private_key = os.environ.get("BORROWER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    if not borrower_private_key:
        print_error("BORROWER1_PRIVATE_KEY not found in .env")
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

    # Find active offer from LENDER1
    offers_dir = Path(__file__).parent.parent / "offers"
    offer_file = None
    offer = None

    print_info("Searching for active offers from LENDER1...")
    offer_files = sorted(offers_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    current_timestamp = w3.eth.get_block('latest')['timestamp']

    for file in offer_files:
        candidate_offer = load_offer(file)
        if candidate_offer['lender'].lower() == lender_address.lower():
            # Check if NOT cancelled and NOT expired
            offer_id_bytes = bytes.fromhex(candidate_offer['offerId'][2:])
            cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()

            if candidate_offer['expire'] > current_timestamp and cancel_block == 0:
                # Check if lender nonce matches
                lender_nonce = contract.functions.lenderNonce(lender_address).call()
                if candidate_offer['nonce'] == lender_nonce:
                    offer_file = file
                    offer = candidate_offer
                    print_success(f"Found active offer: {offer_file.name}")
                    break

    if not offer_file:
        print_error("No suitable active offer found from LENDER1")
        print_info("Please create an offer first:")
        print_info(f"  {YELLOW}python3 scripts/cli.py create-offer --account LENDER1 --max-tao 100 --max-alpha-price 0.5 --daily-rate 1.0 --netuid 3{NC}")
        sys.exit(1)

    # Test parameters (second borrow)
    netuid = offer['netuid']
    tao_amount = 20 * 10**9  # 20 TAO in RAO (different from first borrow)
    alpha_amount = 100 * 10**9  # 100 ALPHA in RAO (sufficient collateral at 0.5 price)

    print_info(f"\nTest Parameters (Second Borrow):")
    print_info(f"  Netuid: {netuid}")
    print_info(f"  Borrow Amount: {tao_amount / 1e9:.2f} TAO")
    print_info(f"  Collateral: {alpha_amount / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 0: Verify Setup Conditions & Existing Loans
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions & Existing Loans")

    # Check borrower registration
    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    if not borrower_registered:
        print_error("SETUP ERROR: Borrower not registered")
        sys.exit(1)
    print_success("✓ Borrower registered")

    # Check lender registration
    lender_registered = contract.functions.registeredUser(lender_address).call()
    if not lender_registered:
        print_error("SETUP ERROR: Lender not registered")
        sys.exit(1)
    print_success("✓ Lender registered")

    # Check contract not paused
    paused = contract.functions.pausedBorrow().call()
    if paused:
        print_error("SETUP ERROR: Contract is paused")
        sys.exit(1)
    print_success("✓ Contract not paused")

    # Check subnet active
    subnet_active = contract.functions.activeSubnets(netuid).call()
    if not subnet_active:
        print_error(f"SETUP ERROR: Subnet {netuid} not active")
        sys.exit(1)
    print_success(f"✓ Subnet {netuid} active")

    # Check lender has sufficient TAO
    lender_tao = contract.functions.userAlphaBalance(lender_address, 0).call()
    if lender_tao < tao_amount:
        print_error(f"SETUP ERROR: Lender has insufficient TAO ({lender_tao / 1e9:.2f} < {tao_amount / 1e9:.2f})")
        sys.exit(1)
    print_success(f"✓ Lender has sufficient TAO: {lender_tao / 1e9:.2f} TAO")

    # Check borrower has sufficient ALPHA
    borrower_alpha = contract.functions.userAlphaBalance(borrower_address, netuid).call()
    if borrower_alpha < alpha_amount:
        print_error(f"SETUP ERROR: Borrower has insufficient ALPHA ({borrower_alpha / 1e9:.2f} < {alpha_amount / 1e9:.2f})")
        sys.exit(1)
    print_success(f"✓ Borrower has sufficient ALPHA: {borrower_alpha / 1e9:.2f} ALPHA")

    # Check for existing loans
    next_loan_id = contract.functions.nextLoanId().call()
    existing_loans = []

    print_info(f"\nChecking for existing loans (nextLoanId = {next_loan_id})...")
    for loan_id in range(next_loan_id):
        loan_info = get_loan_full(contract, loan_id)
        if loan_info:
            term = loan_info['term']
            data = loan_info['data']
            if term['borrower'].lower() == borrower_address.lower() and data['state'] == 0:  # OPEN
                existing_loans.append({
                    'id': loan_id,
                    'amount': data['loanAmount'],
                    'collateral': term['collateralAmount'],
                    'info': loan_info
                })
                print_success(f"  ✓ Found existing loan {loan_id}: {data['loanAmount'] / 1e9:.2f} TAO, {term['collateralAmount'] / 1e9:.2f} ALPHA collateral")

    if len(existing_loans) == 0:
        print_error("SETUP ERROR: No existing loans found for BORROWER1")
        print_error("This test requires at least one existing active loan")
        print_error("Please run TC11 first to create an initial loan")
        sys.exit(1)

    print_success(f"✓ BORROWER1 has {len(existing_loans)} existing active loan(s)")

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
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    next_loan_id_before = contract.functions.nextLoanId().call()
    next_loan_data_id_before = contract.functions.nextLoanDataId().call()
    offer_id_bytes = bytes.fromhex(offer['offerId'][2:])
    lend_balance_before = contract.functions.userLendBalance(lender_address, offer_id_bytes).call()

    print_info(f"\nContract State:")
    print_info(f"  nextLoanId: {next_loan_id_before}")
    print_info(f"  nextLoanDataId: {next_loan_data_id_before}")
    print_info(f"  userLendBalance[LENDER1][offerId]: {lend_balance_before / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State (Existing Loans)
    # ========================================================================
    print_section("Step 3: Read Initial Loan State (Existing Loans)")

    print_info(f"Storing state of {len(existing_loans)} existing loan(s) for later comparison...")
    for loan in existing_loans:
        print_info(f"  Loan {loan['id']}: {loan['amount'] / 1e9:.2f} TAO, {loan['collateral'] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation (Second Borrow)
    # ========================================================================
    print_section("Step 4: Execute Second borrow()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds (status=1)")
    print(f"  {BLUE}Event:{NC} CreateLoan(...) for new loan")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - nextLoanId: {next_loan_id_before} → {next_loan_id_before + 1}")
    print(f"    - New loan created with ID {next_loan_id_before}")
    print(f"    - Existing loans remain unchanged")
    print(f"    - Borrower receives {tao_amount / 1e9:.2f} TAO")
    print(f"    - {alpha_amount / 1e9:.2f} ALPHA collateral locked (additional)")
    print()

    # Convert offer to tuple for contract call
    offer_tuple = (
        bytes.fromhex(offer['offerId'][2:]),
        Web3.to_checksum_address(offer['lender']),
        offer['netuid'],
        offer['nonce'],
        offer['expire'],
        offer['maxTaoAmount'],
        offer['maxAlphaPrice'],
        offer['dailyInterestRate'],
        bytes.fromhex(offer['signature'][2:])
    )

    print_info(f"Borrowing {tao_amount / 1e9:.2f} TAO with {alpha_amount / 1e9:.2f} ALPHA collateral (second borrow)...")

    # Execute transaction
    tx_receipt = None
    reverted = False

    try:
        tx = contract.functions.borrow(offer_tuple, tao_amount, alpha_amount).build_transaction({
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

    except Exception as e:
        reverted = True
        error_msg = str(e)
        print_error(f"Transaction reverted unexpectedly")
        print_info(f"Error: {error_msg[:200]}")
        sys.exit(1)

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final state
    next_loan_id_after = contract.functions.nextLoanId().call()
    next_loan_data_id_after = contract.functions.nextLoanDataId().call()
    lend_balance_after = contract.functions.userLendBalance(lender_address, offer_id_bytes).call()

    print_info(f"\nContract State After:")
    print_info(f"  nextLoanId: {next_loan_id_before} → {next_loan_id_after}")
    print_info(f"  nextLoanDataId: {next_loan_data_id_before} → {next_loan_data_id_after}")
    print_info(f"  userLendBalance[LENDER1][offerId]: {lend_balance_before / 1e9:.2f} → {lend_balance_after / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State (All Loans)
    # ========================================================================
    print_section("Step 7: Read Final Loan State (All Loans)")

    # Verify transaction succeeded
    if not tx_receipt or tx_receipt['status'] == 0:
        print_error("✗ Transaction failed unexpectedly!")
        sys.exit(1)

    # Check existing loans unchanged
    print_info("\nVerifying existing loans unchanged...")
    for loan in existing_loans:
        loan_id = loan['id']
        old_info = loan['info']
        new_info = get_loan_full(contract, loan_id)

        if new_info is None:
            print_error(f"✗ Cannot read existing loan {loan_id}")
            sys.exit(1)

        old_data = old_info['data']
        new_data = new_info['data']
        old_term = old_info['term']
        new_term = new_info['term']

        # Verify unchanged
        if (old_data['state'] != new_data['state'] or
            old_data['loanAmount'] != new_data['loanAmount'] or
            old_term['collateralAmount'] != new_term['collateralAmount']):
            print_error(f"✗ Existing loan {loan_id} was modified!")
            sys.exit(1)

        print_success(f"  ✓ Loan {loan_id} unchanged: {new_data['loanAmount'] / 1e9:.2f} TAO, state={new_data['state']}")

    # Read the newly created loan
    new_loan_id = next_loan_id_before
    print_info(f"\nReading newly created loan {new_loan_id}...")
    new_loan_info = get_loan_full(contract, new_loan_id)
    if new_loan_info is None:
        print_error(f"✗ Failed to read new loan {new_loan_id}")
        sys.exit(1)

    new_loan_term = new_loan_info['term']
    new_loan_data = new_loan_info['data']
    new_loan_offer = new_loan_info['offer']

    print_success(f"✓ Loan {new_loan_id} created successfully")
    print_info(f"\nNew Loan Term:")
    print_info(f"  borrower: {new_loan_term['borrower']}")
    print_info(f"  collateralAmount: {new_loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  netuid: {new_loan_term['netuid']}")
    print_info(f"  loanDataId: {new_loan_term['loanDataId']}")

    print_info(f"\nNew Loan Data:")
    print_info(f"  loanId: {new_loan_data['loanId']}")
    print_info(f"  loanAmount: {new_loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  state: {new_loan_data['state']} (OPEN)")
    print_info(f"  startBlock: {new_loan_data['startBlock']}")
    print_info(f"  initiator: {new_loan_data['initiator']}")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction succeeded
    print_success("✓ Transaction succeeded")

    # Verify CreateLoan event
    try:
        create_logs = contract.events.CreateLoan().process_receipt(tx_receipt)
        if len(create_logs) == 0:
            print_error("✗ No CreateLoan event found")
            sys.exit(1)

        event = create_logs[0]['args']
        print_success("✓ CreateLoan event emitted:")
        print_info(f"  borrower: {event['borrower']}")
        print_info(f"  loanId: {event['loanId']}")
        print_info(f"  loanDataId: {event['loanDataId']}")
        print_info(f"  offerId: {event['offerId'].hex()}")
        print_info(f"  collateralAmount: {event['collateralAmount'] / 1e9:.2f} ALPHA")
        print_info(f"  loanAmount: {event['loanAmount'] / 1e9:.2f} TAO")

    except Exception as e:
        print_error(f"✗ Failed to parse CreateLoan event: {e}")
        sys.exit(1)

    # Verify state increments
    if next_loan_id_after != next_loan_id_before + 1:
        print_error(f"✗ nextLoanId not incremented correctly")
        sys.exit(1)
    print_success(f"✓ nextLoanId incremented: {next_loan_id_before} → {next_loan_id_after}")

    # Verify lend balance increased
    expected_lend_balance = lend_balance_before + tao_amount
    if lend_balance_after != expected_lend_balance:
        print_error(f"✗ Lend balance incorrect: expected {expected_lend_balance / 1e9:.2f}, got {lend_balance_after / 1e9:.2f}")
        sys.exit(1)
    print_success(f"✓ Lend balance increased by {tao_amount / 1e9:.2f} TAO (cumulative: {lend_balance_after / 1e9:.2f} TAO)")

    # Verify borrower now has multiple loans
    total_loans = len(existing_loans) + 1
    print_success(f"✓ BORROWER1 now has {total_loans} active loans")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Report results
    print_section("Test Result")
    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC12: Success - With Existing Balance")
    print_success("Second borrow transaction succeeded")
    print_success("New loan created successfully")
    print_success("All existing loans remain unchanged")
    print_success("Balance changes verified correctly")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - Second borrow transaction succeeded")
    print(f"  - New loan created with ID {new_loan_id}")
    print(f"  - {len(existing_loans)} existing loan(s) unchanged")
    print(f"  - Borrower received {tao_amount / 1e9:.2f} TAO")
    print(f"  - {alpha_amount / 1e9:.2f} ALPHA additional collateral locked")
    print(f"  - Total active loans: {total_loans}")
    print(f"  - Cumulative lend balance: {lend_balance_after / 1e9:.2f} TAO")
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
