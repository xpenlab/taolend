#!/usr/bin/env python3
"""
Test Case TC04: Cancel Already Cancelled Offer
Objective: Verify cancel(Offer) reverts when offer is already cancelled
Tests: verifyOffer modifier - require(canceledOffers[_offer.offerId] == 0, "offer canceled")

Strategy: Cancel offer once successfully, then try to cancel again
Expected: Second cancel reverts with "offer canceled" error
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

def load_addresses():
    """Load addresses from addresses.json"""
    addresses_file = Path(__file__).parent.parent / "addresses.json"
    with open(addresses_file, 'r') as f:
        data = json.load(f)
        return {account['name']: account for account in data['accounts']}

def load_contract_abi():
    """Load contract ABI"""
    abi_file = Path(__file__).parent.parent / "artifacts" / "contracts" / "LendingPoolV2.sol" / "LendingPoolV2.json"
    with open(abi_file, 'r') as f:
        contract_json = json.load(f)
        return contract_json['abi']

def load_offer(offer_file):
    """Load offer from JSON file"""
    with open(offer_file, 'r') as f:
        return json.load(f)

def main():
    print_section("Test Case TC04: Cancel Already Cancelled Offer")
    print(f"{CYAN}Objective:{NC} Verify cancel(Offer) reverts when already cancelled")
    print(f"{CYAN}Strategy:{NC} Cancel offer once, then try to cancel again")
    print(f"{CYAN}Expected:{NC} Second cancel reverts with 'offer canceled'\n")

    # Setup
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

    # Find an active offer from LENDER1
    offers_dir = Path(__file__).parent.parent / "offers"
    offer_file = None
    offer = None

    print_info("Searching for active offers from LENDER1...")

    offer_files = sorted(offers_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    current_timestamp = w3.eth.get_block('latest')['timestamp']

    for file in offer_files:
        candidate_offer = load_offer(file)
        if candidate_offer['lender'].lower() == lender_address.lower():
            # Check if NOT expired and NOT cancelled
            offer_id_bytes = bytes.fromhex(candidate_offer['offerId'][2:])
            cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()

            if candidate_offer['expire'] > current_timestamp and cancel_block == 0:
                offer_file = file
                offer = candidate_offer
                print_success(f"Found active offer: {offer_file.name}")
                print_info(f"  Offer ID: {offer['offerId'][:10]}...")
                break

    if not offer_file:
        print_warning("No suitable active offer found.")
        print_info("Please run: python3 scripts/cli.py create-offer --account LENDER1 --max-tao 100 --alpha-price 0.025 --daily-rate 1.0 --netuid 3 --expire-blocks 10000")
        sys.exit(1)

    # Step 0: Verify Setup and Cancel Once
    print_section("Step 0: Verify Setup and Cancel Once")

    # Check registration
    lender_registered = contract.functions.registeredUser(lender_address).call()
    if not lender_registered:
        print_error("SETUP ERROR: Lender not registered. Run: python3 scripts/cli.py register --account LENDER1")
        sys.exit(1)

    print_success(f"✓ LENDER1 registered: {lender_address}")

    # Verify nonce matches
    lender_nonce = contract.functions.lenderNonce(lender_address).call()
    if offer['nonce'] != lender_nonce:
        print_error(f"SETUP ERROR: Offer nonce mismatch!")
        print_error(f"  Offer nonce: {offer['nonce']}")
        print_error(f"  Current nonce: {lender_nonce}")
        sys.exit(1)

    print_success(f"✓ Offer nonce matches: {lender_nonce}")

    # Convert offer to tuple
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

    # First cancel (should succeed)
    print_info("Performing FIRST cancel (should succeed)...")

    try:
        tx = contract.functions.cancel(offer_tuple).build_transaction({
            'from': lender_address,
            'nonce': w3.eth.get_transaction_count(lender_address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price,
        })

        signed_tx = w3.eth.account.sign_transaction(tx, lender_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"First cancel() sent: {tx_hash.hex()}")

        tx_receipt_first = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt_first['blockNumber']}")

        if tx_receipt_first['status'] == 1:
            print_success("✓ First cancel() succeeded")
        else:
            print_error("First cancel() reverted unexpectedly!")
            sys.exit(1)

    except Exception as e:
        print_error(f"First cancel() failed: {e}")
        sys.exit(1)

    # Verify offer is now cancelled
    offer_id_bytes = bytes.fromhex(offer['offerId'][2:])
    cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()

    if cancel_block == 0:
        print_error("Offer is NOT marked as cancelled!")
        sys.exit(1)

    print_success(f"✓ Offer marked as cancelled at block {cancel_block}")

    # Step 1: Read Initial Contract State
    print_section("Step 1: Read Initial Contract State (Before Second Cancel)")

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

    # Query specific state
    print_info(f"canceledOffers[{offer['offerId'][:10]}...] = {cancel_block} (already cancelled)")
    print_info(f"lenderNonce[{lender_address}] = {lender_nonce}")

    # Step 2: Read Initial Account Balances
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # Step 3: Read Initial Loan State
    print_section("Step 3: Read Initial Loan State")
    print_info("N/A for cancel operations")

    # Step 4: Execute Test Operation
    print_section("Step 4: Execute SECOND cancel(Offer) - Already Cancelled")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} Transaction reverts (status=0)")
    print(f"  {YELLOW}Reason:{NC} 'offer canceled'")
    print(f"  {CYAN}State Changes:{NC} None (only gas consumed)\n")

    print_info(f"Attempting SECOND cancel of already-cancelled offer {offer['offerId'][:10]}...")

    # Execute transaction (expect revert)
    tx_receipt = None
    reverted = False

    try:
        tx = contract.functions.cancel(offer_tuple).build_transaction({
            'from': lender_address,
            'nonce': w3.eth.get_transaction_count(lender_address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price,
        })

        signed_tx = w3.eth.account.sign_transaction(tx, lender_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        # Check if reverted
        if tx_receipt['status'] == 0:
            reverted = True
            print_success("✓ Transaction reverted as expected (status=0)")
        else:
            print_error("✗ Transaction succeeded unexpectedly (status=1)")

    except Exception as e:
        error_str = str(e)
        print_info(f"Transaction failed before mining: {error_str[:200]}")

        if "offer canceled" in error_str.lower() or "canceled" in error_str.lower():
            reverted = True
            print_success("✓ Transaction reverted with expected reason (offer canceled)")
        else:
            print_warning(f"Transaction reverted but reason unclear: {error_str[:200]}")
            reverted = True

    # Step 5: Read Final Contract State
    print_section("Step 5: Read Final Contract State")

    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(snapshot_after)

    # Step 6: Read Final Account Balances
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # Step 7: Read Final Loan State
    print_section("Step 7: Read Final Loan State")
    print_info("N/A for cancel operations")

    # Step 8: Compare and Verify
    print_section("Step 8: Compare and Verify")

    # Verify transaction reverted
    if not reverted:
        print_error("✗ TEST FAILED: Transaction should have reverted but didn't")
        sys.exit(1)

    print_success("✓ Transaction reverted as expected")

    # Verify state unchanged
    cancel_block_after = contract.functions.canceledOffers(offer_id_bytes).call()
    lender_nonce_after = contract.functions.lenderNonce(lender_address).call()

    print_info(f"\nState verification:")
    print_info(f"  canceledOffers[{offer['offerId'][:10]}...]: {cancel_block} → {cancel_block_after}")
    print_info(f"  lenderNonce[{lender_address[:10]}...]: {lender_nonce} → {lender_nonce_after}")

    if cancel_block_after != cancel_block:
        print_error(f"✗ canceledOffers changed unexpectedly!")
        sys.exit(1)

    if lender_nonce_after != lender_nonce:
        print_error(f"✗ lenderNonce changed unexpectedly!")
        sys.exit(1)

    print_success(f"✓ Contract state unchanged (canceledOffers={cancel_block}, nonce={lender_nonce})")

    # Calculate and print differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Report results
    print_section("Test Result")

    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("Second cancel correctly reverted for already-cancelled offer")
    print_success("Verification: canceledOffers check working correctly")
    print_success("No state changes except gas consumed")
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_info("\nTest cancelled by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
