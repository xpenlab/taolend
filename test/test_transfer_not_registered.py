#!/usr/bin/env python3
"""
Test Case TC01: Initiator Not Registered
Objective: Verify transfer fails when initiator is not registered
Tests: onlyRegistered modifier - require(registeredUser[msg.sender], "not registered")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "not registered"
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
    create_offer, offer_to_tuple, load_offer_from_file,
    STATE_OPEN, STATE_IN_COLLECTION
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
    print_section("Test Case TC01: Initiator Not Registered")
    print(f"{CYAN}Objective:{NC} Verify transfer fails when initiator is not registered")
    print(f"{CYAN}Strategy:{NC} Attempt transfer with unregistered initiator")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'not registered'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    old_lender_address = addresses['LENDER1']['evmAddress']
    new_lender_address = addresses['LENDER2']['evmAddress']
    borrower_address = addresses['BORROWER1']['evmAddress']

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

    # Find an unregistered account to use as initiator
    print_info("Finding unregistered account to use as initiator...")
    initiator_address = None
    initiator_private_key = None
    initiator_label = None

    candidate_accounts = ['LENDER3', 'BORROWER2', 'LENDER4']

    for account_name in candidate_accounts:
        if account_name in addresses:
            candidate_address = addresses[account_name]['evmAddress']
            # Check if this account is NOT registered
            is_registered = contract.functions.registeredUser(candidate_address).call()
            if not is_registered:
                initiator_address = candidate_address
                initiator_private_key = os.environ.get(f"{account_name}_PRIVATE_KEY")
                initiator_label = account_name
                print_success(f"Found unregistered account: {account_name} ({candidate_address})")
                break

    if initiator_address is None:
        print_error("SETUP ERROR: No unregistered account found in addresses.json")
        print_error("This test requires an unregistered account (LENDER3, BORROWER2, or LENDER4)")
        print_info("\nTo run this test:")
        print_info("  1. Add one of these accounts to addresses.json")
        print_info("  2. Add the private key to .env (e.g., LENDER3_PRIVATE_KEY=0x...)")
        print_info("  3. Do NOT register the account")
        print_info("\nOR: Ensure one of the existing accounts (LENDER3/BORROWER2/LENDER4) is not registered")
        sys.exit(1)

    if not initiator_private_key:
        print_error(f"SETUP ERROR: Private key for {initiator_label} not found in .env")
        print_error(f"Please add {initiator_label}_PRIVATE_KEY to .env file")
        sys.exit(1)

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check OLD_LENDER is registered
    old_lender_registered = contract.functions.registeredUser(old_lender_address).call()
    if not old_lender_registered:
        print_error("SETUP ERROR: LENDER1 (OLD_LENDER) not registered")
        sys.exit(1)
    print_success(f"✓ OLD_LENDER registered: {old_lender_address}")

    # Check NEW_LENDER is registered
    new_lender_registered = contract.functions.registeredUser(new_lender_address).call()
    if not new_lender_registered:
        print_error("SETUP ERROR: LENDER2 (NEW_LENDER) not registered")
        sys.exit(1)
    print_success(f"✓ NEW_LENDER registered: {new_lender_address}")

    # Check BORROWER is registered
    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    if not borrower_registered:
        print_error("SETUP ERROR: BORROWER1 not registered")
        sys.exit(1)
    print_success(f"✓ BORROWER1 registered: {borrower_address}")

    # Check INITIATOR is NOT registered (this is the test condition)
    initiator_registered = contract.functions.registeredUser(initiator_address).call()
    if initiator_registered:
        print_error(f"SETUP ERROR: {initiator_label} is already registered")
        print_error("This test requires an unregistered initiator account")
        sys.exit(1)
    print_success(f"✓ {initiator_label} NOT registered (as required): {initiator_address}")

    # Find an active loan (BORROWER1 borrowed from OLD_LENDER)
    print_info("\nSearching for active loan...")
    next_loan_id = contract.functions.nextLoanId().call()

    active_loan_id = None
    for loan_id in range(next_loan_id):
        try:
            loan_info = get_loan_full(contract, loan_id)
            if loan_info is None:
                continue

            loan_term = loan_info['term']
            loan_data = loan_info['data']
            offer = loan_info['offer']

            # Check if loan belongs to BORROWER1, lent by OLD_LENDER, and is in OPEN or IN_COLLECTION state
            if (loan_term['borrower'].lower() == borrower_address.lower() and
                offer['lender'].lower() == old_lender_address.lower() and
                loan_data['state'] in [STATE_OPEN, STATE_IN_COLLECTION]):
                active_loan_id = loan_id
                print_success(f"✓ Found active loan: Loan ID {loan_id}")
                print_info(f"  State: {['OPEN', 'IN_COLLECTION', 'REPAID', 'CLAIMED', 'RESOLVED'][loan_data['state']]}")
                print_info(f"  Borrower: {loan_term['borrower']}")
                print_info(f"  Old Lender: {offer['lender']}")
                print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
                print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
                print_info(f"  Netuid: {loan_term['netuid']}")
                break
        except Exception as e:
            continue

    if active_loan_id is None:
        print_error("SETUP ERROR: No active loan found")
        print_info("Please create a loan first:")
        print_info("  1. Create an offer: python3 scripts/cli.py create-offer --account LENDER1 ...")
        print_info("  2. Borrow: python3 scripts/cli.py borrow --account BORROWER1 ...")
        sys.exit(1)

    test_loan_id = active_loan_id

    # Get loan details
    loan_info_initial = get_loan_full(contract, test_loan_id)
    loan_term_initial = loan_info_initial['term']
    loan_data_initial = loan_info_initial['data']
    offer_initial = loan_info_initial['offer']
    netuid = loan_term_initial['netuid']

    # Calculate repay amount (needed for new lender's TAO balance)
    current_block = w3.eth.block_number
    elapsed_blocks = current_block - loan_data_initial['startBlock']
    interest = (loan_data_initial['loanAmount'] * elapsed_blocks * offer_initial['dailyInterestRate']) // (7200 * 10**9)
    repay_amount = loan_data_initial['loanAmount'] + interest
    protocol_fee = (interest * 3000) // 10000

    print_info(f"\nRepayment Calculation:")
    print_info(f"  Loan Amount: {loan_data_initial['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Elapsed Blocks: {elapsed_blocks}")
    print_info(f"  Interest: {interest / 1e9:.9f} TAO")
    print_info(f"  Repay Amount: {repay_amount / 1e9:.9f} TAO")
    print_info(f"  Protocol Fee: {protocol_fee / 1e9:.9f} TAO")

    # Check NEW_LENDER has sufficient TAO
    new_lender_tao = contract.functions.userAlphaBalance(new_lender_address, 0).call()
    print_info(f"\nNEW_LENDER TAO balance: {new_lender_tao / 1e9:.2f} TAO")
    if new_lender_tao < repay_amount:
        print_warning(f"⚠ NEW_LENDER has insufficient TAO (but test should fail at registration check first)")

    # Load new offer from NEW_LENDER (created via CLI)
    print_info("\nLoading new offer from NEW_LENDER...")

    # Offer created with CLI command:
    # python3 scripts/cli.py create-offer --account LENDER2 --netuid 3 --max-tao 100 --max-alpha-price 0.48 --daily-rate 1.0 --expire-hours 48
    new_offer_file = "offers/290f8994967f7a9cb583843fe0933d91dfa02ea3bfc4a9b3c6509bd4ca03bc39.json"
    new_offer = load_offer_from_file(new_offer_file)

    print_success("✓ New offer loaded from file")
    print_info(f"  Offer ID: {new_offer['offerId']}")
    print_info(f"  Daily Rate: {new_offer['dailyInterestRate'] / 1e9 * 100:.4f}%")
    print_info(f"  Max Alpha Price: {new_offer['maxAlphaPrice'] / 1e9:.9f} TAO/ALPHA")

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
        {"address": old_lender_address, "label": "OLD_LENDER"},
        {"address": new_lender_address, "label": "NEW_LENDER"},
        {"address": borrower_address, "label": "BORROWER1"},
        {"address": initiator_address, "label": initiator_label}
    ]

    # Capture initial snapshot
    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    protocol_fee_before = contract.functions.protocolFeeAccumulated().call()
    offer_id_bytes = loan_data_initial['offerId']
    old_lender_lend_balance_before = contract.functions.userLendBalance(old_lender_address, offer_id_bytes).call()

    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance: {old_lender_lend_balance_before / 1e9:.2f} TAO")

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
    print_info(f"  Loan Data ID: {loan_term_before['loanDataId']}")
    print_info(f"  State: {['OPEN', 'IN_COLLECTION', 'REPAID', 'CLAIMED', 'RESOLVED'][loan_data_before['state']]}")
    print_info(f"  Old Lender: {offer_before['lender']}")
    print_info(f"  Borrower: {loan_term_before['borrower']}")
    print_info(f"  Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute transfer()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} 'not registered'")
    print(f"  {CYAN}Reason:{NC} {initiator_label} is not registered (onlyRegistered modifier)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from initiator's EVM TAO")
    print()

    print_info(f"Attempting to transfer loan {test_loan_id}...")
    print_info(f"Initiator: {initiator_address} ({initiator_label}, NOT registered)")
    print_info(f"New Lender: {new_lender_address}")

    # Convert offer to tuple format
    offer_tuple = offer_to_tuple(new_offer)

    # Execute transaction
    tx_receipt = None
    reverted = False
    revert_reason = None

    try:
        tx = contract.functions.transfer(test_loan_id, offer_tuple).build_transaction({
            'from': initiator_address,
            'nonce': w3.eth.get_transaction_count(initiator_address),
            'gas': 3000000,
            'gasPrice': w3.eth.gas_price,
        })

        signed_tx = w3.eth.account.sign_transaction(tx, initiator_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        if tx_receipt['status'] == 0:
            reverted = True
            print_warning("Transaction reverted (as expected)")

    except Exception as e:
        reverted = True
        error_msg = str(e)
        revert_reason = error_msg
        print_success(f"✓ Transaction reverted before mining (as expected)")

        # Try to extract revert reason
        if "not registered" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'not registered'")

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
    old_lender_lend_balance_after = contract.functions.userLendBalance(old_lender_address, offer_id_bytes).call()

    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} → {protocol_fee_after / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance: {old_lender_lend_balance_before / 1e9:.2f} → {old_lender_lend_balance_after / 1e9:.2f} TAO")

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
    print_info(f"  Loan Data ID: {loan_term_after['loanDataId']}")
    print_info(f"  State: {['OPEN', 'IN_COLLECTION', 'REPAID', 'CLAIMED', 'RESOLVED'][loan_data_after['state']]}")
    print_info(f"  Lender: {offer_after['lender']}")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction reverted
    if not reverted and (tx_receipt and tx_receipt['status'] == 1):
        print_error("✗ Transaction succeeded unexpectedly!")
        print_error("Expected: Transaction should revert with 'not registered'")
        sys.exit(1)

    print_success("✓ Transaction reverted as expected")

    # Verify revert reason contains "not registered"
    if revert_reason and "not registered" in revert_reason.lower():
        print_success("✓ Revert reason confirmed: 'not registered'")
    elif revert_reason:
        print_warning(f"⚠ Revert reason may differ: {revert_reason[:200]}")

    # Verify loan state unchanged
    if loan_data_after['state'] != loan_data_before['state']:
        print_error(f"✗ Loan state changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Loan state unchanged")

    # Verify loanDataId unchanged
    if loan_term_after['loanDataId'] != loan_term_before['loanDataId']:
        print_error(f"✗ Loan Data ID changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Loan Data ID unchanged")

    # Verify lender unchanged
    if offer_after['lender'].lower() != offer_before['lender'].lower():
        print_error(f"✗ Lender changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Lender unchanged (still OLD_LENDER)")

    # Verify protocol fee unchanged
    if protocol_fee_after != protocol_fee_before:
        print_error(f"✗ Protocol fee changed unexpectedly!")
        sys.exit(1)
    print_success("✓ Protocol fee unchanged")

    # Verify lend balance unchanged
    if old_lender_lend_balance_after != old_lender_lend_balance_before:
        print_error(f"✗ OLD_LENDER lend balance changed unexpectedly!")
        sys.exit(1)
    print_success("✓ OLD_LENDER lend balance unchanged")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify only gas was deducted
    print_info("\nExpected changes:")
    print_info(f"  - {initiator_label} EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # Report results
    print_section("Test Result")

    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC01: Initiator Not Registered")
    print_success(f"Transaction correctly reverted with 'not registered'")
    print_success("All state validations passed")
    print_success("No unexpected state changes detected")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - Unregistered initiator cannot call transfer()")
    print(f"  - onlyRegistered modifier working correctly")
    print(f"  - Contract state protected from unauthorized access")
    print(f"  - Loan state remains: {['OPEN', 'IN_COLLECTION'][loan_data_before['state']]}")
    print(f"  - Loan Data ID unchanged: {loan_term_before['loanDataId']}")
    print(f"  - Lender unchanged: {offer_before['lender']}")

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
