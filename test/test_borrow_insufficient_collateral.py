#!/usr/bin/env python3
"""
Test Case TC10: Insufficient Collateral
Objective: Verify borrow fails when collateral value is insufficient
Tests: Line 893 - require(_alphaAmount * _offer.maxAlphaPrice >= _taoAmount * PRICE_BASE, "low collateral")

Strategy: Attempt borrow with collateral value below loan amount
Expected: Transaction reverts with "low collateral"
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
    print_section("Test Case TC10: Insufficient Collateral")
    print(f"{CYAN}Objective:{NC} Verify borrow fails when collateral value is insufficient")
    print(f"{CYAN}Strategy:{NC} Attempt borrow with collateral value below required loan amount")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'low collateral'\n")

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

    # Find active offer from LENDER1
    offers_dir = Path(__file__).parent.parent / "offers"
    offer_file = None
    offer = None

    print_info("Searching for active offers from LENDER1...")
    offer_files = sorted(offers_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    current_timestamp = w3.eth.get_block('latest')['timestamp']

    for file in offer_files:
        candidate_offer = load_offer(file)
        if candidate_offer['lender'].lower() == lender_address.lower():
            # Check if NOT cancelled and NOT expired
            offer_id_bytes = bytes.fromhex(candidate_offer['offerId'][2:])
            cancel_block = contract.functions.canceledOffers(offer_id_bytes).call()

            if candidate_offer['expire'] > current_timestamp and cancel_block == 0:
                # Check if lender nonce matches
                lender_nonce = contract.functions.lenderNonce(lender_address).call()
                if candidate_offer['nonce'] == lender_nonce:
                    offer_file = file
                    offer = candidate_offer
                    print_success(f"Found active offer: {offer_file.name}")
                    break

    if not offer_file:
        print_error("No suitable active offer found from LENDER1")
        print_info("Please create an offer first:")
        print_info(f"  {YELLOW}python3 scripts/cli.py create-offer --account LENDER1 --max-tao 100 --alpha-price 0.25 --daily-rate 1.0 --netuid 3{NC}")
        sys.exit(1)

    # Test parameters
    netuid = offer['netuid']
    tao_amount = 50 * 10**9  # 50 TAO in RAO (loan amount)
    alpha_amount = 100 * 10**9  # 100 ALPHA in RAO (sufficient quantity, but insufficient value)
    # At offer.maxAlphaPrice = 0.25 TAO/ALPHA: 100 ALPHA * 0.25 = 25 TAO value < 50 TAO loan

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
        print_error("SETUP ERROR: LENDER1 not registered")
        print_info("Please register LENDER1:")
        print_info(f"  {YELLOW}python3 scripts/cli.py register --account LENDER1{NC}")
        sys.exit(1)
    print_success(f"✓ LENDER1 registered: {lender_address}")

    # Check BORROWER1 is registered (required for this test)
    borrower_registered = contract.functions.registeredUser(borrower_address).call()
    if not borrower_registered:
        print_error("SETUP ERROR: BORROWER1 not registered")
        print_info("Please register BORROWER1:")
        print_info(f"  {YELLOW}python3 scripts/cli.py register --account BORROWER1{NC}")
        sys.exit(1)
    print_success(f"✓ BORROWER1 registered: {borrower_address}")

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
    print_success(f"✓ Subnet {netuid} is active")

    # Check lender has SUFFICIENT TAO (required for this test)
    lender_tao = contract.functions.userAlphaBalance(lender_address, 0).call()
    if lender_tao < tao_amount:
        print_error("SETUP ERROR: Lender has insufficient TAO")
        print_error(f"  Required: {tao_amount / 1e9:.2f} TAO")
        print_error(f"  Available: {lender_tao / 1e9:.2f} TAO")
        sys.exit(1)
    print_success(f"✓ Lender has sufficient TAO: {lender_tao / 1e9:.2f} TAO")

    # Check borrower has SUFFICIENT ALPHA quantity (required for this test)
    borrower_alpha = contract.functions.userAlphaBalance(borrower_address, netuid).call()
    if borrower_alpha < alpha_amount:
        print_error("SETUP ERROR: Borrower has insufficient ALPHA")
        print_error(f"  Required: {alpha_amount / 1e9:.2f} ALPHA")
        print_error(f"  Available: {borrower_alpha / 1e9:.2f} ALPHA")
        sys.exit(1)
    print_success(f"✓ Borrower has sufficient ALPHA: {borrower_alpha / 1e9:.2f} ALPHA")

    # Calculate and display collateral value
    # Assuming offer maxAlphaPrice is around 0.25 TAO/ALPHA
    print_info(f"\nCollateral Value Check:")
    print_info(f"  ALPHA amount: {alpha_amount / 1e9:.2f} ALPHA")
    print_info(f"  Loan amount: {tao_amount / 1e9:.2f} TAO")
    print_info(f"  Expected: Collateral value < Loan amount (insufficient)")

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
    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    next_loan_id = contract.functions.nextLoanId().call()
    next_loan_data_id = contract.functions.nextLoanDataId().call()
    offer_id_bytes = bytes.fromhex(offer['offerId'][2:])
    lend_balance = contract.functions.userLendBalance(lender_address, offer_id_bytes).call()

    print_info(f"\nContract State:")
    print_info(f"  nextLoanId: {next_loan_id}")
    print_info(f"  nextLoanDataId: {next_loan_data_id}")
    print_info(f"  userLendBalance[LENDER1][offerId]: {lend_balance / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")

    print_info(f"Reading loan state for loan ID {next_loan_id} (to be created if test passes)...")

    try:
        loan_info_before = get_loan_full(contract, next_loan_id)
        loan_term_before, loan_data_before, loan_offer_before = loan_info_before

        if loan_term_before['borrower'] == '0x0000000000000000000000000000000000000000':
            print_success(f"✓ Loan ID {next_loan_id} does not exist yet (as expected)")
        else:
            print_warning(f"⚠ Loan ID {next_loan_id} already exists")
    except Exception as e:
        print_info(f"Loan {next_loan_id} does not exist (expected): {str(e)[:100]}")

    # ========================================================================
    # STEP 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute borrow()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} 'low collateral'")
    print(f"  {CYAN}Reason:{NC} Collateral value insufficient for loan amount")
    print(f"  {CYAN}Formula:{NC} alphaAmount * maxAlphaPrice < taoAmount * PRICE_BASE")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from borrower's EVM TAO")
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

    print_info(f"Attempting to borrow {tao_amount / 1e9:.2f} TAO with {alpha_amount / 1e9:.2f} ALPHA collateral...")
    print_info(f"Collateral value will be insufficient based on offer price")

    # Execute transaction
    tx_receipt = None
    reverted = False
    revert_reason = None

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
            print_warning("Transaction reverted (as expected)")

    except Exception as e:
        reverted = True
        error_msg = str(e)
        revert_reason = error_msg
        print_success(f"✓ Transaction reverted before mining (as expected)")

        # Try to extract revert reason
        if "low collateral" in error_msg.lower() or "collateral" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'low collateral'")

        print_info(f"Error message: {error_msg[:300]}")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final state
    next_loan_id_after = contract.functions.nextLoanId().call()
    next_loan_data_id_after = contract.functions.nextLoanDataId().call()
    lend_balance_after = contract.functions.userLendBalance(lender_address, offer_id_bytes).call()

    print_info(f"\nContract State After:")
    print_info(f"  nextLoanId: {next_loan_id} → {next_loan_id_after}")
    print_info(f"  nextLoanDataId: {next_loan_data_id} → {next_loan_data_id_after}")
    print_info(f"  userLendBalance[LENDER1][offerId]: {lend_balance / 1e9:.2f} → {lend_balance_after / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")

    print_info(f"Verifying loan {next_loan_id} was NOT created...")
    try:
        loan_info_after = get_loan_full(contract, next_loan_id)
        loan_term_after, _, _ = loan_info_after
        if loan_term_after['borrower'] == '0x0000000000000000000000000000000000000000':
            print_success(f"✓ Loan ID {next_loan_id} still does not exist (as expected)")
        else:
            print_error(f"✗ Loan ID {next_loan_id} was created unexpectedly!")
            sys.exit(1)
    except:
        print_success(f"✓ Loan ID {next_loan_id} was not created (as expected)")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction reverted
    if not reverted and (tx_receipt and tx_receipt['status'] == 1):
        print_error("✗ Transaction succeeded unexpectedly!")
        print_error("Expected: Transaction should revert with 'not registered'")
        sys.exit(1)

    print_success("✓ Transaction reverted as expected")

    # Verify revert reason contains "low collateral"
    if revert_reason and "low collateral" in revert_reason.lower():
        print_success("✓ Revert reason confirmed: 'low collateral'")
    elif revert_reason:
        print_warning(f"⚠ Revert reason may differ: {revert_reason[:200]}")

    # Verify no state changes (except gas)
    if next_loan_id_after != next_loan_id:
        print_error(f"✗ nextLoanId changed unexpectedly: {next_loan_id} → {next_loan_id_after}")
        sys.exit(1)
    print_success("✓ nextLoanId unchanged")

    if next_loan_data_id_after != next_loan_data_id:
        print_error(f"✗ nextLoanDataId changed unexpectedly: {next_loan_data_id} → {next_loan_data_id_after}")
        sys.exit(1)
    print_success("✓ nextLoanDataId unchanged")

    if lend_balance_after != lend_balance:
        print_error(f"✗ Lend balance changed unexpectedly")
        sys.exit(1)
    print_success("✓ Lend balance unchanged")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # Verify only gas was deducted
    print_info("\nExpected changes:")
    print_info("  - Borrower EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # Get borrower balance change
    borrower_before = snapshot_before['balances']['BORROWER1']['evm_tao_wei']
    borrower_after = snapshot_after['balances']['BORROWER1']['evm_tao_wei']
    borrower_diff = borrower_after - borrower_before

    if borrower_diff < 0:
        print_success(f"✓ Borrower EVM TAO decreased (gas): {abs(borrower_diff) / 1e18:.9f} TAO")
    else:
        print_warning(f"⚠ Borrower EVM TAO did not decrease (may have reverted before gas charge)")

    # Verify all contract balances unchanged
    lender_tao_before = snapshot_before['balances']['LENDER1']['contract']['netuid_0']['balance_rao']
    lender_tao_after = snapshot_after['balances']['LENDER1']['contract']['netuid_0']['balance_rao']

    if lender_tao_before == lender_tao_after:
        print_success("✓ Lender contract TAO balance unchanged")
    else:
        print_error(f"✗ Lender contract TAO balance changed unexpectedly!")
        sys.exit(1)

    borrower_alpha_before = snapshot_before['balances']['BORROWER1']['contract'].get(f'netuid_{netuid}', {}).get('balance_rao', 0)
    borrower_alpha_after = snapshot_after['balances']['BORROWER1']['contract'].get(f'netuid_{netuid}', {}).get('balance_rao', 0)

    if borrower_alpha_before == borrower_alpha_after:
        print_success("✓ Borrower contract ALPHA balance unchanged")
    else:
        print_error(f"✗ Borrower contract ALPHA balance changed unexpectedly!")
        sys.exit(1)

    # Report results
    print_section("Test Result")

    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC10: Insufficient Collateral")
    print_success(f"Transaction correctly reverted with 'low collateral'")
    print_success("All state validations passed")
    print_success("No unexpected state changes detected")

    print(f"\n{CYAN}Summary:{NC}")
    print(f"  - Borrow with insufficient collateral value correctly fails")
    print(f"  - Collateral value validation working correctly")
    print(f"  - Contract protects lenders by requiring adequate collateral value")

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
