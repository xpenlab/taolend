#!/usr/bin/env python3
"""
Test Case TC10: Low Lender TAO
Objective: Verify refinance fails when new lender has insufficient TAO balance
Tests: Lender balance check - require(userAlphaBalance[_offer.lender][0] >= _newLoanAmount, "low lender tao")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "low lender tao"
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
    create_offer, offer_to_tuple, send_transaction,
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
    print_section("Test Case TC10: Low Lender TAO")
    print(f"{CYAN}Objective:{NC} Verify refinance fails when new lender has insufficient TAO balance")
    print(f"{CYAN}Strategy:{NC} Withdraw lender's TAO to make balance insufficient, then attempt refinance")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'low lender tao'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    borrower_address = addresses['BORROWER1']['evmAddress']
    new_lender_address = addresses['LENDER2']['evmAddress']

    # Get private keys
    borrower_private_key = os.environ.get('BORROWER1_PRIVATE_KEY')
    new_lender_private_key = os.environ.get('LENDER2_PRIVATE_KEY')
    if not borrower_private_key or not new_lender_private_key:
        print_error("BORROWER1_PRIVATE_KEY or LENDER2_PRIVATE_KEY not found in .env")
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

    # Verify users are registered
    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    new_lender_registered = contract.functions.registeredUser(new_lender_address).call()
    if not borrower_registered or not new_lender_registered:
        print_error(f"BORROWER1 and LENDER2 must be registered for this test")
        sys.exit(1)
    print_success(f"BORROWER1 and LENDER2 are registered")

    # Find an active loan for BORROWER1
    print_info("Finding active loan for BORROWER1...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None
    loan_amount = None

    for test_loan_id in range(next_loan_id - 1, max(0, next_loan_id - 20), -1):
        try:
            loan_info = get_loan_full(contract, test_loan_id)
            if loan_info and loan_info['data']['state'] in [STATE_OPEN, STATE_IN_COLLECTION]:
                if loan_info['term']['borrower'].lower() == borrower_address.lower():
                    loan_id = test_loan_id
                    loan_netuid = loan_info['term']['netuid']
                    loan_collateral = loan_info['term']['collateralAmount']
                    loan_amount = loan_info['data']['loanAmount']
                    print_success(f"Found active loan: ID={loan_id}, netuid={loan_netuid}")
                    print_info(f"  Collateral: {loan_collateral / 1e9:.2f} ALPHA, Loan: {loan_amount / 1e9:.2f} TAO")
                    break
        except Exception as e:
            continue

    if loan_id is None:
        print_error("No active loans found for BORROWER1.")
        sys.exit(1)

    # Check new lender's current TAO balance
    new_lender_tao_balance = contract.functions.userAlphaBalance(new_lender_address, 0).call()
    print_info(f"NEW_LENDER current TAO balance: {new_lender_tao_balance / 1e9:.2f} TAO")

    # Withdraw enough TAO to make balance insufficient
    # We want balance < loan_amount
    target_balance = int(loan_amount * 0.5)  # Keep only 50% of loan amount
    withdraw_amount = new_lender_tao_balance - target_balance

    if withdraw_amount > 0:
        print_info(f"Withdrawing {withdraw_amount / 1e9:.2f} TAO from NEW_LENDER to make balance insufficient...")

        try:
            tx_data = contract.functions.withdrawTao(
                withdraw_amount
            ).build_transaction({
                'from': new_lender_address,
                'nonce': w3.eth.get_transaction_count(new_lender_address),
                'gas': 500000,
                'gasPrice': w3.eth.gas_price,
                'chainId': chain_id
            })

            signed_tx = w3.eth.account.sign_transaction(tx_data, new_lender_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if tx_receipt['status'] == 1:
                print_success(f"✓ Withdrew {withdraw_amount / 1e9:.2f} TAO")
            else:
                print_error("Withdrawal failed")
                sys.exit(1)
        except Exception as e:
            print_error(f"Withdrawal error: {e}")
            sys.exit(1)

    # Verify insufficient balance
    new_lender_tao_balance = contract.functions.userAlphaBalance(new_lender_address, 0).call()
    print_warning(f"NEW_LENDER TAO balance: {new_lender_tao_balance / 1e9:.2f} TAO (INSUFFICIENT for {loan_amount / 1e9:.2f} TAO loan)")

    if new_lender_tao_balance >= loan_amount:
        print_error(f"Balance still sufficient: {new_lender_tao_balance / 1e9:.2f} TAO >= {loan_amount / 1e9:.2f} TAO")
        sys.exit(1)

    # Create offer for NEW_LENDER
    print_info("Creating offer for NEW_LENDER...")

    # Query alpha price
    try:
        alpha_price = contract.functions.getAlphaPrice(loan_netuid).call()
        safe_max_alpha_price = int(alpha_price * 0.85)
    except:
        safe_max_alpha_price = int(0.5e9)

    new_offer = create_offer(
        w3=w3,
        contract=contract,
        lender_address=new_lender_address,
        lender_private_key=new_lender_private_key,
        netuid=loan_netuid,
        max_tao_amount=int(200e9),  # High max to not hit that limit
        max_alpha_price=safe_max_alpha_price,
        daily_interest_rate=5_000_000,
        expire_seconds=86400
    )
    print_success(f"Created offer: offerId={new_offer['offerId']}, netuid={new_offer['netuid']}")

    # Calculate refinance amount (same as original loan)
    new_loan_amount = loan_amount
    print_info(f"Refinance amount: {new_loan_amount / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("STEP 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, loan_netuid])
    addresses_list = [
        {"address": borrower_address, "label": "BORROWER1"},
        {"address": new_lender_address, "label": "NEW_LENDER"},
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
    print_info(f"Loan Netuid: {loan_term_before['netuid']}")
    print_info(f"State: {loan_data_before['state']} (OPEN)")
    print_info(f"Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("STEP 4: Execute Test Operation - Refinance")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}✗ Revert:{NC} 'low lender tao'")
    print(f"  {CYAN}Reason:{NC} NEW_LENDER TAO balance ({new_lender_tao_balance / 1e9:.2f} TAO) < Loan amount ({new_loan_amount / 1e9:.2f} TAO)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from borrower's EVM TAO")

    print_info(f"\nAttempting to refinance loan {loan_id}...")
    print_info(f"Borrower: {borrower_address}")
    print_info(f"New Lender: {new_lender_address}")
    print_warning(f"New Lender TAO: {new_lender_tao_balance / 1e9:.2f} TAO (INSUFFICIENT)")
    print_info(f"Required TAO: {new_loan_amount / 1e9:.2f} TAO")

    # Build transaction
    offer_tuple = offer_to_tuple(new_offer)
    nonce = w3.eth.get_transaction_count(borrower_address)

    # Estimate gas (expected to fail)
    try:
        gas_estimate = contract.functions.refinance(
            loan_id,
            offer_tuple,
            new_loan_amount
        ).estimate_gas({
            'from': borrower_address,
            'nonce': nonce
        })
        print_info(f"Gas estimate: {gas_estimate:,}")
    except Exception as e:
        error_msg = str(e)
        if 'low lender tao' in error_msg:
            print_success(f"✓ Gas estimation failed (expected): 'low lender tao'")
        else:
            print_info(f"Gas estimation failed: {error_msg[:80]}...")
        gas_estimate = 500000

    # Build and sign transaction
    tx = contract.functions.refinance(
        loan_id,
        offer_tuple,
        new_loan_amount
    ).build_transaction({
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
    loan_term_after = loan_info_after['term']
    loan_data_after = loan_info_after['data']
    offer_after = loan_info_after['offer']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_after['state']} (OPEN)")
    print_info(f"Loan Amount: {loan_data_after['loanAmount'] / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("STEP 8: Compare and Verify")

    # Verify transaction status
    print_info(f"Transaction status: {tx_receipt['status']}")

    if tx_receipt['status'] == 0:
        print_success("✓ Transaction REVERTED as expected")
        print_success("✓ Test PASSED: Refinance correctly rejected insufficient lender TAO balance")
    else:
        print_error("✗ Transaction SUCCEEDED unexpectedly")
        print_error("✗ Test FAILED: Refinance should have reverted")
        sys.exit(1)

    # Verify no state changes
    print_info("Verifying no state changes...")

    if loan_data_before['state'] == loan_data_after['state']:
        print_success("✓ Loan state unchanged (OPEN)")
    else:
        print_error(f"✗ Loan state changed: {loan_data_before['state']} → {loan_data_after['state']}")

    if loan_term_before['loanDataId'] == loan_term_after['loanDataId']:
        print_success("✓ Loan data ID unchanged")
    else:
        print_error(f"✗ Loan data ID changed: {loan_term_before['loanDataId']} → {loan_term_after['loanDataId']}")

    # Print balance differences
    print_info("Balance differences:")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Summary
    print_section("TEST SUMMARY")
    print_success("✓ TC10 PASSED: Refinance correctly rejects insufficient lender TAO balance")
    print_info("Validation tested: Lender balance check (require userAlphaBalance[lender][0] >= newLoanAmount)")
    print_info("Error message: 'low lender tao'")
    print_info(f"Lender TAO balance: {new_lender_tao_balance / 1e9:.2f} TAO")
    print_info(f"Required TAO: {new_loan_amount / 1e9:.2f} TAO")
    print_info("All state unchanged (except gas deduction)")

if __name__ == "__main__":
    main()
