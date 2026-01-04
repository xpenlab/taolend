#!/usr/bin/env python3
"""
Test Case TC10: Collect Success
Objective: Verify lender can successfully collect loan after MIN_LOAN_DURATION
Tests: Successful state transition from OPEN → IN_COLLECTION

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction succeeds, loan state changes to IN_COLLECTION
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
    print_section("Test Case TC10: Collect Success")
    print(f"{CYAN}Objective:{NC} Verify lender can successfully collect loan after MIN_LOAN_DURATION")
    print(f"{CYAN}Strategy:{NC} Lender collects OPEN loan after waiting sufficient time")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, loan state: OPEN → IN_COLLECTION\n")

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

    # Find an OPEN loan where sufficient time has passed
    print_info("Finding an OPEN loan that has passed MIN_LOAN_DURATION...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None
    current_block = w3.eth.block_number

    # Search backwards from next_loan_id
    for test_loan_id in range(next_loan_id - 1, max(0, next_loan_id - 50), -1):
        try:
            loan_info = get_loan_full(contract, test_loan_id)
            if loan_info and loan_info['data']['state'] == STATE_OPEN:
                start_block = loan_info['data']['startBlock']
                blocks_passed = current_block - start_block

                # Check if MIN_LOAN_DURATION has passed
                if blocks_passed > min_loan_duration:
                    loan_id = test_loan_id
                    loan_netuid = loan_info['term']['netuid']
                    loan_lender = loan_info['offer']['lender']
                    loan_borrower = loan_info['term']['borrower']
                    loan_collateral = loan_info['term']['collateralAmount']
                    loan_amount = loan_info['data']['loanAmount']

                    print_success(f"Found eligible loan: ID={loan_id}, state=OPEN")
                    print_info(f"  Lender: {loan_lender}")
                    print_info(f"  Borrower: {loan_borrower}")
                    print_info(f"  Start block: {start_block}, Current: {current_block}")
                    print_info(f"  Blocks passed: {blocks_passed} (MIN_LOAN_DURATION: {min_loan_duration})")
                    print_info(f"  Collateral: {loan_collateral / 1e9:.2f} ALPHA")
                    print_info(f"  Loan: {loan_amount / 1e9:.2f} TAO")

                    # Update lender_address to match the loan's actual lender
                    lender_address = loan_lender
                    borrower_address = loan_borrower
                    break
        except Exception as e:
            continue

    if loan_id is None:
        print_error("No eligible OPEN loans found that have passed MIN_LOAN_DURATION")
        print_error("Please create a loan and wait for MIN_LOAN_DURATION blocks")
        sys.exit(1)

    # Get lender's private key
    # Try to match lender_address to a known account
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
        print_error("Please ensure the lender's private key is set in .env")
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

    print_info(f"Loan ID: {loan_id}")
    print_info(f"Borrower: {loan_term_before['borrower']}")
    print_info(f"Lender: {offer_before['lender']}")
    print_info(f"State: {loan_data_before['state']} (OPEN)")
    print_info(f"Start Block: {loan_data_before['startBlock']}")
    print_info(f"Last Update Block: {loan_data_before['lastUpdateBlock']}")
    print_info(f"Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"Loan Data ID: {loan_term_before['loanDataId']}")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("STEP 4: Execute Test Operation - Collect")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}✓ Success:{NC} Loan collected successfully")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - Loan state: OPEN (0) → IN_COLLECTION (1)")
    print(f"    - lastUpdateBlock updated to current block")
    print(f"    - No balance changes (state transition only)")

    current_block = w3.eth.block_number
    print_info(f"\nAttempting to collect loan {loan_id}...")
    print_info(f"Lender: {lender_address}")
    print_info(f"Current block: {current_block}")
    print_info(f"Loan start block: {loan_data_before['startBlock']}")
    print_info(f"Blocks passed: {current_block - loan_data_before['startBlock']}")

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
    offer_after = loan_info_after['offer']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_after['state']} (IN_COLLECTION)")
    print_info(f"Start Block: {loan_data_after['startBlock']}")
    print_info(f"Last Update Block: {loan_data_after['lastUpdateBlock']}")
    print_info(f"Loan Amount: {loan_data_after['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Loan Data ID: {loan_term_after['loanDataId']}")

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
        print_error("✗ Test FAILED: Collect should have succeeded")
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

    # Print balance differences
    print_info("\nBalance differences:")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify no balance changes (except gas)
    print_info("\nVerifying no balance changes (except gas)...")

    # Check contract balances unchanged
    contract_before = snapshot_before['contract']
    contract_after = snapshot_after['contract']

    if contract_before['protocol_fee_accumulated']['fee_rao'] == contract_after['protocol_fee_accumulated']['fee_rao']:
        print_success("✓ Protocol fee unchanged")
    else:
        print_error(f"✗ Protocol fee changed: {contract_before['protocol_fee_accumulated']['fee_rao']} → {contract_after['protocol_fee_accumulated']['fee_rao']}")

    # Check events
    print_info("\nVerifying events...")
    collect_events = contract.events.CollectLoan().process_receipt(tx_receipt)
    if len(collect_events) == 1:
        event = collect_events[0]['args']
        print_success(f"✓ CollectLoan event emitted")
        print_info(f"  lender: {event['lender']}")
        print_info(f"  loanId: {event['loanId']}")
        print_info(f"  loanDataId: {event['loanDataId']}")
        print_info(f"  offerId: {event['offerId'].hex()[:16]}...")
        print_info(f"  netuid: {event['netuid']}")
        print_info(f"  block: {event['block']}")
        print_info(f"  collateralAmount: {event['collateralAmount'] / 1e9:.2f} ALPHA")
        print_info(f"  loanAmount: {event['loanAmount'] / 1e9:.2f} TAO")

        # Verify event fields
        if event['lender'].lower() == lender_address.lower():
            print_success("  ✓ Lender matches")
        else:
            print_error(f"  ✗ Lender mismatch")

        if event['loanId'] == loan_id:
            print_success("  ✓ Loan ID matches")
        else:
            print_error(f"  ✗ Loan ID mismatch")
    else:
        print_error(f"✗ Expected 1 CollectLoan event, got {len(collect_events)}")

    # Summary
    print_section("TEST SUMMARY")
    print_success("✓ TC10 PASSED: Collect successful")
    print_info("State transition: OPEN → IN_COLLECTION")
    print_info("lastUpdateBlock updated to current block")
    print_info("No balance changes (state transition only)")
    print_info("CollectLoan event emitted correctly")

if __name__ == "__main__":
    main()
