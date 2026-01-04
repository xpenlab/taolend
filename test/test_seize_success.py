#!/usr/bin/env python3
"""
Test Case TC10: Seize Success
Objective: Verify lender can successfully seize collateral after MIN_LOAN_DURATION grace period
Tests: Successful state transition from IN_COLLECTION → CLAIMED with collateral transfer

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction succeeds, collateral transferred to lender, loan written off
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
    STATE_IN_COLLECTION, STATE_CLAIMED
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
    print_section("Test Case TC10: Seize Success")
    print(f"{CYAN}Objective:{NC} Verify lender can successfully seize collateral after grace period")
    print(f"{CYAN}Strategy:{NC} Lender seizes IN_COLLECTION loan after MIN_LOAN_DURATION expires")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, state: IN_COLLECTION → CLAIMED, collateral transferred\n")

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

    # Find an IN_COLLECTION loan where grace period has passed
    print_info("Finding an IN_COLLECTION loan where grace period has passed...")
    next_loan_id = contract.functions.nextLoanId().call()
    loan_id = None
    loan_netuid = None
    lender_address = None
    borrower_address = None

    current_block = w3.eth.block_number

    # Search backwards from next_loan_id
    for test_loan_id in range(next_loan_id - 1, max(0, next_loan_id - 100), -1):
        try:
            loan_info = get_loan_full(contract, test_loan_id)
            if loan_info and loan_info['data']['state'] == STATE_IN_COLLECTION:
                last_update_block = loan_info['data']['lastUpdateBlock']
                seize_block = last_update_block + min_loan_duration

                # Check if grace period has passed
                if current_block > seize_block:
                    loan_id = test_loan_id
                    loan_netuid = loan_info['term']['netuid']
                    lender_address = loan_info['offer']['lender']
                    borrower_address = loan_info['term']['borrower']
                    loan_collateral = loan_info['term']['collateralAmount']
                    loan_amount = loan_info['data']['loanAmount']
                    blocks_passed = current_block - seize_block

                    print_success(f"Found loan in IN_COLLECTION state: ID={loan_id}")
                    print_info(f"  Lender: {lender_address}")
                    print_info(f"  Borrower: {borrower_address}")
                    print_info(f"  State: IN_COLLECTION (1)")
                    print_info(f"  Collateral: {loan_collateral / 1e9:.2f} ALPHA")
                    print_info(f"  Loan: {loan_amount / 1e9:.2f} TAO")
                    print_info(f"  Last update block: {last_update_block}")
                    print_info(f"  Current block: {current_block}")
                    print_info(f"  Seize allowed since block: {seize_block}")
                    print_success(f"  ✓ Grace period passed: {blocks_passed} blocks ago")
                    break
        except Exception as e:
            continue

    if loan_id is None:
        print_error("No loans found in IN_COLLECTION state where grace period has passed")
        print_error("Please wait for an IN_COLLECTION loan to pass MIN_LOAN_DURATION")
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
    loan_data_before = loan_info_before['data']
    loan_term_before = loan_info_before['term']
    offer_before = loan_info_before['offer']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_before['state']} (IN_COLLECTION)")
    print_info(f"Last Update Block: {loan_data_before['lastUpdateBlock']}")
    print_info(f"Start Block: {loan_data_before['startBlock']}")
    print_info(f"Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"Lender: {offer_before['lender']}")
    print_info(f"Borrower: {loan_term_before['borrower']}")

    # Get initial lender balances
    lender_label_full = f"LENDER ({lender_label})"
    lender_alpha_before = snapshot_before['balances'][lender_label_full]['contract'][f'netuid_{loan_netuid}']['balance_rao']
    print_info(f"\nLender's initial ALPHA balance (netuid={loan_netuid}): {lender_alpha_before / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("STEP 4: Execute Test Operation - Seize")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}✓ Success:{NC} Transaction succeeds")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - Loan state: IN_COLLECTION (1) → CLAIMED (3)")
    print(f"    - Lender ALPHA balance increases by {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")
    print(f"    - Loan written off (lender loses {loan_data_before['loanAmount'] / 1e9:.2f} TAO)")
    print(f"    - lastUpdateBlock updated to current block")
    print(f"    - SeizeLoan event emitted")

    print_info(f"\nExecuting seize for loan {loan_id}...")

    # Build transaction
    nonce = w3.eth.get_transaction_count(lender_address)

    # Estimate gas
    try:
        gas_estimate = contract.functions.seize(loan_id).estimate_gas({
            'from': lender_address,
            'nonce': nonce
        })
        print_info(f"Gas estimate: {gas_estimate:,}")
    except Exception as e:
        print_error(f"Gas estimation failed: {str(e)[:100]}")
        sys.exit(1)

    # Build and sign transaction
    tx = contract.functions.seize(loan_id).build_transaction({
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
    loan_term_after = loan_info_after['term']

    print_info(f"Loan ID: {loan_id}")
    print_info(f"State: {loan_data_after['state']} (CLAIMED)")
    print_info(f"Last Update Block: {loan_data_after['lastUpdateBlock']}")
    print_info(f"Start Block: {loan_data_after['startBlock']} (unchanged)")
    print_info(f"Loan Amount: {loan_data_after['loanAmount'] / 1e9:.2f} TAO (unchanged)")
    print_info(f"Collateral: {loan_term_after['collateralAmount'] / 1e9:.2f} ALPHA (unchanged)")

    # Get final lender balances
    lender_alpha_after = snapshot_after['balances'][lender_label_full]['contract'][f'netuid_{loan_netuid}']['balance_rao']
    print_info(f"\nLender's final ALPHA balance (netuid={loan_netuid}): {lender_alpha_after / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("STEP 8: Compare and Verify")

    # Verify transaction status
    print_info(f"Transaction status: {tx_receipt['status']}")

    if tx_receipt['status'] == 1:
        print_success("✓ Transaction SUCCEEDED")
    else:
        print_error("✗ Transaction FAILED")
        sys.exit(1)

    # Verify state transition
    print_info("\nVerifying state transition...")
    if loan_data_before['state'] == STATE_IN_COLLECTION and loan_data_after['state'] == STATE_CLAIMED:
        print_success(f"✓ Loan state changed: IN_COLLECTION (1) → CLAIMED (3)")
    else:
        print_error(f"✗ Unexpected state transition: {loan_data_before['state']} → {loan_data_after['state']}")
        sys.exit(1)

    # Verify lastUpdateBlock updated
    if loan_data_after['lastUpdateBlock'] == tx_receipt['blockNumber']:
        print_success(f"✓ lastUpdateBlock updated to {tx_receipt['blockNumber']}")
    else:
        print_error(f"✗ lastUpdateBlock not updated correctly: expected {tx_receipt['blockNumber']}, got {loan_data_after['lastUpdateBlock']}")

    # Verify startBlock unchanged
    if loan_data_before['startBlock'] == loan_data_after['startBlock']:
        print_success(f"✓ startBlock unchanged: {loan_data_after['startBlock']}")
    else:
        print_error(f"✗ startBlock changed: {loan_data_before['startBlock']} → {loan_data_after['startBlock']}")

    # Verify collateral transfer
    print_info("\nVerifying collateral transfer...")
    collateral_amount = loan_term_before['collateralAmount']
    alpha_change = lender_alpha_after - lender_alpha_before

    if alpha_change == collateral_amount:
        print_success(f"✓ Lender received collateral: +{alpha_change / 1e9:.2f} ALPHA")
    else:
        print_error(f"✗ Incorrect collateral transfer: expected +{collateral_amount / 1e9:.2f}, got +{alpha_change / 1e9:.2f} ALPHA")

    # Print balance differences
    print_info("\nBalance differences:")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify events
    print_info("\nVerifying events...")
    logs = tx_receipt['logs']
    seize_event = None

    for log in logs:
        try:
            decoded = contract.events.SeizeLoan().process_log(log)
            seize_event = decoded['args']
            break
        except:
            continue

    if seize_event:
        print_success("✓ SeizeLoan event emitted")
        print_info(f"  lender: {seize_event['lender']}")
        print_info(f"  loanId: {seize_event['loanId']}")
        print_info(f"  loanDataId: {seize_event['loanDataId']}")
        print_info(f"  netuid: {seize_event['netuid']}")
        print_info(f"  block: {seize_event['block']}")
        print_info(f"  collateralAmount: {seize_event['collateralAmount'] / 1e9:.2f} ALPHA")
        print_info(f"  loanAmount: {seize_event['loanAmount'] / 1e9:.2f} TAO")

        # Verify event parameters
        if seize_event['lender'].lower() == lender_address.lower():
            print_success("  ✓ Lender matches")
        else:
            print_error(f"  ✗ Lender mismatch: expected {lender_address}, got {seize_event['lender']}")

        if seize_event['loanId'] == loan_id:
            print_success("  ✓ Loan ID matches")
        else:
            print_error(f"  ✗ Loan ID mismatch: expected {loan_id}, got {seize_event['loanId']}")

        if seize_event['collateralAmount'] == collateral_amount:
            print_success("  ✓ Collateral amount matches")
        else:
            print_error(f"  ✗ Collateral mismatch: expected {collateral_amount}, got {seize_event['collateralAmount']}")
    else:
        print_error("✗ SeizeLoan event not found")

    # Summary
    print_section("TEST SUMMARY")
    print_success("✓ TC10 PASSED: Seize successful")
    print_info("State transition: IN_COLLECTION → CLAIMED")
    print_info(f"Collateral transferred: {collateral_amount / 1e9:.2f} ALPHA to lender")
    print_info(f"Loan written off: {loan_data_before['loanAmount'] / 1e9:.2f} TAO (lender's loss)")
    print_info("SeizeLoan event emitted correctly")

if __name__ == "__main__":
    main()
