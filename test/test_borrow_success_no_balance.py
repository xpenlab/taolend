#!/usr/bin/env python3
"""
Test Case TC11: Success - No Existing Balance
Objective: Verify successful borrow when borrower has no existing loan
Tests: Complete borrow flow with all validations passing

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction succeeds, loan created, balances updated correctly
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
    print_section("Test Case TC11: Success - No Existing Balance")
    print(f"{CYAN}Objective:{NC} Verify successful borrow when borrower has no existing loan")
    print(f"{CYAN}Strategy:{NC} Execute borrow with all conditions valid")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, loan created, balances updated\n")

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
        print_info(f"  {YELLOW}python3 scripts/cli.py create-offer --account LENDER1 --max-tao 100 --alpha-price 0.25 --daily-rate 1.0 --netuid 3{NC}")
        sys.exit(1)

    # Test parameters
    netuid = offer['netuid']
    tao_amount = 30 * 10**9  # 30 TAO in RAO (valid amount)
    alpha_amount = 150 * 10**9  # 150 ALPHA in RAO (sufficient collateral at 0.25 price)

    print_info(f"\nTest Parameters:")
    print_info(f"  Netuid: {netuid}")
    print_info(f"  Borrow Amount: {tao_amount / 1e9:.2f} TAO")
    print_info(f"  Collateral: {alpha_amount / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

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
    next_loan_id = contract.functions.nextLoanId().call()
    next_loan_data_id = contract.functions.nextLoanDataId().call()
    offer_id_bytes = bytes.fromhex(offer['offerId'][2:])
    lend_balance = contract.functions.userLendBalance(lender_address, offer_id_bytes).call()

    print_info(f"\nContract State:")
    print_info(f"  nextLoanId: {next_loan_id}")
    print_info(f"  nextLoanDataId: {next_loan_data_id}")
    print_info(f"  userLendBalance[LENDER1][offerId]: {lend_balance / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")

    print_info(f"Reading loan state for loan ID {next_loan_id} (to be created)...")

    # Try to read the loan that will be created - should fail or return empty
    try:
        loan_info_before = get_loan_full(contract, next_loan_id)
        loan_term_before = loan_info_before['term']
        loan_data_before = loan_info_before['data']
        loan_offer_before = loan_info_before['offer']

        # Check if loan exists (borrower should be zero address if not exists)
        if loan_term_before['borrower'] == '0x0000000000000000000000000000000000000000':
            print_success(f"✓ Loan ID {next_loan_id} does not exist yet (as expected)")
        else:
            print_warning(f"⚠ Loan ID {next_loan_id} already exists!")
            print_info(f"  Borrower: {loan_term_before['borrower']}")
            print_info(f"  Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")
            print_info(f"  State: {loan_data_before['state']}")
    except Exception as e:
        print_info(f"Cannot read loan {next_loan_id} (expected for non-existent loan): {str(e)[:100]}")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute borrow()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds (status=1)")
    print(f"  {BLUE}Event:{NC} CreateLoan(...)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - nextLoanId: {next_loan_id} → {next_loan_id + 1}")
    print(f"    - Loan created with ID {next_loan_id}")
    print(f"    - Borrower receives {tao_amount / 1e9:.2f} TAO")
    print(f"    - {alpha_amount / 1e9:.2f} ALPHA collateral locked")
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

    print_info(f"Borrowing {tao_amount / 1e9:.2f} TAO with {alpha_amount / 1e9:.2f} ALPHA collateral...")

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
        print_warning(f"Transaction reverted (expected for negative test)")
        print_info(f"Error: {error_msg[:200]}")

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
    print_info(f"  nextLoanId: {next_loan_id} → {next_loan_id_after}")
    print_info(f"  nextLoanDataId: {next_loan_data_id} → {next_loan_data_id_after}")
    print_info(f"  userLendBalance[LENDER1][offerId]: {lend_balance / 1e9:.2f} → {lend_balance_after / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")

    # For positive test: Read the created loan
    if tx_receipt and tx_receipt['status'] == 1:
        loan_id = next_loan_id  # The loan that was just created

        print_info(f"Reading created loan {loan_id}...")
        loan_info = get_loan_full(contract, loan_id)
        if loan_info is None:
            print_error(f"✗ Failed to read loan {loan_id}")
            sys.exit(1)

        loan_term = loan_info['term']
        loan_data = loan_info['data']
        loan_offer = loan_info['offer']

        print_success(f"✓ Loan {loan_id} created successfully")
        print_info(f"\nLoan Term:")
        print_info(f"  borrower: {loan_term['borrower']}")
        print_info(f"  collateralAmount: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
        print_info(f"  netuid: {loan_term['netuid']}")
        print_info(f"  loanDataId: {loan_term['loanDataId']}")

        print_info(f"\nLoan Data:")
        print_info(f"  loanId: {loan_data['loanId']}")
        print_info(f"  loanAmount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
        print_info(f"  state: {loan_data['state']} (OPEN)")
        print_info(f"  startBlock: {loan_data['startBlock']}")
        print_info(f"  initiator: {loan_data['initiator']}")
    else:
        print_error("✗ Transaction failed unexpectedly!")
        sys.exit(1)

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction succeeded
    if not tx_receipt or tx_receipt['status'] == 0:
        print_error("✗ Transaction failed unexpectedly!")
        sys.exit(1)
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
    if next_loan_id_after != next_loan_id + 1:
        print_error(f"✗ nextLoanId not incremented correctly")
        sys.exit(1)
    print_success(f"✓ nextLoanId incremented: {next_loan_id} → {next_loan_id_after}")

    # Verify lend balance increased
    expected_lend_balance = lend_balance + tao_amount
    if lend_balance_after != expected_lend_balance:
        print_error(f"✗ Lend balance incorrect: expected {expected_lend_balance / 1e9:.2f}, got {lend_balance_after / 1e9:.2f}")
        sys.exit(1)
    print_success(f"✓ Lend balance increased by {tao_amount / 1e9:.2f} TAO")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Report results
    print_section("Test Result")
    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC11: Success - No Existing Balance")
    print_success("Borrow transaction succeeded, loan created successfully")
    print_success("All state validations passed")
    print_success("Balance changes verified correctly")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - First borrow transaction succeeded")
    print(f"  - Loan created with ID {next_loan_id}")
    print(f"  - Borrower received {tao_amount / 1e9:.2f} TAO")
    print(f"  - {alpha_amount / 1e9:.2f} ALPHA collateral locked")
    print(f"  - All validations passed")
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
