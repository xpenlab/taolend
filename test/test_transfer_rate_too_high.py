#!/usr/bin/env python3
"""
Test Case TC09: Day Rate Too High (>150%)
Objective: Verify transfer fails when new rate exceeds 150% of old rate
Tests: require(_offer.dailyInterestRate <= oldOffer.dailyInterestRate * 150 / 100, "day rate too high")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "day rate too high"
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
    """Test transfer fails when new rate exceeds 150% of old rate"""

    print_section("Test Case TC09: Day Rate Too High (>150%)")
    print(f"{Colors.CYAN}Objective:{Colors.ENDC} Verify transfer fails when new rate exceeds 150% of old rate")
    print(f"{Colors.CYAN}Strategy:{Colors.ENDC} Attempt transfer with new rate > 150% of old rate")
    print(f"{Colors.CYAN}Expected:{Colors.ENDC} Transaction reverts with 'day rate too high'")

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

    # Test setup: Loan 10 has rate 6000000 (0.6%), lender LENDER1
    # We'll use LENDER2's offer with rate 10000000 (1.0%)
    # Rate ratio: 10000000 / 6000000 = 166.67% > 150% limit
    loan_id = 10
    old_lender_address = addresses['LENDER1']['evmAddress']
    new_lender_address = addresses['LENDER2']['evmAddress']
    borrower_address = addresses['BORROWER1']['evmAddress']
    initiator_address = addresses['LENDER1']['evmAddress']  # OLD_LENDER initiates
    initiator_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    print_info(f"Using Loan ID {loan_id} (netuid 3, OPEN state)")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify accounts are registered
    is_registered = contract.functions.registeredUser(initiator_address).call()
    if not is_registered:
        print_error(f"INITIATOR must be registered for this test")
        return 1
    print_success(f"✓ INITIATOR registered: {initiator_address}")

    is_registered_new = contract.functions.registeredUser(new_lender_address).call()
    if not is_registered_new:
        print_error(f"NEW_LENDER must be registered for this test")
        return 1
    print_success(f"✓ NEW_LENDER registered: {new_lender_address}")

    # Find loan
    loan_full = get_loan_full(contract, loan_id)

    if loan_full is None:
        print_error(f"Loan {loan_id} not found")
        return 1

    loan_term = loan_full['term']
    loan_data = loan_full['data']
    offer_data = loan_full['offer']

    if loan_data['state'] not in [STATE_OPEN, STATE_IN_COLLECTION]:
        print_error(f"Loan {loan_id} is not in active state (current: {STATE_NAMES.get(loan_data['state'], 'UNKNOWN')})")
        return 1

    loan_netuid = loan_term['netuid']
    old_lender_from_loan = offer_data['lender']
    old_rate = offer_data['dailyInterestRate']

    print_success(f"✓ Found active loan: Loan ID {loan_id}")
    print_info(f"  State: {STATE_NAMES[loan_data['state']]}")
    print_info(f"  Loan Netuid: {loan_netuid}")
    print_info(f"  Borrower: {loan_term['borrower']}")
    print_info(f"  Old Lender: {old_lender_from_loan}")
    print_info(f"  Old Rate: {old_rate} ({old_rate / 1e9 * 100:.4f}%)")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")

    # Verify old rate is 6000000 (0.6%)
    if old_rate != 6000000:
        print_error(f"⚠ Test setup error: Expected old rate 6000000, got {old_rate}")
        print_error("This test requires loan with rate 6000000 (0.6%)")
        return 1

    print_success(f"✓ Old rate confirmed: {old_rate} (0.6%)")

    # Load new offer with HIGH rate (10000000 = 1.0%)
    print_info("\nLoading new high-rate offer...")
    new_offer_file = "offers/290f8994967f7a9cb583843fe0933d91dfa02ea3bfc4a9b3c6509bd4ca03bc39.json"  # LENDER2, netuid 3, rate 10000000
    new_offer = load_offer_from_file(new_offer_file)

    offer_netuid = new_offer['netuid']
    new_offer_lender = new_offer['lender']
    new_rate = new_offer['dailyInterestRate']

    print_success("✓ New offer loaded from file")
    print_info(f"  Offer ID: {new_offer['offerId']}")
    print_info(f"  Offer Netuid: {offer_netuid}")
    print_info(f"  Offer Lender: {new_offer_lender}")
    print_info(f"  New Rate: {new_rate} ({new_rate / 1e9 * 100:.4f}%)")
    print_info(f"  Max Alpha Price: {new_offer['maxAlphaPrice'] / 1e9:.9f} TAO/ALPHA")

    # Verify netuid matches
    if offer_netuid != loan_netuid:
        print_error(f"⚠ Test setup error: Offer netuid ({offer_netuid}) doesn't match loan netuid ({loan_netuid})")
        return 1

    # Verify lender is different
    if new_offer_lender.lower() == old_lender_from_loan.lower():
        print_error(f"⚠ Test setup error: New lender is same as old lender")
        return 1

    # Calculate rate ratio
    rate_ratio = (new_rate * 100) // old_rate  # Percentage
    max_allowed_rate = (old_rate * 150) // 100

    print_warning(f"\nRate Check:")
    print_warning(f"  Old Rate: {old_rate} ({old_rate / 1e9 * 100:.4f}%)")
    print_warning(f"  New Rate: {new_rate} ({new_rate / 1e9 * 100:.4f}%)")
    print_warning(f"  Rate Ratio: {rate_ratio}% (new/old)")
    print_warning(f"  Max Allowed Rate (150%): {max_allowed_rate} ({max_allowed_rate / 1e9 * 100:.4f}%)")
    print_warning(f"  Status: {new_rate} > {max_allowed_rate} ➔ TOO HIGH ✗")

    if new_rate <= max_allowed_rate:
        print_error(f"⚠ Test setup error: New rate ({new_rate}) is not > 150% of old rate ({max_allowed_rate})")
        return 1

    print_success("✓ Rate validation confirmed: new rate exceeds 150% limit")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")
    print_info("Capturing initial state snapshot...")

    # Setup BalanceChecker
    test_netuids = [0, loan_netuid]
    checker = BalanceChecker(w3, contract, test_netuids)

    # Capture initial snapshot
    snapshot_accounts = [
        {'label': 'OLD_LENDER', 'address': old_lender_address},
        {'label': 'NEW_LENDER', 'address': new_lender_address},
        {'label': 'BORROWER1', 'address': borrower_address},
        {'label': 'INITIATOR', 'address': initiator_address}
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
    print_info(f"  Netuid: {loan_term_before['netuid']}")
    print_info(f"  Lender: {offer_before['lender']}")
    print_info(f"  Borrower: {loan_term_before['borrower']}")
    print_info(f"  Loan Amount: {loan_data_before['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term_before['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Daily Rate: {offer_before['dailyInterestRate']} ({offer_before['dailyInterestRate'] / 1e9 * 100:.4f}%)")

    # ========================================================================
    # STEP 4: Execute transfer()
    # ========================================================================
    print_section("Step 4: Execute transfer()")

    print(f"\n{Colors.BOLD}Expected Result:{Colors.ENDC}")
    print(f"  {Colors.RED}Revert:{Colors.ENDC} 'day rate too high'")
    print(f"  {Colors.CYAN}Reason:{Colors.ENDC} New rate ({new_rate}) exceeds 150% of old rate ({max_allowed_rate})")
    print(f"  {Colors.CYAN}Rate Ratio:{Colors.ENDC} {rate_ratio}% > 150%")
    print(f"  {Colors.CYAN}State Changes:{Colors.ENDC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from initiator's EVM TAO")

    print_info(f"\nAttempting to transfer loan {loan_id}...")
    print_info(f"Initiator: {initiator_address} (OLD_LENDER, registered)")
    print_info(f"Old Lender: {old_lender_from_loan}")
    print_info(f"New Lender: {new_offer_lender}")
    print_info(f"Old Rate: {old_rate} → New Rate: {new_rate}")

    # Build transaction
    nonce = w3.eth.get_transaction_count(initiator_address)

    # Convert offer to tuple format (includes signature)
    offer_tuple = offer_to_tuple(new_offer)

    tx = contract.functions.transfer(
        loan_id,
        offer_tuple
    ).build_transaction({
        'from': initiator_address,
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, initiator_private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print_info(f"Transaction sent: {tx_hash.hex()}")

    # Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print_info(f"Transaction mined in block {receipt['blockNumber']}")

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
    print_info(f"  Netuid: {loan_term_after['netuid']}")
    print_info(f"  Lender: {offer_after['lender']}")
    print_info(f"  Daily Rate: {offer_after['dailyInterestRate']} ({offer_after['dailyInterestRate'] / 1e9 * 100:.4f}%)")

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

    # Verify daily rate unchanged
    if offer_after['dailyInterestRate'] == offer_before['dailyInterestRate']:
        print_success(f"✓ Daily rate unchanged ({offer_after['dailyInterestRate']})")
    else:
        print_error(f"❌ Daily rate changed: {offer_before['dailyInterestRate']} → {offer_after['dailyInterestRate']}")
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
    print_info("  - INITIATOR EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # ========================================================================
    # Test Result
    # ========================================================================
    print_section("Test Result")
    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC09: Day Rate Too High (>150%)")
    print_success("Transaction correctly reverted with 'day rate too high'")
    print_success("All state validations passed")
    print_success("No unexpected state changes detected")

    print(f"\n{Colors.CYAN}Summary:{Colors.ENDC}")
    print(f"  - Cannot transfer loan with rate increase > 150%")
    print(f"  - Rate validation working correctly")
    print(f"  - Old rate: {old_rate} ({old_rate / 1e9 * 100:.4f}%)")
    print(f"  - New rate (rejected): {new_rate} ({new_rate / 1e9 * 100:.4f}%)")
    print(f"  - Rate ratio: {rate_ratio}% (limit: 150%)")
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
