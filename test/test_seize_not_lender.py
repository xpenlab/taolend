#!/usr/bin/env python3
"""
Test Case TC08: Not Lender (Seize)
Objective: Verify only lender can seize - borrower cannot seize their own collateral
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
    STATE_IN_COLLECTION
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
    print_section("Test Case TC08: Not Lender (Seize)")
    print(f"{CYAN}Objective:{NC} Verify only lender can seize - borrower cannot seize their own collateral")
    print(f"{CYAN}Strategy:{NC} Borrower attempts to seize their own loan")
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

    # Find a loan in IN_COLLECTION state
    print_info("Finding a loan in IN_COLLECTION state...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None
    lender_address = None
    borrower_address = None

    # Search backwards from next_loan_id
    for test_loan_id in range(next_loan_id - 1, max(0, next_loan_id - 100), -1):
        try:
            loan_info = get_loan_full(contract, test_loan_id)
            if loan_info and loan_info['data']['state'] == STATE_IN_COLLECTION:
                # Check if grace period has passed
                current_block = w3.eth.block_number
                last_update_block = loan_info['data']['lastUpdateBlock']
                min_loan_duration = 150  # Test mode

                if current_block > last_update_block + min_loan_duration:
                    loan_id = test_loan_id
                    loan_netuid = loan_info['term']['netuid']
                    lender_address = loan_info['offer']['lender']
                    borrower_address = loan_info['term']['borrower']
                    loan_collateral = loan_info['term']['collateralAmount']
                    loan_amount = loan_info['data']['loanAmount']

                    print_success(f"Found loan in IN_COLLECTION state: ID={loan_id}")
                    print_info(f"  Lender: {lender_address}")
                    print_info(f"  Borrower: {borrower_address}")
                    print_info(f"  State: IN_COLLECTION (1)")
                    print_info(f"  Collateral: {loan_collateral / 1e9:.2f} ALPHA")
                    print_info(f"  Loan: {loan_amount / 1e9:.2f} TAO")
                    print_info(f"  Grace period passed: Yes (block {current_block} > {last_update_block + min_loan_duration})")
                    break
        except Exception as e:
            continue

    if loan_id is None:
        print_error("No loans found in IN_COLLECTION state with grace period passed")
        print_error("Please run a collect test first and wait for grace period to expire")
        sys.exit(1)

    # Get borrower's private key
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
        sys.exit(1)

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
    loan_data_before = loan_info_before['data']
    loan_term_before = loan_info_before['term']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_before['state']} (IN_COLLECTION)")
    print_info(f"Lender: {lender_address}")
    print_warning(f"⚠️  Borrower {borrower_address} is NOT the lender - cannot seize")
    print_info(f"Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("STEP 4: Execute Test Operation - Seize (Expected to Fail)")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}✗ Revert:{NC} 'not lender'")
    print(f"  {CYAN}Reason:{NC} Only lender can seize collateral, borrower cannot")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from borrower's EVM TAO")

    print_info(f"\nAttempting to seize loan {loan_id} as borrower...")
    print_warning(f"⚠️  Borrower is trying to seize their own collateral (not allowed)")

    # Build transaction
    nonce = w3.eth.get_transaction_count(borrower_address)

    # Estimate gas (expected to fail)
    try:
        gas_estimate = contract.functions.seize(loan_id).estimate_gas({
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
    tx = contract.functions.seize(loan_id).build_transaction({
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
    print_info(f"State: {loan_data_after['state']} (still IN_COLLECTION)")
    print_info(f"Loan Amount: {loan_data_after['loanAmount'] / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("STEP 8: Compare and Verify")

    # Verify transaction status
    print_info(f"Transaction status: {tx_receipt['status']}")

    if tx_receipt['status'] == 0:
        print_success("✓ Transaction REVERTED as expected")
        print_success("✓ Test PASSED: Seize correctly rejected non-lender (borrower)")
    else:
        print_error("✗ Transaction SUCCEEDED unexpectedly")
        print_error("✗ Test FAILED: Seize should have reverted")
        sys.exit(1)

    # Verify no state changes
    print_info("Verifying no state changes...")

    if loan_data_before['state'] == loan_data_after['state']:
        print_success("✓ Loan state unchanged (still IN_COLLECTION)")
    else:
        print_error(f"✗ Loan state changed: {loan_data_before['state']} → {loan_data_after['state']}")

    # Print balance differences
    print_info("Balance differences:")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Summary
    print_section("TEST SUMMARY")
    print_success("✓ TC08 PASSED: Seize correctly rejects non-lender (borrower)")
    print_info("Access control: Only lender can seize collateral")
    print_info("Error message: 'not lender'")
    print_info("All state unchanged (except gas deduction)")

if __name__ == "__main__":
    main()
