#!/usr/bin/env python3
"""
Test Case TC10: Cancel Offer Success
Objective: Verify cancel(Offer) succeeds with valid offer (baseline test)
Tests: All verifyOffer checks pass, cancel operation completes successfully

Strategy: Create valid offer, cancel it successfully, verify state changes
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
    print_section("Test Case TC10: Cancel Offer Success (Baseline)")
    print(f"{CYAN}Objective:{NC} Verify cancel(Offer) succeeds with valid offer")
    print(f"{CYAN}Strategy:{NC} Create valid offer, cancel successfully, verify state changes")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, CancelOffer event emitted\n")

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
            # Check if NOT already cancelled
            offer_id_bytes = bytes.fromhex(candidate_offer['offerId'][2:])
            cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()

            # Check if NOT expired
            if candidate_offer['expire'] > current_timestamp and cancel_block == 0:
                offer_file = file
                offer = candidate_offer
                print_success(f"Found active offer: {offer_file.name}")
                print_info(f"  Offer ID: {offer['offerId'][:10]}...")
                print_info(f"  Max TAO: {offer['maxTaoAmount'] / 1e9} TAO")
                print_info(f"  Alpha Price: {offer['maxAlphaPrice'] / 1e9} TAO")
                print_info(f"  Daily Rate: {offer['dailyInterestRate'] / 10000}%")
                print_info(f"  Netuid: {offer['netuid']}")
                print_info(f"  Expire: {offer['expire']} (current: {current_timestamp})")
                break

    if not offer_file:
        print_warning("No suitable active offer found.")
        print_info("Please run the following command to create a new offer:")
        print_info(f"  {YELLOW}python3 scripts/cli.py create-offer --account LENDER1 --max-tao 100 --alpha-price 0.025 --daily-rate 1.0 --netuid 3 --expire-blocks 10000{NC}")
        print_info("")
        print_info("Then run this test again.")
        sys.exit(1)

    # Step 0: Verify Setup Conditions
    print_section("Step 0: Verify Setup Conditions")

    # Check registration
    lender_registered = contract.functions.registeredUser(lender_address).call()
    if not lender_registered:
        print_error("SETUP ERROR: Lender not registered. Run: python3 scripts/cli.py register --account LENDER1")
        sys.exit(1)

    print_success(f"✓ LENDER1 registered: {lender_address}")

    # Verify offer is not expired
    current_timestamp = w3.eth.get_block('latest')['timestamp']
    if current_timestamp >= offer['expire']:
        print_error(f"SETUP ERROR: Offer has expired!")
        print_error(f"  Current timestamp: {current_timestamp}")
        print_error(f"  Expire timestamp: {offer['expire']}")
        sys.exit(1)

    print_success(f"✓ Offer is NOT expired:")
    print_info(f"  Current timestamp: {current_timestamp}")
    print_info(f"  Expire timestamp: {offer['expire']}")

    # Verify offer is not cancelled
    offer_id_bytes = bytes.fromhex(offer['offerId'][2:])
    cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()
    if cancel_block > 0:
        print_error(f"SETUP ERROR: Offer is already cancelled at block {cancel_block}")
        sys.exit(1)

    print_success(f"✓ Offer is NOT cancelled")

    # Verify nonce matches
    lender_nonce = contract.functions.lenderNonce(lender_address).call()
    if offer['nonce'] != lender_nonce:
        print_error(f"SETUP ERROR: Offer nonce mismatch!")
        print_error(f"  Offer nonce: {offer['nonce']}")
        print_error(f"  Current nonce: {lender_nonce}")
        sys.exit(1)

    print_success(f"✓ Offer nonce matches: {lender_nonce}")

    # Step 1: Read Initial Contract State
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

    # Query specific state
    cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()
    lender_nonce = contract.functions.lenderNonce(lender_address).call()
    print_info(f"canceledOffers[{offer['offerId'][:10]}...] = {cancel_block}")
    print_info(f"lenderNonce[{lender_address}] = {lender_nonce}")

    # Step 2: Read Initial Account Balances
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # Step 3: Read Initial Loan State
    print_section("Step 3: Read Initial Loan State")
    print_info("N/A for cancel operations")

    # Step 4: Execute Test Operation
    print_section("Step 4: Execute cancel(Offer)")

    print(f"\n{BOLD}{GREEN}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds (status=1)")
    print(f"  {BLUE}Event:{NC} CancelOffer(lender, offerId, netuid)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - canceledOffers[offerId] = current_block_number")
    print(f"    - lenderNonce unchanged")
    print(f"    - Lender EVM TAO decreased by gas")
    print(f"    - All other balances unchanged\n")

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

    print_info(f"Cancelling offer {offer['offerId'][:10]}...")

    # Execute transaction
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

    except Exception as e:
        print_error(f"Transaction failed unexpectedly: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

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

    # Verify transaction status
    if tx_receipt['status'] != 1:
        print_error("✗ Transaction reverted unexpectedly!")
        sys.exit(1)

    print_success("✓ Transaction succeeded (status=1)")

    # Verify CancelOffer event
    try:
        cancel_logs = contract.events.CancelOffer().process_receipt(tx_receipt)
        if len(cancel_logs) == 0:
            print_error("✗ No CancelOffer event found")
            sys.exit(1)

        event = cancel_logs[0]['args']
        print_success("✓ CancelOffer event emitted:")
        print_info(f"  lender: {event['lender']}")
        print_info(f"  offerId: {event['offerId'].hex()}")
        print_info(f"  netuid: {event['netuid']}")

        # Verify event fields
        if event['lender'].lower() != lender_address.lower():
            print_error(f"✗ Event lender mismatch: {event['lender']} != {lender_address}")
            sys.exit(1)

        if event['offerId'] != offer_id_bytes:
            print_error(f"✗ Event offerId mismatch")
            sys.exit(1)

        if event['netuid'] != offer['netuid']:
            print_error(f"✗ Event netuid mismatch: {event['netuid']} != {offer['netuid']}")
            sys.exit(1)

        print_success("✓ Event fields verified")

    except Exception as e:
        print_error(f"✗ Failed to parse CancelOffer event: {e}")
        sys.exit(1)

    # Verify state changes
    cancel_block_after = contract.functions.canceledOffers(offer_id_bytes).call()
    lender_nonce_after = contract.functions.lenderNonce(lender_address).call()

    print_info(f"\nState changes:")
    print_info(f"  canceledOffers[{offer['offerId'][:10]}...]: {cancel_block} → {cancel_block_after}")
    print_info(f"  lenderNonce[{lender_address[:10]}...]: {lender_nonce} → {lender_nonce_after}")

    # Verify canceledOffers updated
    if cancel_block_after != tx_receipt['blockNumber']:
        print_error(f"✗ canceledOffers not set correctly!")
        print_error(f"  Expected: {tx_receipt['blockNumber']}")
        print_error(f"  Got: {cancel_block_after}")
        sys.exit(1)

    print_success(f"✓ canceledOffers set to block {cancel_block_after}")

    # Verify lender nonce unchanged
    if lender_nonce_after != lender_nonce:
        print_error(f"✗ lenderNonce changed unexpectedly!")
        print_error(f"  Before: {lender_nonce}")
        print_error(f"  After: {lender_nonce_after}")
        sys.exit(1)

    print_success(f"✓ lenderNonce unchanged ({lender_nonce})")

    # Calculate and print differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify balance changes
    lender_evm_before = snapshot_before['balances']['LENDER1']['evm_tao_wei']
    lender_evm_after = snapshot_after['balances']['LENDER1']['evm_tao_wei']
    gas_used_wei = tx_receipt['gasUsed'] * tx_receipt['effectiveGasPrice']

    print_info(f"\nExpected changes:")
    print_info(f"  Lender EVM TAO: -{gas_used_wei / 1e18:.9f} TAO (gas)")
    print_info(f"  All other balances: No change")

    # Verify lender EVM TAO decreased by gas
    actual_diff = lender_evm_after - lender_evm_before
    if abs(actual_diff + gas_used_wei) < 1e9:  # Within 1 Gwei tolerance
        print_success(f"✓ Lender EVM TAO decreased by gas: {actual_diff / 1e18:.9f} TAO")
    else:
        print_error(f"✗ Lender EVM TAO change unexpected!")
        print_error(f"  Expected: -{gas_used_wei / 1e18:.9f} TAO")
        print_error(f"  Got: {actual_diff / 1e18:.9f} TAO")
        sys.exit(1)

    # Report results
    print_section("Test Result")

    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("Cancel operation completed successfully")
    print_success(f"Offer {offer['offerId'][:10]}... cancelled at block {cancel_block_after}")
    print_success("All state changes verified")
    print_success("All balance changes verified")
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
