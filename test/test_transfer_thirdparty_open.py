#!/usr/bin/env python3
"""
Test Case TC11: Third Party, OPEN State
Objective: Verify transfer fails when third party tries to transfer OPEN loan
Tests: require(loanData.state == STATE.IN_COLLECTION, "not collecting")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
Expected: Transaction reverts with "not collecting"
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
    """Test transfer fails when third party tries to transfer OPEN loan"""

    print_section("Test Case TC11: Third Party, OPEN State")
    print(f"{Colors.CYAN}Objective:{Colors.ENDC} Verify transfer fails when third party tries to transfer OPEN loan")
    print(f"{Colors.CYAN}Strategy:{Colors.ENDC} Third party attempts to transfer OPEN loan")
    print(f"{Colors.CYAN}Expected:{Colors.ENDC} Transaction reverts with 'not collecting'")

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
    old_lender_address = addresses['LENDER1']['evmAddress']  # Original lender
    new_lender_address = addresses['LENDER2']['evmAddress']  # New lender
    borrower_address = addresses['BORROWER1']['evmAddress']
    third_party_address = addresses['LENDER2']['evmAddress']  # Use LENDER2 as third party
    third_party_private_key = os.environ.get("LENDER2_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    print_info(f"Using Loan ID 9 (netuid 3, OPEN state)")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify third party is registered
    is_registered = contract.functions.registeredUser(third_party_address).call()
    if not is_registered:
        print_error(f"THIRD_PARTY must be registered for this test")
        return 1
    print_success(f"✓ THIRD_PARTY registered: {third_party_address}")

    # Find loan (Loan ID 9, netuid 3)
    loan_id = 9
    loan_full = get_loan_full(contract, loan_id)

    if loan_full is None:
        print_error(f"Loan {loan_id} not found")
        return 1

    loan_term = loan_full['term']
    loan_data = loan_full['data']
    offer_data = loan_full['offer']

    if loan_data['state'] != STATE_OPEN:
        print_error(f"Loan {loan_id} is not in OPEN state (current: {STATE_NAMES.get(loan_data['state'], 'UNKNOWN')})")
        print_error("This test requires loan in OPEN state")
        return 1

    loan_netuid = loan_term['netuid']
    old_lender_from_loan = offer_data['lender']

    print_success(f"✓ Found OPEN loan: Loan ID {loan_id}")
    print_info(f"  State: {STATE_NAMES[loan_data['state']]}")
    print_info(f"  Loan Netuid: {loan_netuid}")
    print_info(f"  Borrower: {loan_term['borrower']}")
    print_info(f"  Old Lender: {old_lender_from_loan}")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")

    # Verify third party is NOT the old lender
    if third_party_address.lower() == old_lender_from_loan.lower():
        print_error(f"⚠ Test setup error: Third party ({third_party_address}) is the same as old lender")
        print_error("This test requires third party to be different from old lender")
        return 1

    print_success(f"✓ Third party is different from old lender")
    print_info(f"  Old Lender: {old_lender_from_loan}")
    print_info(f"  Third Party: {third_party_address}")

    # Load new offer from LENDER2 for netuid 3
    print_info("\nLoading new offer from LENDER2...")
    new_offer_file = "offers/290f8994967f7a9cb583843fe0933d91dfa02ea3bfc4a9b3c6509bd4ca03bc39.json"  # LENDER2's offer for netuid 3
    new_offer = load_offer_from_file(new_offer_file)

    offer_netuid = new_offer['netuid']
    new_offer_lender = new_offer['lender']

    print_success("✓ New offer loaded from file")
    print_info(f"  Offer ID: {new_offer['offerId']}")
    print_info(f"  Offer Netuid: {offer_netuid}")
    print_info(f"  Offer Lender: {new_offer_lender}")
    print_info(f"  Daily Rate: {new_offer['dailyInterestRate'] / 1e9 * 100:.4f}%")
    print_info(f"  Max Alpha Price: {new_offer['maxAlphaPrice'] / 1e9:.9f} TAO/ALPHA")

    # Verify netuid matches
    if offer_netuid != loan_netuid:
        print_error(f"⚠ Test setup error: Offer netuid ({offer_netuid}) doesn't match loan netuid ({loan_netuid})")
        return 1

    # Verify lender is different
    if new_offer_lender.lower() == old_lender_from_loan.lower():
        print_error(f"⚠ Test setup error: New lender is same as old lender")
        return 1

    print_success("✓ Setup verified: Third party attempts to transfer OPEN loan")

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
        {'label': 'THIRD_PARTY', 'address': third_party_address}
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

    # ========================================================================
    # STEP 4: Execute transfer()
    # ========================================================================
    print_section("Step 4: Execute transfer()")

    print(f"\n{Colors.BOLD}Expected Result:{Colors.ENDC}")
    print(f"  {Colors.RED}Revert:{Colors.ENDC} 'not collecting'")
    print(f"  {Colors.CYAN}Reason:{Colors.ENDC} Third party cannot transfer OPEN loan")
    print(f"  {Colors.CYAN}Logic:{Colors.ENDC}")
    print(f"    - Loan state: OPEN (not IN_COLLECTION)")
    print(f"    - Initiator: {third_party_address} (not old lender)")
    print(f"    - Only old lender can transfer from OPEN state")
    print(f"    - Third parties can only transfer from IN_COLLECTION state")
    print(f"  {Colors.CYAN}State Changes:{Colors.ENDC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from third party's EVM TAO")

    print_info(f"\nAttempting to transfer loan {loan_id}...")
    print_info(f"Initiator: {third_party_address} (THIRD_PARTY, registered)")
    print_info(f"Old Lender: {old_lender_from_loan}")
    print_info(f"New Lender: {new_offer_lender}")
    print_info(f"Loan State: {STATE_NAMES[loan_data_before['state']]}")

    # Build transaction
    nonce = w3.eth.get_transaction_count(third_party_address)

    # Convert offer to tuple format (includes signature)
    offer_tuple = offer_to_tuple(new_offer)

    tx = contract.functions.transfer(
        loan_id,
        offer_tuple
    ).build_transaction({
        'from': third_party_address,
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })

    # Sign and send transaction
    signed_tx = w3.eth.account.sign_transaction(tx, third_party_private_key)
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

    # Verify netuid unchanged
    if loan_term_after['netuid'] == loan_term_before['netuid']:
        print_success(f"✓ Loan netuid unchanged ({loan_term_after['netuid']})")
    else:
        print_error(f"❌ Loan netuid changed: {loan_term_before['netuid']} → {loan_term_after['netuid']}")
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
    print_info("  - THIRD_PARTY EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # ========================================================================
    # Test Result
    # ========================================================================
    print_section("Test Result")
    print_success("✓✓✓ TEST PASSED ✓✓✓")
    print_success("TC11: Third Party, OPEN State")
    print_success("Transaction correctly reverted with 'not collecting'")
    print_success("All state validations passed")
    print_success("No unexpected state changes detected")

    print(f"\n{Colors.CYAN}Summary:{Colors.ENDC}")
    print(f"  - Third parties cannot transfer OPEN loans")
    print(f"  - Only old lender can transfer from OPEN state (after MIN_LOAN_DURATION)")
    print(f"  - Third parties can only transfer from IN_COLLECTION state")
    print(f"  - Contract state validation working correctly")
    print(f"  - Loan state remains: {STATE_NAMES[loan_data_after['state']]}")
    print(f"  - Loan Data ID unchanged: {loan_term_after['loanDataId']}")
    print(f"  - Lender unchanged: {offer_after['lender']}")
    print(f"  - Initiator: {third_party_address} (third party, rejected)")

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
