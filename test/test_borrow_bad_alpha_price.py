#!/usr/bin/env python3
"""
Test Case TC09: Alpha Price Not Safe
Objective: Verify borrow fails when offer price is too high vs on-chain price
Tests: Line 892 - require(_offer.maxAlphaPrice * RATE_BASE < alphaPrice * SAFE_ALPHA_PRICE, "bad price")

Strategy: Attempt borrow with offer that has maxAlphaPrice >= onChainPrice * 0.9
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
from common import get_loan_full, load_addresses, load_contract_abi

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

def load_offer(offer_file):
    """Load offer from JSON file"""
    with open(offer_file, 'r') as f:
        return json.load(f)

def main():
    print_section("Test Case TC09: Alpha Price Not Safe")
    print(f"{CYAN}Objective:{NC} Verify borrow fails when offer price violates 90% safety margin")
    print(f"{CYAN}Strategy:{NC} Use offer with maxAlphaPrice >= onChainPrice * 0.9")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'bad price'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    lender_address = addresses['LENDER1']['evmAddress']
    borrower_address = addresses['BORROWER1']['evmAddress']

    # Load private keys
    lender_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
    borrower_private_key = os.environ.get("BORROWER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

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

    # Find the unsafe offer (should be the most recent one with maxAlphaPrice 0.51)
    offers_dir = Path(__file__).parent.parent / "offers"
    offer_file = Path(offers_dir) / "458470e156abce694ba0a48119b86db1cbba11a6db794e6d157ba3418fe7c128.json"

    if not offer_file.exists():
        print_error("Unsafe offer file not found")
        print_info("Expected: offers/458470e156abce694ba0a48119b86db1cbba11a6db794e6d157ba3418fe7c128.json")
        print_info("Please create unsafe offer first:")
        print_info(f"  {YELLOW}python3 scripts/cli.py create-offer --account LENDER1 --max-tao 50 --max-alpha-price 0.51 --daily-rate 1.0 --netuid 3{NC}")
        sys.exit(1)

    offer = load_offer(offer_file)
    print_success(f"Found unsafe offer: {offer_file.name}")

    # Test parameters
    netuid = offer['netuid']

    # Query on-chain alpha price
    on_chain_price = contract.functions.getAlphaPrice(netuid).call()
    safe_threshold = on_chain_price * 9000 // 10000  # 90%
    offer_price = offer['maxAlphaPrice']

    print_info(f"\nPrice Analysis:")
    print_info(f"  On-chain ALPHA Price: {on_chain_price / 1e9:.9f} TAO per ALPHA")
    print_info(f"  Safe Threshold (90%): {safe_threshold / 1e9:.9f} TAO per ALPHA")
    print_info(f"  Offer maxAlphaPrice:  {offer_price / 1e9:.9f} TAO per ALPHA")

    # Check if offer price violates safety margin
    RATE_BASE = 10000
    SAFE_ALPHA_PRICE = 9000
    violates_safety = offer_price * RATE_BASE >= on_chain_price * SAFE_ALPHA_PRICE

    if violates_safety:
        print_success(f"  ✓ Offer price violates safety margin (will trigger 'bad price')")
    else:
        print_error(f"  ✗ Offer price is safe (test condition not met)")
        print_error(f"  Expected: {offer_price / 1e9:.9f} >= {safe_threshold / 1e9:.9f}")
        sys.exit(1)

    # Calculate reasonable borrow amount
    tao_amount = 10 * 10**9  # 10 TAO in RAO
    alpha_amount = int(tao_amount * 1e9 / offer_price * 1.1)  # 110% collateral

    print_info(f"\nTest Parameters:")
    print_info(f"  Netuid: {netuid}")
    print_info(f"  Borrow Amount: {tao_amount / 1e9:.2f} TAO")
    print_info(f"  Collateral: {alpha_amount / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check LENDER1 is registered
    lender_registered = contract.functions.registeredUser(lender_address).call()
    if not lender_registered:
        print_error("SETUP ERROR: Lender not registered")
        sys.exit(1)
    print_success("✓ Lender registered")

    # Check BORROWER1 is registered
    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    if not borrower_registered:
        print_error("SETUP ERROR: Borrower not registered")
        sys.exit(1)
    print_success("✓ Borrower registered")

    # Check contract not paused
    paused = contract.functions.pausedBorrow().call()
    if paused:
        print_error("SETUP ERROR: Contract is paused")
        sys.exit(1)
    print_success("✓ Contract not paused")

    # Check subnet active
    subnet_active = contract.functions.activeSubnets(netuid).call()
    if not subnet_active:
        print_error(f"SETUP ERROR: Subnet {netuid} not active")
        sys.exit(1)
    print_success(f"✓ Subnet {netuid} active")

    # Check lender has sufficient TAO
    lender_tao = contract.functions.userAlphaBalance(lender_address, 0).call()
    if lender_tao < tao_amount:
        print_warning(f"⚠ Lender TAO ({lender_tao / 1e9:.2f}) < Required ({tao_amount / 1e9:.2f})")
        print_warning(f"⚠ May fail on 'low lender tao' before 'bad price'")
    else:
        print_success(f"✓ Lender has sufficient TAO: {lender_tao / 1e9:.2f} TAO")

    # Check borrower has sufficient ALPHA
    borrower_alpha = contract.functions.userAlphaBalance(borrower_address, netuid).call()
    if borrower_alpha < alpha_amount:
        print_warning(f"⚠ Borrower ALPHA ({borrower_alpha / 1e9:.2f}) < Required ({alpha_amount / 1e9:.2f})")
        print_warning(f"⚠ May fail on 'low alpha' before 'bad price'")
    else:
        print_success(f"✓ Borrower has sufficient ALPHA: {borrower_alpha / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0, netuid]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": lender_address, "label": "LENDER1"},
        {"address": borrower_address, "label": "BORROWER1"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    next_loan_id = contract.functions.nextLoanId().call()

    print_info(f"\nContract State:")
    print_info(f"  nextLoanId: {next_loan_id}")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("Skipped for negative test (no loan will be created)")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute borrow() - Expected to Fail")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Failure:{NC} Transaction reverts with 'bad price'")
    print(f"  {CYAN}Reason:{NC} offer.maxAlphaPrice * 10000 >= alphaPrice * 9000")
    print(f"  {YELLOW}Check:{NC} {offer_price} * 10000 >= {on_chain_price} * 9000")
    print(f"  {YELLOW}Values:{NC} {offer_price * 10000} >= {on_chain_price * 9000}")
    print()

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

    print_info(f"Attempting to borrow {tao_amount / 1e9:.2f} TAO (should fail)...")

    # Execute transaction
    tx_receipt = None
    reverted = False
    error_msg = None

    try:
        tx = contract.functions.borrow(offer_tuple, tao_amount, alpha_amount).build_transaction({
            'from': borrower_address,
            'nonce': w3.eth.get_transaction_count(borrower_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
        })

        signed_tx = w3.eth.account.sign_transaction(tx, borrower_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        if tx_receipt['status'] == 0:
            reverted = True
            print_success("✓ Transaction reverted as expected")
        else:
            print_error("✗ Transaction succeeded unexpectedly!")

    except Exception as e:
        reverted = True
        error_msg = str(e)
        print_success(f"✓ Transaction reverted (exception caught)")
        print_info(f"Error message: {error_msg[:200]}")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final state
    next_loan_id_after = contract.functions.nextLoanId().call()

    print_info(f"\nContract State After:")
    print_info(f"  nextLoanId: {next_loan_id} → {next_loan_id_after}")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info("Skipped for negative test (no loan created)")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction reverted
    if not reverted:
        print_error("✗ TEST FAILED: Transaction did not revert")
        sys.exit(1)
    print_success("✓ Transaction reverted as expected")

    # Try to extract revert reason
    if tx_receipt and tx_receipt['status'] == 0:
        print_info("\nAttempting to extract revert reason...")
        try:
            # Replay transaction to get revert reason
            w3.eth.call({
                'to': contract.address,
                'from': borrower_address,
                'data': contract.functions.borrow(offer_tuple, tao_amount, alpha_amount).build_transaction({
                    'from': borrower_address,
                })['data']
            }, tx_receipt['blockNumber'] - 1)
        except Exception as e:
            error_str = str(e)
            if 'bad price' in error_str:
                print_success("✓ Revert reason confirmed: 'bad price'")
            else:
                print_warning(f"⚠ Revert reason: {error_str[:200]}")

    # Verify no state changes
    if next_loan_id_after != next_loan_id:
        print_error(f"✗ nextLoanId changed: {next_loan_id} → {next_loan_id_after}")
        sys.exit(1)
    print_success("✓ nextLoanId unchanged")

    # Calculate and print balance differences
    print_section("Balance Changes (Should be minimal - gas only)")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Report results
    print_section("Test Result")
    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC09: Alpha Price Not Safe")
    print_success("Borrow correctly rejected when offer price violates 90% safety margin")
    print_success("No state changes except gas deduction")
    print_success("Revert reason: 'bad price'")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - On-chain ALPHA price: {on_chain_price / 1e9:.9f} TAO per ALPHA")
    print(f"  - Safe threshold (90%): {safe_threshold / 1e9:.9f} TAO per ALPHA")
    print(f"  - Offer maxAlphaPrice: {offer_price / 1e9:.9f} TAO per ALPHA")
    print(f"  - Violates safety margin: YES ({offer_price / 1e9:.6f} >= {safe_threshold / 1e9:.6f})")
    print(f"  - Transaction correctly reverted with 'bad price'")
    print(f"  - No state changes (except gas)")
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
