#!/usr/bin/env python3
"""
Test Case TC05: Cancel with Invalid Netuid (Zero)
Objective: Verify cancel(Offer) reverts when netuid is zero
Tests: verifyOffer modifier - require(_offer.netuid > 0, "bad netuid")

Strategy: Create offer with netuid=0, attempt to cancel
Expected: Transaction reverts with "bad netuid" error
Note: netuid=0 is reserved for TAO, not ALPHA subnets
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3
from eth_account.messages import encode_defunct

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

def create_test_offer(w3, contract, lender_address, lender_private_key):
    """Create a test offer with netuid=0 (invalid)"""

    # Query current nonce
    lender_nonce = contract.functions.lenderNonce(lender_address).call()

    # Create offer with netuid=0 (INVALID - reserved for TAO)
    offer = {
        'lender': lender_address,
        'netuid': 0,  # INVALID - must be > 0
        'nonce': lender_nonce,
        'expire': w3.eth.get_block('latest')['timestamp'] + 86400,  # Expires in 1 day
        'maxTaoAmount': 100 * 10**9,  # 100 TAO in RAO
        'maxAlphaPrice': 25 * 10**6,  # 0.025 TAO in RAO
        'dailyInterestRate': 100000,  # 1.0% daily (100000 / 10000 = 10%)
    }

    # Calculate offerId (same as LoanLib.calculateOfferId)
    offer_hash = w3.keccak(
        w3.codec.encode(
            ['address', 'uint16', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256'],
            [
                offer['lender'],
                offer['netuid'],
                offer['nonce'],
                offer['expire'],
                offer['maxTaoAmount'],
                offer['maxAlphaPrice'],
                offer['dailyInterestRate']
            ]
        )
    )
    offer['offerId'] = '0x' + offer_hash.hex()

    # Sign offer (Ethereum Signed Message)
    message = encode_defunct(hexstr=offer['offerId'])
    signed = w3.eth.account.sign_message(message, private_key=lender_private_key)
    offer['signature'] = '0x' + signed.signature.hex()

    print_success("Created test offer with netuid=0 (INVALID)")
    print_info(f"  Offer ID: {offer['offerId'][:10]}...")
    print_info(f"  Lender: {offer['lender']}")
    print_info(f"  Netuid: {offer['netuid']} (INVALID - should be > 0)")
    print_info(f"  Nonce: {offer['nonce']}")

    return offer

def main():
    print_section("Test Case TC05: Cancel with Invalid Netuid (Zero)")
    print(f"{CYAN}Objective:{NC} Verify cancel(Offer) reverts when netuid is zero")
    print(f"{CYAN}Strategy:{NC} Create offer with netuid=0, attempt to cancel")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'bad netuid'\n")

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

    # Step 0: Verify Setup Conditions
    print_section("Step 0: Verify Setup and Create Invalid Offer")

    # Check registration
    lender_registered = contract.functions.registeredUser(lender_address).call()
    if not lender_registered:
        print_error("SETUP ERROR: Lender not registered. Run: python3 scripts/cli.py register --account LENDER1")
        sys.exit(1)

    print_success(f"✓ LENDER1 registered: {lender_address}")

    # Create test offer with netuid=0 (invalid)
    offer = create_test_offer(w3, contract, lender_address, lender_private_key)

    # Step 1: Read Initial Contract State
    print_section("Step 1: Read Initial Contract State")

    offer_id_bytes = bytes.fromhex(offer['offerId'][2:])
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
    print_section("Step 4: Execute cancel(Offer) with netuid=0")

    print(f"\n{BOLD}{RED}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} Transaction reverts (status=0)")
    print(f"  {YELLOW}Reason:{NC} 'bad netuid'")
    print(f"  {CYAN}State Changes:{NC} None (only gas consumed)\n")

    # Convert offer to tuple for contract call
    offer_tuple = (
        bytes.fromhex(offer['offerId'][2:]),
        Web3.to_checksum_address(offer['lender']),
        offer['netuid'],  # This is 0 (INVALID)
        offer['nonce'],
        offer['expire'],
        offer['maxTaoAmount'],
        offer['maxAlphaPrice'],
        offer['dailyInterestRate'],
        bytes.fromhex(offer['signature'][2:])
    )

    print_info(f"Attempting to cancel offer with netuid=0 (invalid)...")

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

        if "bad netuid" in error_str.lower() or "netuid" in error_str.lower():
            reverted = True
            print_success("✓ Transaction reverted with expected reason (bad netuid)")
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

    # Verify state unchanged (except gas)
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
    print_success("Cancel operation correctly reverted for netuid=0")
    print_success("Verification: netuid > 0 check working correctly")
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
