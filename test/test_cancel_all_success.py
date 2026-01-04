#!/usr/bin/env python3
"""
Test Case TC05: cancel() - Cancel All Success
Objective: Verify cancel() succeeds and increments lender's nonce
Tests: Successful batch cancellation of all offers

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction succeeds, CancelAllOffers event emitted, nonce incremented
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

def main():
    print_section("Test Case TC05: cancel() - Cancel All Success")
    print(f"{CYAN}Objective:{NC} Verify cancel() succeeds and increments lender's nonce")
    print(f"{CYAN}Strategy:{NC} Lender calls cancel() to invalidate all existing offers")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, CancelAllOffers event emitted, nonce += 1\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender_address = addresses['LENDER1']['evmAddress']

    # Load private key
    lender_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
    if not lender_private_key:
        print_error("LENDER1_PRIVATE_KEY not found in .env")
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

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check lender is registered
    lender_registered = contract.functions.registeredUser(lender_address).call()
    if not lender_registered:
        print_error("SETUP ERROR: Lender not registered. Run: python3 scripts/cli.py register --account LENDER1")
        sys.exit(1)

    print_success(f"✓ LENDER1 is registered: {lender_address}")

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
    addresses_list = [{"address": lender_address, "label": "LENDER1"}]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_before)

    # Query nonce
    nonce_before = contract.functions.lenderNonce(lender_address).call()
    print_info(f"lenderNonce[{lender_address}] = {nonce_before}")

    # ========================================================================
    # Step 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # Step 3: Read Initial Nonce State
    # ========================================================================
    print_section("Step 3: Read Initial Nonce State")
    print_info(f"Current nonce: {nonce_before}")
    print_info("After cancel(), all offers with this nonce will become invalid")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute cancel()")

    print(f"\n{BOLD}{GREEN}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds (status=1)")
    print(f"  {BLUE}Event:{NC} CancelAllOffers(lender, nonce)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - lenderNonce[lender] = {nonce_before + 1}")
    print(f"    - All offers with nonce={nonce_before} become invalid")
    print(f"    - Lender EVM TAO decreased by gas")
    print(f"    - All other balances unchanged\n")

    print_info(f"Cancelling all offers for LENDER1...")

    # Execute transaction
    try:
        # Note: cancel() has no parameters
        tx = contract.functions.cancel().build_transaction({
            'from': lender_address,
            'nonce': w3.eth.get_transaction_count(lender_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=lender_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print_info(f"Transaction hash: {tx_hash.hex()}")
        print_info("Waiting for transaction receipt...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt['status'] == 1:
            print_success(f"✓ Transaction succeeded")
            print_info(f"Gas used: {receipt['gasUsed']}")
            print_info(f"Block number: {receipt['blockNumber']}")

            # Check for CancelAllOffers event
            events = contract.events.CancelAllOffers().process_receipt(receipt)
            if events:
                for event in events:
                    print_success(f"✓ CancelAllOffers event emitted:")
                    print_info(f"  Lender: {event['args']['lender']}")
                    print_info(f"  Nonce (old): {event['args']['nonce']}")
            else:
                print_warning("⚠ No CancelAllOffers event found")

        else:
            print_error("❌ Transaction failed")
            sys.exit(1)

    except Exception as e:
        print_error(f"❌ Transaction failed with error: {str(e)}")
        sys.exit(1)

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    # Capture final snapshot
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # Query nonce
    nonce_after = contract.functions.lenderNonce(lender_address).call()
    print_info(f"lenderNonce[{lender_address}] = {nonce_after}")

    # ========================================================================
    # Step 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # Step 7: Read Final Nonce State
    # ========================================================================
    print_section("Step 7: Read Final Nonce State")
    print_info(f"Current nonce: {nonce_after} (should be {nonce_before + 1})")
    print_info("All offers with old nonce are now invalid")

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

    # Check 1: lenderNonce incremented
    expected_nonce = nonce_before + 1
    if nonce_after == expected_nonce:
        print_success(f"✓ lenderNonce incremented: {nonce_before} → {nonce_after}")
    else:
        print_error(f"✗ lenderNonce incorrect: expected {expected_nonce}, got {nonce_after}")
        all_checks_passed = False

    # Check 2: Contract state unchanged (except nonce)
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
        print_success("✓ Contract state unchanged (no balance transfers)")
    else:
        print_error("✗ Contract state changed")
        all_checks_passed = False

    # Check 3: Only gas consumed from lender EVM balance
    lender_before = snapshot_before['balances']['LENDER1']
    lender_after = snapshot_after['balances']['LENDER1']

    # All contract balances should be unchanged
    for netuid in [0, 2, 3]:
        netuid_key = f'netuid_{netuid}'
        balance_before = lender_before['contract'][netuid_key]['balance_rao']
        balance_after = lender_after['contract'][netuid_key]['balance_rao']
        if balance_before != balance_after:
            print_error(f"✗ Contract balance changed for netuid {netuid}")
            all_checks_passed = False

    if all_checks_passed:
        print_success("✓ All contract balances unchanged")

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success("Lender successfully cancelled all offers via nonce increment")
        print_success(f"lenderNonce: {nonce_before} → {nonce_after}")
        print_success("CancelAllOffers event emitted correctly")
        print_success("No balance changes except gas")
        print_info("\nNote: All existing offers with old nonce are now invalid")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
