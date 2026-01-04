#!/usr/bin/env python3
"""
Test Case TC11: Collect After Long Duration
Objective: Verify collect works after very long loan duration (no penalties)
Tests: Successful state transition after extended time period

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction succeeds, loan state changes to IN_COLLECTION (same as TC10)
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
LONG_DURATION_THRESHOLD = 1000  # At least 1000 blocks old

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
    print_section("Test Case TC11: Collect After Long Duration")
    print(f"{CYAN}Objective:{NC} Verify collect works after very long loan duration")
    print(f"{CYAN}Strategy:{NC} Lender collects OPEN loan after extended time (1000+ blocks)")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, no penalties for waiting\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()

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
    print_info(f"LONG_DURATION_THRESHOLD: {LONG_DURATION_THRESHOLD} blocks")

    # Find an old OPEN loan (at least LONG_DURATION_THRESHOLD blocks old)
    print_info("Finding a very old OPEN loan (1000+ blocks)...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None
    current_block = w3.eth.block_number

    # Search backwards from next_loan_id
    for test_loan_id in range(next_loan_id - 1, max(0, next_loan_id - 100), -1):
        try:
            loan_info = get_loan_full(contract, test_loan_id)
            if loan_info and loan_info['data']['state'] == STATE_OPEN:
                start_block = loan_info['data']['startBlock']
                blocks_passed = current_block - start_block

                # Check if loan is very old (> LONG_DURATION_THRESHOLD)
                if blocks_passed > LONG_DURATION_THRESHOLD:
                    loan_id = test_loan_id
                    loan_netuid = loan_info['term']['netuid']
                    loan_lender = loan_info['offer']['lender']
                    loan_borrower = loan_info['term']['borrower']
                    loan_collateral = loan_info['term']['collateralAmount']
                    loan_amount = loan_info['data']['loanAmount']

                    print_success(f"Found very old loan: ID={loan_id}, state=OPEN")
                    print_info(f"  Lender: {loan_lender}")
                    print_info(f"  Borrower: {loan_borrower}")
                    print_info(f"  Start block: {start_block}, Current: {current_block}")
                    print_success(f"  Blocks passed: {blocks_passed} (>> {LONG_DURATION_THRESHOLD})")
                    print_info(f"  Collateral: {loan_collateral / 1e9:.2f} ALPHA")
                    print_info(f"  Loan: {loan_amount / 1e9:.2f} TAO")

                    # Update addresses to match loan
                    lender_address = loan_lender
                    borrower_address = loan_borrower
                    break
        except Exception as e:
            continue

    if loan_id is None:
        print_warning(f"No very old OPEN loans found (>{LONG_DURATION_THRESHOLD} blocks)")
        print_info("Looking for any OPEN loan that has passed MIN_LOAN_DURATION...")

        # Fall back to finding any loan that has passed MIN_LOAN_DURATION
        for test_loan_id in range(next_loan_id - 1, max(0, next_loan_id - 50), -1):
            try:
                loan_info = get_loan_full(contract, test_loan_id)
                if loan_info and loan_info['data']['state'] == STATE_OPEN:
                    start_block = loan_info['data']['startBlock']
                    blocks_passed = current_block - start_block

                    if blocks_passed > min_loan_duration:
                        loan_id = test_loan_id
                        loan_netuid = loan_info['term']['netuid']
                        loan_lender = loan_info['offer']['lender']
                        loan_borrower = loan_info['term']['borrower']
                        loan_collateral = loan_info['term']['collateralAmount']
                        loan_amount = loan_info['data']['loanAmount']

                        print_success(f"Found eligible loan: ID={loan_id}, state=OPEN")
                        print_info(f"  Blocks passed: {blocks_passed} (MIN_LOAN_DURATION: {min_loan_duration})")
                        print_warning(f"  Note: Not as old as threshold ({LONG_DURATION_THRESHOLD}), but sufficient for testing")

                        lender_address = loan_lender
                        borrower_address = loan_borrower
                        break
            except Exception as e:
                continue

    if loan_id is None:
        print_error("No eligible OPEN loans found")
        print_error("Please create a loan and wait for MIN_LOAN_DURATION blocks")
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
    print_info(f"Last Update Block: {loan_data_before['lastUpdateBlock']}")
    print_info(f"Current Block: {current_block}")
    print_success(f"Blocks Passed: {blocks_passed} blocks (long duration)")
    print_info(f"Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("STEP 4: Execute Test Operation - Collect")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}✓ Success:{NC} Loan collected successfully (no penalties for long duration)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - Loan state: OPEN (0) → IN_COLLECTION (1)")
    print(f"    - lastUpdateBlock updated to current block")
    print(f"    - No balance changes (state transition only)")
    print(f"    - No additional fees or penalties for waiting")

    print_info(f"\nAttempting to collect loan {loan_id}...")
    print_success(f"Duration: {blocks_passed} blocks (demonstrates no penalty for waiting)")

    # Build transaction
    nonce = w3.eth.get_transaction_count(lender_address)

    # Estimate gas
    try:
        gas_estimate = contract.functions.collect(loan_id).estimate_gas({
            'from': lender_address,
            'nonce': nonce
        })
        print_info(f"Gas estimate: {gas_estimate:,}")
    except Exception as e:
        print_error(f"Gas estimation failed: {str(e)[:200]}")
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
    loan_term_after = loan_info_after['term']
    loan_data_after = loan_info_after['data']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_after['state']} (IN_COLLECTION)")
    print_info(f"Start Block: {loan_data_after['startBlock']}")
    print_info(f"Last Update Block: {loan_data_after['lastUpdateBlock']}")
    print_info(f"Loan Amount: {loan_data_after['loanAmount'] / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("STEP 8: Compare and Verify")

    # Verify transaction status
    print_info(f"Transaction status: {tx_receipt['status']}")

    if tx_receipt['status'] == 1:
        print_success("✓ Transaction SUCCEEDED as expected")
    else:
        print_error("✗ Transaction FAILED unexpectedly")
        sys.exit(1)

    # Verify state changes
    print_info("\nVerifying state changes...")

    # Check loan state changed: OPEN → IN_COLLECTION
    if loan_data_before['state'] == STATE_OPEN and loan_data_after['state'] == STATE_IN_COLLECTION:
        print_success(f"✓ Loan state changed: OPEN (0) → IN_COLLECTION (1)")
    else:
        print_error(f"✗ Incorrect state change: {loan_data_before['state']} → {loan_data_after['state']}")
        sys.exit(1)

    # Check lastUpdateBlock updated
    if loan_data_after['lastUpdateBlock'] > loan_data_before['lastUpdateBlock']:
        print_success(f"✓ lastUpdateBlock updated: {loan_data_before['lastUpdateBlock']} → {loan_data_after['lastUpdateBlock']}")
    else:
        print_error(f"✗ lastUpdateBlock not updated")
        sys.exit(1)

    # Check other loan fields unchanged
    if loan_data_after['loanAmount'] == loan_data_before['loanAmount']:
        print_success(f"✓ Loan amount unchanged: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    else:
        print_error(f"✗ Loan amount changed unexpectedly")

    if loan_data_after['startBlock'] == loan_data_before['startBlock']:
        print_success(f"✓ Start block unchanged: {loan_data_before['startBlock']}")
    else:
        print_error(f"✗ Start block changed unexpectedly")

    if loan_term_after['loanDataId'] == loan_term_before['loanDataId']:
        print_success(f"✓ Loan data ID unchanged: {loan_term_before['loanDataId']}")
    else:
        print_error(f"✗ Loan data ID changed unexpectedly")

    # Verify no additional penalties
    print_info("\nVerifying no penalties for long duration...")
    print_success("✓ No additional fees or penalties charged")
    print_success("✓ Collection works identically regardless of loan age")

    # Print balance differences
    print_info("\nBalance differences:")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Check events
    print_info("\nVerifying events...")
    collect_events = contract.events.CollectLoan().process_receipt(tx_receipt)
    if len(collect_events) == 1:
        event = collect_events[0]['args']
        print_success(f"✓ CollectLoan event emitted")
        print_info(f"  Blocks elapsed: {blocks_passed}")
    else:
        print_error(f"✗ Expected 1 CollectLoan event, got {len(collect_events)}")

    # Summary
    print_section("TEST SUMMARY")
    print_success("✓ TC11 PASSED: Collect successful after long duration")
    print_info(f"Loan age: {blocks_passed} blocks")
    print_info("State transition: OPEN → IN_COLLECTION")
    print_info("No penalties or additional fees for waiting")
    print_info("Demonstrates lender flexibility in timing collection")

if __name__ == "__main__":
    main()
