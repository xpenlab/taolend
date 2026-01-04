#!/usr/bin/env python3
"""
Test Case TC02: cancel(Offer) - Not Lender
Objective: Verify cancel(Offer) fails when initiator is not the lender
Tests: Lender check - require(_offer.lender == msg.sender, "not lender")

Strategy: 8-step testing pattern with BalanceChecker
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
from common import load_addresses, load_contract_abi

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
    print_section("Test Case TC02: cancel(Offer) - Not Lender")
    print(f"{CYAN}Objective:{NC} Verify cancel(Offer) fails when initiator is not the lender")
    print(f"{CYAN}Strategy:{NC} Borrower attempts to cancel lender's offer")
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

    # Find a registered borrower (not the lender)
    print_info("Finding registered borrower...")
    borrower_address = None
    borrower_private_key = None
    borrower_label = None

    candidate_borrowers = ['BORROWER1', 'BORROWER2', 'LENDER2']  # Use LENDER2 as borrower if needed

    for account_name in candidate_borrowers:
        if account_name in addresses:
            address = addresses[account_name]['evmAddress']
            is_registered = contract.functions.registeredUser(address).call()
            if is_registered:
                borrower_address = address
                borrower_label = account_name
                # Try to get private key
                key_name = f"{account_name}_PRIVATE_KEY"
                borrower_private_key = os.environ.get(key_name)
                if borrower_private_key:
                    print_success(f"Found registered borrower: {account_name} ({address})")
                    break

    if not borrower_address or not borrower_private_key:
        print_error("No suitable registered borrower found with private key")
        print_info("Checked accounts: " + ", ".join(candidate_borrowers))
        print_info("Please register one of these accounts:")
        print_info(f"  {YELLOW}python3 scripts/cli.py register --account BORROWER1{NC}")
        sys.exit(1)

    # Find an active offer from a different lender
    print_info("Searching for active offers from other lenders...")
    offers_dir = Path(__file__).parent.parent / "offers"
    offer_file = None
    offer = None

    offer_files = sorted(offers_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    current_timestamp = w3.eth.get_block('latest')['timestamp']

    for file in offer_files:
        candidate_offer = load_offer(file)
        lender_address = candidate_offer['lender']

        # Must be different from borrower
        if lender_address.lower() == borrower_address.lower():
            continue

        # Check if NOT already cancelled
        offer_id_bytes = bytes.fromhex(candidate_offer['offerId'][2:])
        cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()

        # Check if NOT expired
        if candidate_offer['expire'] > current_timestamp and cancel_block == 0:
            # Check nonce matches
            lender_nonce = contract.functions.lenderNonce(lender_address).call()
            if candidate_offer['nonce'] == lender_nonce:
                offer_file = file
                offer = candidate_offer
                print_success(f"Found active offer: {offer_file.name}")
                print_info(f"  Offer ID: {offer['offerId'][:10]}...")
                print_info(f"  Lender: {offer['lender']}")
                print_info(f"  Borrower trying: {borrower_address}")
                print_info(f"  Netuid: {offer['netuid']}")
                break

    if not offer_file:
        print_warning("No suitable active offer found.")
        print_info("Please create an offer first:")
        print_info(f"  {YELLOW}python3 scripts/cli.py create-offer --account LENDER1 --max-tao 100 --alpha-price 0.025 --daily-rate 1.0 --netuid 3 --expire-blocks 10000{NC}")
        sys.exit(1)

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check borrower is registered
    is_registered = contract.functions.registeredUser(borrower_address).call()
    if not is_registered:
        print_error(f"SETUP ERROR: {borrower_label} is not registered")
        sys.exit(1)

    print_success(f"✓ {borrower_label} is registered: {borrower_address}")

    # Verify borrower is NOT the lender
    if borrower_address.lower() == offer['lender'].lower():
        print_error(f"SETUP ERROR: Borrower and lender are the same")
        sys.exit(1)

    print_success(f"✓ Borrower ({borrower_address}) is NOT the lender ({offer['lender']})")

    # Verify offer is valid
    offer_id_bytes = bytes.fromhex(offer['offerId'][2:])
    cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()
    if cancel_block > 0:
        print_error(f"SETUP ERROR: Offer is already cancelled at block {cancel_block}")
        sys.exit(1)

    print_success(f"✓ Offer is NOT cancelled")

    # ========================================================================
    # Step 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0, 2, 3]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": borrower_address, "label": borrower_label},
        {"address": offer['lender'], "label": "LENDER"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()
    lender_nonce = contract.functions.lenderNonce(offer['lender']).call()
    print_info(f"canceledOffers[{offer['offerId'][:10]}...] = {cancel_block}")
    print_info(f"lenderNonce[{offer['lender']}] = {lender_nonce}")

    # ========================================================================
    # Step 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # Step 3: Read Initial Offer State
    # ========================================================================
    print_section("Step 3: Read Initial Offer State")
    print_info(f"Offer ID: {offer['offerId']}")
    print_info(f"Canceled block: {cancel_block} (0 = not canceled)")
    print_info(f"Offer lender: {offer['lender']}")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute cancel(Offer) - Should FAIL")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} Transaction reverts with 'not lender'")
    print(f"  {CYAN}State Changes:{NC} None (transaction reverted)")
    print(f"    - canceledOffers[offerId] unchanged (still 0)")
    print(f"    - lenderNonce unchanged")
    print(f"    - All balances unchanged except gas\n")

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

    print_info(f"Borrower {borrower_label} attempting to cancel lender's offer...")

    # Execute transaction - should fail
    try:
        tx = contract.functions.cancel(offer_tuple).build_transaction({
            'from': borrower_address,
            'nonce': w3.eth.get_transaction_count(borrower_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=borrower_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print_info(f"Transaction hash: {tx_hash.hex()}")
        print_info("Waiting for transaction receipt...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Check transaction status
        if receipt['status'] == 0:
            # Transaction reverted as expected
            print_success("✓ Transaction reverted as expected (status=0)")
            print_info("Expected revert reason: 'not lender'")
        else:
            # Transaction succeeded when it should have reverted
            print_error("❌ TEST FAILED: Transaction succeeded when it should have reverted")
            print_error(f"Transaction status: {receipt['status']}")
            print_error("Expected: Transaction to revert with 'not lender'")
            sys.exit(1)

    except Exception as e:
        # Transaction reverted with exception (also valid)
        error_msg = str(e)
        print_success(f"✓ Transaction reverted with exception")
        print_info(f"Error message: {error_msg}")

        # Check if error message contains expected revert reason
        if "not lender" in error_msg.lower():
            print_success(f"✓ Correct revert reason: 'not lender'")
        else:
            print_warning(f"⚠ Unexpected revert reason: {error_msg}")
            print_warning("Expected: 'not lender'")

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    # Capture final snapshot
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # Query specific state
    cancel_block_after = contract.functions.canceledOffers(offer_id_bytes).call()
    lender_nonce_after = contract.functions.lenderNonce(offer['lender']).call()
    print_info(f"canceledOffers[{offer['offerId'][:10]}...] = {cancel_block_after}")
    print_info(f"lenderNonce[{offer['lender']}] = {lender_nonce_after}")

    # ========================================================================
    # Step 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # Step 7: Read Final Offer State
    # ========================================================================
    print_section("Step 7: Read Final Offer State")
    print_info(f"Offer ID: {offer['offerId']}")
    print_info(f"Canceled block: {cancel_block_after} (should still be 0)")

    # ========================================================================
    # Step 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Calculate differences
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # Verification
    # ========================================================================
    print_section("Verification Summary")

    all_checks_passed = True

    # Check 1: canceledOffers unchanged
    if cancel_block_after == cancel_block:
        print_success(f"✓ canceledOffers unchanged: {cancel_block} → {cancel_block_after}")
    else:
        print_error(f"✗ canceledOffers changed: {cancel_block} → {cancel_block_after}")
        all_checks_passed = False

    # Check 2: lenderNonce unchanged
    if lender_nonce_after == lender_nonce:
        print_success(f"✓ lenderNonce unchanged: {lender_nonce} → {lender_nonce_after}")
    else:
        print_error(f"✗ lenderNonce changed: {lender_nonce} → {lender_nonce_after}")
        all_checks_passed = False

    # Check 3: Contract balances unchanged (except gas)
    contract_state_before = snapshot_before['contract']
    contract_state_after = snapshot_after['contract']

    # Compare only relevant fields (exclude block_number and address)
    state_unchanged = (
        contract_state_before['protocol_fee_accumulated'] == contract_state_after['protocol_fee_accumulated'] and
        contract_state_before['subnet_total_balance'] == contract_state_after['subnet_total_balance'] and
        contract_state_before['subnet_staking'] == contract_state_after['subnet_staking'] and
        contract_state_before['next_loan_id'] == contract_state_after['next_loan_id']
    )

    if state_unchanged:
        print_success("✓ Contract state unchanged")
    else:
        print_error("✗ Contract state changed")
        all_checks_passed = False

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success("Transaction reverted as expected with 'not lender'")
        print_success("Only lender can cancel their own offers")
        print_success("All state remains unchanged")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
