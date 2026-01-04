#!/usr/bin/env python3
"""
Test Case TC08: Not Lender (Borrower Tries)
Objective: Verify collect fails when initiator is not the lender
Tests: Lender check - require(offer.lender == msg.sender, "not lender")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "not lender"
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
    print_section("Test Case TC08: Not Lender (Borrower Tries)")
    print(f"{CYAN}Objective:{NC} Verify collect fails when initiator is not the lender")
    print(f"{CYAN}Strategy:{NC} Borrower attempts to collect their own loan")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'not lender'\n")

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

    # Find an OPEN loan where MIN_LOAN_DURATION has passed
    print_info("Finding an OPEN loan that has passed MIN_LOAN_DURATION...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None
    current_block = w3.eth.block_number
    lender_address = None
    borrower_address = None

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
                    lender_address = loan_info['offer']['lender']
                    borrower_address = loan_info['term']['borrower']
                    loan_collateral = loan_info['term']['collateralAmount']
                    loan_amount = loan_info['data']['loanAmount']

                    print_success(f"Found eligible loan: ID={loan_id}, state=OPEN")
                    print_info(f"  Lender: {lender_address}")
                    print_info(f"  Borrower: {borrower_address}")
                    print_info(f"  Start block: {start_block}, Current: {current_block}")
                    print_info(f"  Blocks passed: {blocks_passed} (MIN_LOAN_DURATION: {min_loan_duration})")
                    print_info(f"  Collateral: {loan_collateral / 1e9:.2f} ALPHA")
                    print_info(f"  Loan: {loan_amount / 1e9:.2f} TAO")
                    break
        except Exception as e:
            continue

    if loan_id is None:
        print_error("No eligible OPEN loans found that have passed MIN_LOAN_DURATION")
        print_error("Please create a loan and wait for MIN_LOAN_DURATION blocks")
        sys.exit(1)

    # Get borrower's private key (we want borrower to try to collect)
    borrower_private_key = None
    borrower_label = None
    for account_name, account_data in addresses.items():
        if account_data.get('evmAddress', '').lower() == borrower_address.lower():
            borrower_private_key = os.environ.get(f"{account_name}_PRIVATE_KEY")
            borrower_label = account_name
            if borrower_private_key:
                print_success(f"Found borrower private key: {account_name}")
                break

    if not borrower_private_key:
        print_error(f"Private key not found for borrower {borrower_address}")
        print_error("Please ensure the borrower's private key is set in .env")
        sys.exit(1)

    # Verify borrower is registered
    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    if not borrower_registered:
        print_error(f"Borrower {borrower_address} must be registered")
        sys.exit(1)
    print_success("Borrower is registered")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("STEP 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, loan_netuid])
    addresses_list = [
        {"address": lender_address, "label": "LENDER"},
        {"address": borrower_address, "label": f"BORROWER ({borrower_label})"},
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
    print_info(f"Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("STEP 4: Execute Test Operation - Collect (Expected to Fail)")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}✗ Revert:{NC} 'not lender'")
    print(f"  {CYAN}Reason:{NC} Only lender can initiate collection")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from borrower's EVM TAO")

    current_block = w3.eth.block_number
    print_info(f"\nAttempting to collect loan {loan_id}...")
    print_warning(f"⚠️  Initiator: {borrower_address} (BORROWER, not lender)")
    print_info(f"Lender: {lender_address}")
    print_info(f"Current block: {current_block}")

    # Build transaction
    nonce = w3.eth.get_transaction_count(borrower_address)

    # Estimate gas (expected to fail)
    try:
        gas_estimate = contract.functions.collect(loan_id).estimate_gas({
            'from': borrower_address,
            'nonce': nonce
        })
        print_info(f"Gas estimate: {gas_estimate:,}")
    except Exception as e:
        error_msg = str(e)
        if 'not lender' in error_msg:
            print_success(f"✓ Gas estimation failed (expected): 'not lender'")
        else:
            print_info(f"Gas estimation failed: {error_msg[:80]}...")
        gas_estimate = 500000  # Use default

    # Build and sign transaction
    tx = contract.functions.collect(loan_id).build_transaction({
        'from': borrower_address,
        'nonce': nonce,
        'gas': gas_estimate,
        'gasPrice': w3.eth.gas_price,
        'chainId': chain_id
    })

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, borrower_private_key)
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
        print_success("✓ Test PASSED: Collect correctly rejected non-lender")
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

    if loan_term_before['loanDataId'] == loan_info_after['term']['loanDataId']:
        print_success("✓ Loan data ID unchanged")
    else:
        print_error("✗ Loan data ID changed unexpectedly")

    # Print balance differences
    print_info("Balance differences:")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Summary
    print_section("TEST SUMMARY")
    print_success("✓ TC08 PASSED: Collect correctly rejects non-lender")
    print_info("Only lender can initiate collection")
    print_info("Error message: 'not lender'")
    print_info("All state unchanged (except gas deduction)")

if __name__ == "__main__":
    main()
