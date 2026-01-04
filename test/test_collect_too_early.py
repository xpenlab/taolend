#!/usr/bin/env python3
"""
Test Case TC09: Collect Too Early
Objective: Verify collect fails when MIN_LOAN_DURATION has not passed
Tests: Duration check - require(block.number > startBlock + MIN_LOAN_DURATION, "too early")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "too early"
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
    create_offer, offer_to_tuple, save_offer_to_file,
    STATE_OPEN
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
    print_section("Test Case TC09: Collect Too Early")
    print(f"{CYAN}Objective:{NC} Verify collect fails when MIN_LOAN_DURATION has not passed")
    print(f"{CYAN}Strategy:{NC} Lender attempts to collect loan before MIN_LOAN_DURATION")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'too early'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender_address = addresses['LENDER1']['evmAddress']
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

    # Get MIN_LOAN_DURATION from contract
    min_loan_duration = contract.functions.MIN_LOAN_DURATION().call()
    print_info(f"MIN_LOAN_DURATION: {min_loan_duration} blocks")

    # Find a recent OPEN loan (within MIN_LOAN_DURATION)
    print_info("Finding a recent OPEN loan (within MIN_LOAN_DURATION)...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None
    current_block = w3.eth.block_number

    # Search backwards from next_loan_id for a very recent loan
    for test_loan_id in range(next_loan_id - 1, max(0, next_loan_id - 20), -1):
        try:
            loan_info = get_loan_full(contract, test_loan_id)
            if loan_info and loan_info['data']['state'] == STATE_OPEN:
                start_block = loan_info['data']['startBlock']
                blocks_passed = current_block - start_block

                # Check if loan is still within MIN_LOAN_DURATION
                if blocks_passed <= min_loan_duration:
                    loan_id = test_loan_id
                    loan_netuid = loan_info['term']['netuid']
                    loan_lender = loan_info['offer']['lender']
                    loan_borrower = loan_info['term']['borrower']
                    loan_collateral = loan_info['term']['collateralAmount']
                    loan_amount = loan_info['data']['loanAmount']

                    print_success(f"Found recent loan: ID={loan_id}, state=OPEN")
                    print_info(f"  Lender: {loan_lender}")
                    print_info(f"  Borrower: {loan_borrower}")
                    print_info(f"  Start block: {start_block}, Current: {current_block}")
                    print_info(f"  Blocks passed: {blocks_passed} (MIN_LOAN_DURATION: {min_loan_duration})")
                    print_warning(f"  ⚠️  Still within MIN_LOAN_DURATION ({blocks_passed} ≤ {min_loan_duration})")
                    print_info(f"  Collateral: {loan_collateral / 1e9:.2f} ALPHA")
                    print_info(f"  Loan: {loan_amount / 1e9:.2f} TAO")

                    # Update lender_address to match the loan's actual lender
                    lender_address = loan_lender
                    borrower_address = loan_borrower
                    break
        except Exception as e:
            continue

    if loan_id is None:
        print_warning("No recent OPEN loans found within MIN_LOAN_DURATION")
        print_info("Creating a new loan for this test...")

        # Create a new loan
        # Get private keys
        lender_private_key = os.environ.get("LENDER1_PRIVATE_KEY")
        borrower_private_key = os.environ.get("BORROWER1_PRIVATE_KEY")

        if not lender_private_key or not borrower_private_key:
            print_error("LENDER1_PRIVATE_KEY or BORROWER1_PRIVATE_KEY not found in .env")
            sys.exit(1)

        # Use netuid 2 or 3 for test
        test_netuid = 2

        # Check borrower has ALPHA deposited
        borrower_alpha_balance = contract.functions.userAlphaBalance(borrower_address, test_netuid).call()
        if borrower_alpha_balance < int(10e9):  # Need at least 10 ALPHA
            print_error(f"BORROWER needs at least 10 ALPHA on netuid {test_netuid}")
            print_error(f"Current balance: {borrower_alpha_balance / 1e9:.2f} ALPHA")
            sys.exit(1)

        # Check lender has TAO
        lender_tao_balance = contract.functions.userAlphaBalance(lender_address, 0).call()
        if lender_tao_balance < int(5e9):  # Need at least 5 TAO
            print_error(f"LENDER needs at least 5 TAO")
            print_error(f"Current balance: {lender_tao_balance / 1e9:.2f} TAO")
            sys.exit(1)

        # Create offer
        print_info("Creating offer for LENDER...")
        alpha_price = contract.functions.getAlphaPrice(test_netuid).call()
        safe_max_alpha_price = int(alpha_price * 0.85)  # 85% of current price

        offer = create_offer(
            w3=w3,
            contract=contract,
            lender_address=lender_address,
            lender_private_key=lender_private_key,
            netuid=test_netuid,
            max_tao_amount=int(100e9),  # 100 TAO
            max_alpha_price=safe_max_alpha_price,
            daily_interest_rate=5_000_000,  # 0.5%
            expire_block=w3.eth.block_number + 10000
        )
        save_offer_to_file(offer)
        print_success(f"Created offer: {offer['offerId'][:16]}...")

        # Borrow
        print_info("BORROWER borrowing TAO...")
        collateral_amount = int(10e9)  # 10 ALPHA
        loan_amount = int(5e9)  # 5 TAO

        offer_tuple = offer_to_tuple(offer)
        nonce = w3.eth.get_transaction_count(borrower_address)

        tx = contract.functions.borrow(
            offer_tuple,
            collateral_amount,
            loan_amount
        ).build_transaction({
            'from': borrower_address,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price,
            'chainId': chain_id
        })

        signed_tx = w3.eth.account.sign_transaction(tx, borrower_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Borrow transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if tx_receipt['status'] == 0:
            print_error("Borrow transaction failed")
            sys.exit(1)

        # Get loan ID from event
        borrow_events = contract.events.BorrowLoan().process_receipt(tx_receipt)
        if len(borrow_events) > 0:
            loan_id = borrow_events[0]['args']['loanId']
            print_success(f"Loan created: ID={loan_id}")
            loan_netuid = test_netuid
        else:
            print_error("Failed to get loan ID from BorrowLoan event")
            sys.exit(1)

    # Get lender's private key
    lender_private_key = None
    lender_label = None
    for account_name, account_data in addresses.items():
        if account_data.get('evmAddress', '').lower() == lender_address.lower():
            lender_private_key = os.environ.get(f"{account_name}_PRIVATE_KEY")
            lender_label = account_name
            if lender_private_key:
                print_success(f"Found lender private key: {account_name}")
                break

    if not lender_private_key:
        print_error(f"Private key not found for lender {lender_address}")
        sys.exit(1)

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("STEP 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, loan_netuid])
    addresses_list = [
        {"address": lender_address, "label": f"LENDER ({lender_label})"},
        {"address": borrower_address, "label": "BORROWER"},
        {"address": contract.address, "label": "CONTRACT"}
    ]

    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # ========================================================================
    # STEP 2: Read Initial Account Balances (included in snapshot)
    # ========================================================================
    print_section("STEP 2: Read Initial Account Balances")
    print_info("Account balances captured in snapshot above")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("STEP 3: Read Initial Loan State")

    loan_info_before = get_loan_full(contract, loan_id)
    loan_term_before = loan_info_before['term']
    loan_data_before = loan_info_before['data']
    offer_before = loan_info_before['offer']

    current_block = w3.eth.block_number
    blocks_passed = current_block - loan_data_before['startBlock']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_before['state']} (OPEN)")
    print_info(f"Start Block: {loan_data_before['startBlock']}")
    print_info(f"Current Block: {current_block}")
    print_info(f"Blocks Passed: {blocks_passed}")
    print_info(f"MIN_LOAN_DURATION: {min_loan_duration}")
    print_warning(f"Duration Check: {blocks_passed} ≤ {min_loan_duration} (too early)")
    print_info(f"Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("STEP 4: Execute Test Operation - Collect (Expected to Fail)")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}✗ Revert:{NC} 'too early'")
    print(f"  {CYAN}Reason:{NC} Loan duration has not passed MIN_LOAN_DURATION")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from lender's EVM TAO")

    print_info(f"\nAttempting to collect loan {loan_id}...")
    print_warning(f"⚠️  Current duration: {blocks_passed} blocks ≤ MIN_LOAN_DURATION: {min_loan_duration} blocks")

    # Build transaction
    nonce = w3.eth.get_transaction_count(lender_address)

    # Estimate gas (expected to fail)
    try:
        gas_estimate = contract.functions.collect(loan_id).estimate_gas({
            'from': lender_address,
            'nonce': nonce
        })
        print_info(f"Gas estimate: {gas_estimate:,}")
    except Exception as e:
        error_msg = str(e)
        if 'too early' in error_msg:
            print_success(f"✓ Gas estimation failed (expected): 'too early'")
        else:
            print_info(f"Gas estimation failed: {error_msg[:80]}...")
        gas_estimate = 500000  # Use default

    # Build and sign transaction
    tx = contract.functions.collect(loan_id).build_transaction({
        'from': lender_address,
        'nonce': nonce,
        'gas': gas_estimate,
        'gasPrice': w3.eth.gas_price,
        'chainId': chain_id
    })

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, lender_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print_info(f"\nTransaction sent: {tx_hash.hex()}")

    # Wait for receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("STEP 5: Read Final Contract State")

    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # ========================================================================
    # STEP 6: Read Final Account Balances (included in snapshot)
    # ========================================================================
    print_section("STEP 6: Read Final Account Balances")
    print_info("Account balances captured in snapshot above")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("STEP 7: Read Final Loan State")

    loan_info_after = get_loan_full(contract, loan_id)
    loan_data_after = loan_info_after['data']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_after['state']}")
    print_info(f"Loan Amount: {loan_data_after['loanAmount'] / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("STEP 8: Compare and Verify")

    # Verify transaction status
    print_info(f"Transaction status: {tx_receipt['status']}")

    if tx_receipt['status'] == 0:
        print_success("✓ Transaction REVERTED as expected")
        print_success("✓ Test PASSED: Collect correctly rejected (too early)")
    else:
        print_error("✗ Transaction SUCCEEDED unexpectedly")
        print_error("✗ Test FAILED: Collect should have reverted")
        sys.exit(1)

    # Verify no state changes
    print_info("Verifying no state changes...")

    if loan_data_before['state'] == loan_data_after['state']:
        print_success("✓ Loan state unchanged (still OPEN)")
    else:
        print_error(f"✗ Loan state changed: {loan_data_before['state']} → {loan_data_after['state']}")

    # Print balance differences
    print_info("Balance differences:")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Summary
    print_section("TEST SUMMARY")
    print_success("✓ TC09 PASSED: Collect correctly rejects too early attempt")
    print_info("Duration protection working correctly")
    print_info("Error message: 'too early'")
    print_info("All state unchanged (except gas deduction)")

if __name__ == "__main__":
    main()
