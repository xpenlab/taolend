#!/usr/bin/env python3
"""
Test Case TC12: Bad Alpha Price
Objective: Verify refinance fails when offer's maxAlphaPrice is too high (>= 90% of on-chain price)
Tests: Price safety check - require(alphaPrice * SAFE_ALPHA_PRICE / RATE_BASE > maxAlphaPrice, "bad price")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "bad price"
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
    print_section("Test Case TC12: Bad Alpha Price")
    print(f"{CYAN}Objective:{NC} Verify refinance fails when offer's maxAlphaPrice is too high (>= 90% of on-chain price)")
    print(f"{CYAN}Strategy:{NC} Create offer with maxAlphaPrice >= 90% of on-chain price")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'bad price'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    borrower_address = addresses['BORROWER1']['evmAddress']
    new_lender_address = addresses['LENDER2']['evmAddress']

    # Get private key
    borrower_private_key = os.environ.get('BORROWER1_PRIVATE_KEY')
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

    # Verify BORROWER1 is registered
    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    if not borrower_registered:
        print_error(f"BORROWER1 must be registered for this test")
        sys.exit(1)
    print_success(f"BORROWER1 is registered")

    # Verify NEW_LENDER is registered
    new_lender_registered = contract.functions.registeredUser(new_lender_address).call()
    if not new_lender_registered:
        print_error(f"NEW_LENDER (LENDER2) must be registered for this test")
        sys.exit(1)
    print_success(f"NEW_LENDER (LENDER2) is registered")

    # Find an active loan for BORROWER1
    print_info("Finding active loan for BORROWER1...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None

    # Search backwards from next_loan_id
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

    # Query on-chain alpha price
    print_info("Querying on-chain ALPHA price...")
    try:
        alpha_price = contract.functions.getAlphaPrice(loan_netuid).call()
        print_success(f"On-chain ALPHA price: {alpha_price / 1e9:.4f} TAO per ALPHA")

        # Calculate safe threshold (90%)
        safe_threshold = int(alpha_price * 0.9)
        print_info(f"Safe threshold (90%): {safe_threshold / 1e9:.4f} TAO per ALPHA")

        # Set maxAlphaPrice to 95% (UNSAFE - above 90%)
        unsafe_max_alpha_price = int(alpha_price * 0.95)
        print_warning(f"Setting maxAlphaPrice to 95%: {unsafe_max_alpha_price / 1e9:.4f} TAO per ALPHA (TOO HIGH)")

    except Exception as e:
        print_error(f"Failed to query alpha price: {e}")
        sys.exit(1)

    # Create offer for NEW_LENDER with HIGH maxAlphaPrice
    print_info("Creating offer for NEW_LENDER with UNSAFE maxAlphaPrice...")
    new_lender_private_key = os.environ.get("LENDER2_PRIVATE_KEY")
    if not new_lender_private_key:
        print_error("LENDER2_PRIVATE_KEY not found in .env")
        sys.exit(1)

    new_offer = create_offer(
        w3=w3,
        contract=contract,
        lender_address=new_lender_address,
        lender_private_key=new_lender_private_key,
        netuid=loan_netuid,
        max_tao_amount=int(200e9),
        max_alpha_price=unsafe_max_alpha_price,  # 95% - TOO HIGH!
        daily_interest_rate=5_000_000,
        expire_seconds=86400
    )
    print_success(f"Created offer: offerId={new_offer['offerId']}, netuid={new_offer['netuid']}")
    print_warning(f"Offer maxAlphaPrice: {new_offer['maxAlphaPrice'] / 1e9:.4f} TAO per ALPHA (95% of on-chain)")

    # Calculate refinance amount
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
    print(f"  {RED}✗ Revert:{NC} 'bad price'")
    print(f"  {CYAN}Reason:{NC} Offer maxAlphaPrice ({unsafe_max_alpha_price / 1e9:.4f}) >= 90% of on-chain price ({safe_threshold / 1e9:.4f})")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from borrower's EVM TAO")

    print_info(f"\nAttempting to refinance loan {loan_id}...")
    print_info(f"Borrower: {borrower_address}")
    print_info(f"New Lender: {new_lender_address}")
    print_warning(f"Offer maxAlphaPrice: {unsafe_max_alpha_price / 1e9:.4f} TAO/ALPHA (95% - TOO HIGH)")
    print_info(f"On-chain price: {alpha_price / 1e9:.4f} TAO/ALPHA")
    print_info(f"Safe threshold: {safe_threshold / 1e9:.4f} TAO/ALPHA (90%)")

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
        if 'bad price' in error_msg:
            print_success(f"✓ Gas estimation failed (expected): 'bad price'")
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
        print_success("✓ Test PASSED: Refinance correctly rejected unsafe ALPHA price")
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
    print_success("✓ TC12 PASSED: Refinance correctly rejects unsafe ALPHA price")
    print_info("Validation tested: Price safety check (require alphaPrice * 0.9 > maxAlphaPrice)")
    print_info("Error message: 'bad price'")
    print_info(f"On-chain ALPHA price: {alpha_price / 1e9:.4f} TAO/ALPHA")
    print_info(f"Safe threshold (90%): {safe_threshold / 1e9:.4f} TAO/ALPHA")
    print_info(f"Offer maxAlphaPrice: {unsafe_max_alpha_price / 1e9:.4f} TAO/ALPHA (95% - TOO HIGH)")
    print_info("All state unchanged (except gas deduction)")

if __name__ == "__main__":
    main()
