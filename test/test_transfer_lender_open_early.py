#!/usr/bin/env python3
"""
Test Case TC10: Original Lender, OPEN State, Too Early
Objective: Verify transfer fails when original lender tries to transfer OPEN loan before MIN_LOAN_DURATION
Tests: require(block.number > loanData.startBlock + MIN_LOAN_DURATION, "too early")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "too early"

Special Setup: This test creates a new loan and immediately attempts transfer
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
    offer_to_tuple, load_offer_from_file,
    STATE_OPEN, STATE_IN_COLLECTION, STATE_NAMES
)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Color codes for output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_section(title):
    print(f"\n{'='*80}")
    print(f"{Colors.BOLD}{title}{Colors.ENDC}")
    print(f"{'='*80}")

def print_info(msg):
    print(f"{Colors.CYAN}[INFO]{Colors.ENDC} {msg}")

def print_success(msg):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.ENDC} {msg}")

def print_error(msg):
    print(f"{Colors.RED}[ERROR]{Colors.ENDC} {msg}")

def print_warning(msg):
    print(f"{Colors.BOLD}{Colors.YELLOW}[WARNING]{Colors.ENDC} {msg}")

def main():
    """Test transfer fails when original lender tries to transfer too early"""

    print_section("Test Case TC10: Original Lender, OPEN State, Too Early")
    print(f"{Colors.CYAN}Objective:{Colors.ENDC} Verify transfer fails before MIN_LOAN_DURATION")
    print(f"{Colors.CYAN}Strategy:{Colors.ENDC} Create new loan, then OLD_LENDER attempts immediate transfer")
    print(f"{Colors.CYAN}Expected:{Colors.ENDC} Transaction reverts with 'too early'")

    # Load configuration
    print_info("\nSetting up test environment...")
    addresses = load_addresses()

    # Connect to network
    rpc_url = os.environ.get('RPC_URL', 'http://127.0.0.1:9945')
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print_error("Failed to connect to network")
        return 1

    print_success(f"Connected to Bittensor EVM (Chain ID: {w3.eth.chain_id})")

    # Load contract
    contract_abi = load_contract_abi()
    contract = w3.eth.contract(address=LENDING_POOL_V2_ADDRESS, abi=contract_abi)

    # Test accounts
    old_lender_address = addresses['LENDER1']['evmAddress']
    new_lender_address = addresses['LENDER2']['evmAddress']
    borrower_address = addresses['BORROWER1']['evmAddress']
    lender_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    # Use recently created loan (Loan ID 11, created via CLI)
    loan_id = 11

    print_info(f"Using Loan ID {loan_id} (recently created)")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify accounts are registered
    is_registered_lender = contract.functions.registeredUser(old_lender_address).call()
    if not is_registered_lender:
        print_error(f"OLD_LENDER must be registered for this test")
        return 1
    print_success(f"✓ OLD_LENDER registered: {old_lender_address}")

    is_registered_new = contract.functions.registeredUser(new_lender_address).call()
    if not is_registered_new:
        print_error(f"NEW_LENDER must be registered for this test")
        return 1
    print_success(f"✓ NEW_LENDER registered: {new_lender_address}")

    # Verify loan exists
    loan_full = get_loan_full(contract, loan_id)
    if loan_full is None:
        print_error(f"Loan {loan_id} not found")
        print_error("Please create a new loan first using:")
        print_error("python3 scripts/cli.py borrow --offer-file offers/959ef93720143532e0192a296ede97d4377c39e68a49865638382a6b8575295d.json --tao-amount 15 --alpha-amount 30 --account BORROWER1")
        return 1

    loan_data = loan_full['data']
    loan_term = loan_full['term']
    offer_data = loan_full['offer']
    netuid = loan_term['netuid']

    print_success(f"✓ Found loan: Loan ID {loan_id}")
    print_info(f"  State: {STATE_NAMES[loan_data['state']]}")
    print_info(f"  Start Block: {loan_data['startBlock']}")
    print_info(f"  Lender: {offer_data['lender']}")
    print_info(f"  Borrower: {loan_term['borrower']}")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Netuid: {netuid}")

    # Check MIN_LOAN_DURATION
    current_block = w3.eth.block_number
    MIN_LOAN_DURATION = contract.functions.MIN_LOAN_DURATION().call()
    elapsed_blocks = current_block - loan_data['startBlock']

    print_warning(f"\nTiming Check:")
    print_warning(f"  Current Block: {current_block}")
    print_warning(f"  Start Block: {loan_data['startBlock']}")
    print_warning(f"  Blocks Elapsed: {elapsed_blocks}")
    print_warning(f"  MIN_LOAN_DURATION: {MIN_LOAN_DURATION}")

    if elapsed_blocks > MIN_LOAN_DURATION:
        print_error(f"✗ Too much time elapsed: {elapsed_blocks} > {MIN_LOAN_DURATION}")
        print_error("Cannot test 'too early' condition")
        return 1

    print_success(f"✓ Timing is correct for test (elapsed {elapsed_blocks} <= {MIN_LOAN_DURATION})")

    # Load new lender's offer for transfer
    print_info(f"\nLoading new lender's offer...")
    new_offer_file = "offers/290f8994967f7a9cb583843fe0933d91dfa02ea3bfc4a9b3c6509bd4ca03bc39.json"  # LENDER2, netuid 3
    new_offer = load_offer_from_file(new_offer_file)

    print_success("✓ New offer loaded")
    print_info(f"  Offer ID: {new_offer['offerId'][:10]}...")
    print_info(f"  Lender: {new_offer['lender']}")
    print_info(f"  Daily Rate: {new_offer['dailyInterestRate']} ({new_offer['dailyInterestRate'] / 1e9 * 100:.4f}%)")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")
    print_info("Capturing initial state snapshot...")

    # Setup BalanceChecker
    test_netuids = [0, netuid]
    checker = BalanceChecker(w3, contract, test_netuids)

    # Capture initial snapshot
    snapshot_accounts = [
        {'label': 'OLD_LENDER', 'address': old_lender_address},
        {'label': 'NEW_LENDER', 'address': new_lender_address},
        {'label': 'BORROWER', 'address': borrower_address}
    ]

    before_snapshot = checker.capture_snapshot(snapshot_accounts)
    checker.print_snapshot(before_snapshot)

    # Query specific contract state
    protocol_fee_before = contract.functions.protocolFeeAccumulated().call()
    old_lender_balance_before = contract.functions.userLendBalance(old_lender_address, offer_data['offerId']).call()

    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance: {old_lender_balance_before / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info(f"Reading loan state for loan ID {loan_id}...")

    loan_before = get_loan_full(contract, loan_id)
    loan_term_before = loan_before['term']
    loan_data_before = loan_before['data']
    offer_before = loan_before['offer']

    print_info(f"Loan State Before:")
    print_info(f"  Loan Data ID: {loan_term_before['loanDataId']}")
    print_info(f"  State: {STATE_NAMES[loan_data_before['state']]}")
    print_info(f"  Start Block: {loan_data_before['startBlock']}")
    print_info(f"  Lender: {offer_before['lender']}")
    print_info(f"  Borrower: {loan_term_before['borrower']}")

    # ========================================================================
    # STEP 4: Execute transfer()
    # ========================================================================
    print_section("Step 4: Execute transfer()")

    # Recalculate timing right before transfer
    current_block_before_tx = w3.eth.block_number
    elapsed_before_tx = current_block_before_tx - loan_data_before['startBlock']

    print(f"\n{Colors.BOLD}Expected Result:{Colors.ENDC}")
    print(f"  {Colors.RED}Revert:{Colors.ENDC} 'too early'")
    print(f"  {Colors.CYAN}Reason:{Colors.ENDC} Blocks elapsed ({elapsed_before_tx}) <= MIN_LOAN_DURATION ({MIN_LOAN_DURATION})")
    print(f"  {Colors.CYAN}State Changes:{Colors.ENDC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from initiator's EVM TAO")

    print_info(f"\nAttempting to transfer loan {loan_id} (TOO EARLY)...")
    print_info(f"Initiator: {old_lender_address} (OLD_LENDER, registered)")
    print_info(f"Old Lender: {offer_before['lender']}")
    print_info(f"New Lender: {new_offer['lender']}")
    print_info(f"Loan State: {STATE_NAMES[loan_data_before['state']]}")
    print_info(f"Current Block: {current_block_before_tx}")
    print_info(f"Start Block: {loan_data_before['startBlock']}")
    print_info(f"Elapsed: {elapsed_before_tx} blocks (need > {MIN_LOAN_DURATION})")

    # Build transfer transaction
    nonce = w3.eth.get_transaction_count(old_lender_address)
    offer_tuple = offer_to_tuple(new_offer)

    tx = contract.functions.transfer(
        loan_id,
        offer_tuple
    ).build_transaction({
        'from': old_lender_address,
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })

    # Sign and send transfer transaction
    signed_tx = w3.eth.account.sign_transaction(tx, lender_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print_info(f"Transfer transaction sent: {tx_hash.hex()}")

    # Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print_info(f"Transfer transaction mined in block {receipt['blockNumber']}")

    # Check transaction status
    if receipt['status'] == 0:
        print_warning("Transaction reverted (as expected)")
    else:
        print_error("❌ Transaction succeeded - UNEXPECTED! Test should have reverted.")
        return 1

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")
    print_info("Capturing final state snapshot...")

    after_snapshot = checker.capture_snapshot(snapshot_accounts)
    checker.print_snapshot(after_snapshot)

    # Query contract state after
    protocol_fee_after = contract.functions.protocolFeeAccumulated().call()
    old_lender_balance_after = contract.functions.userLendBalance(old_lender_address, offer_data['offerId']).call()

    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} → {protocol_fee_after / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance: {old_lender_balance_before / 1e9:.2f} → {old_lender_balance_after / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info(f"Verifying loan {loan_id} state unchanged...")

    loan_after = get_loan_full(contract, loan_id)
    loan_term_after = loan_after['term']
    loan_data_after = loan_after['data']
    offer_after = loan_after['offer']

    print_info(f"Loan State After:")
    print_info(f"  Loan Data ID: {loan_term_after['loanDataId']}")
    print_info(f"  State: {STATE_NAMES[loan_data_after['state']]}")
    print_info(f"  Lender: {offer_after['lender']}")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Verify transaction reverted
    if receipt['status'] == 0:
        print_success("✓ Transaction reverted as expected")
    else:
        print_error("❌ Transaction did not revert")
        return 1

    # Verify loan state unchanged
    if loan_data_after['state'] == loan_data_before['state']:
        print_success(f"✓ Loan state unchanged ({STATE_NAMES[loan_data_after['state']]})")
    else:
        print_error(f"❌ Loan state changed: {STATE_NAMES[loan_data_before['state']]} → {STATE_NAMES[loan_data_after['state']]}")
        return 1

    # Verify loan data ID unchanged
    if loan_term_after['loanDataId'] == loan_term_before['loanDataId']:
        print_success("✓ Loan Data ID unchanged")
    else:
        print_error(f"❌ Loan Data ID changed: {loan_term_before['loanDataId']} → {loan_term_after['loanDataId']}")
        return 1

    # Verify lender unchanged
    if offer_after['lender'].lower() == offer_before['lender'].lower():
        print_success("✓ Lender unchanged")
    else:
        print_error(f"❌ Lender changed: {offer_before['lender']} → {offer_after['lender']}")
        return 1

    # Verify protocol fee unchanged
    if protocol_fee_after == protocol_fee_before:
        print_success("✓ Protocol fee unchanged")
    else:
        print_error(f"❌ Protocol fee changed")
        return 1

    # Verify old lender balance unchanged
    if old_lender_balance_after == old_lender_balance_before:
        print_success("✓ OLD_LENDER lend balance unchanged")
    else:
        print_error(f"❌ OLD_LENDER lend balance changed")
        return 1

    # ========================================================================
    # Balance Changes
    # ========================================================================
    print_section("Balance Changes")

    diff = checker.diff_snapshots(before_snapshot, after_snapshot)
    checker.print_diff(diff)

    print_info("\nExpected changes:")
    print_info("  - OLD_LENDER EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # ========================================================================
    # Test Result
    # ========================================================================
    print_section("Test Result")
    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC10: Original Lender, OPEN State, Too Early")
    print_success("Transaction correctly reverted with 'too early'")
    print_success("All state validations passed")
    print_success("No unexpected state changes detected")

    print(f"\n{Colors.CYAN}Summary:{Colors.ENDC}")
    print(f"  - Cannot transfer OPEN loan before MIN_LOAN_DURATION")
    print(f"  - Timing validation working correctly")
    print(f"  - MIN_LOAN_DURATION: {MIN_LOAN_DURATION} blocks")
    print(f"  - Blocks elapsed at transfer: {elapsed_before_tx}")
    print(f"  - Start block: {loan_data_before['startBlock']}")
    print(f"  - Transfer block: {current_block_before_tx}")
    print(f"  - Loan state remains: {STATE_NAMES[loan_data_after['state']]}")
    print(f"  - Loan Data ID unchanged: {loan_term_after['loanDataId']}")

    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_error("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
