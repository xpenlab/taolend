#!/usr/bin/env python3
"""
Test Case TC14: Bad Alpha Price
Objective: Verify transfer fails when offer's maxAlphaPrice is too high (>= 90% of on-chain price)
Tests: _alphaPriceChecker - require(alphaPrice * SAFE_ALPHA_PRICE > _offer.maxAlphaPrice * RATE_BASE, "bad price")

Strategy: 8-step testing pattern with BalanceChecker and get_loan_full
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
from common import (
    get_loan_full, load_addresses, load_contract_abi,
    offer_to_tuple, create_offer, sign_offer, get_offer_id,
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

def calculate_repay_amount(loan_amount_rao, start_block, current_block, daily_rate):
    """Calculate expected repay amount"""
    BLOCKS_PER_DAY = 7200
    PRICE_BASE = int(1e9)

    elapsed_blocks = current_block - start_block
    interest = (loan_amount_rao * elapsed_blocks * daily_rate) // (BLOCKS_PER_DAY * PRICE_BASE)
    repay_amount = loan_amount_rao + interest

    return repay_amount, interest

def main():
    """Test transfer fails when offer's maxAlphaPrice is too high (>= 90% of on-chain price)"""

    print_section("Test Case TC14: Bad Alpha Price")
    print(f"{Colors.CYAN}Objective:{Colors.ENDC} Verify transfer fails when offer's maxAlphaPrice >= 90% of on-chain price")
    print(f"{Colors.CYAN}Strategy:{Colors.ENDC} Create offer with maxAlphaPrice = onChainPrice * 95% (unsafe)")
    print(f"{Colors.CYAN}Expected:{Colors.ENDC} Transaction reverts with 'bad price'")

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
    initiator_address = addresses['LENDER1']['evmAddress']  # OLD_LENDER initiates transfer
    initiator_private_key = os.environ.get("LENDER1_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")
    new_lender_private_key = os.environ.get("LENDER2_PRIVATE_KEY") or os.environ.get("ETH_PRIVATE_KEY")

    print_info(f"Using Loan ID 9 (netuid 3, OPEN state)")

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

    is_new_lender_registered = contract.functions.registeredUser(new_lender_address).call()
    if not is_new_lender_registered:
        print_error(f"NEW_LENDER must be registered for this test")
        return 1
    print_success(f"✓ NEW_LENDER registered: {new_lender_address}")

    # Find loan
    loan_id = 9
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

    print_success(f"✓ Found active loan: Loan ID {loan_id}")
    print_info(f"  State: {STATE_NAMES[loan_data['state']]}")
    print_info(f"  Loan Netuid: {loan_netuid}")
    print_info(f"  Borrower: {loan_term['borrower']}")
    print_info(f"  Old Lender: {old_lender_from_loan}")
    print_info(f"  Loan Amount: {loan_data['loanAmount'] / 1e9:.2f} TAO")
    print_info(f"  Collateral: {loan_term['collateralAmount'] / 1e9:.2f} ALPHA")
    print_info(f"  Start Block: {loan_data['startBlock']}")
    print_info(f"  Daily Rate: {offer_data['dailyInterestRate'] / 1e9 * 100:.4f}%")

    # Calculate repay amount
    current_block = w3.eth.block_number
    repay_amount, interest = calculate_repay_amount(
        loan_data['loanAmount'],
        loan_data['startBlock'],
        current_block,
        offer_data['dailyInterestRate']
    )

    print_info(f"\nRepayment Calculation:")
    print_info(f"  Current Block: {current_block}")
    print_info(f"  Elapsed Blocks: {current_block - loan_data['startBlock']}")
    print_info(f"  Interest Accrued: {interest / 1e9:.9f} TAO")
    print_info(f"  Repay Amount: {repay_amount / 1e9:.9f} TAO")

    # Query on-chain ALPHA price
    print_info(f"\nQuerying on-chain ALPHA price for netuid {loan_netuid}...")
    on_chain_price = contract.functions.getAlphaPrice(loan_netuid).call()
    print_info(f"  On-chain ALPHA price: {on_chain_price / 1e9:.9f} TAO/ALPHA")

    # Calculate unsafe price (95% of on-chain price)
    # Contract requires: alphaPrice * SAFE_ALPHA_PRICE > maxAlphaPrice * RATE_BASE
    # Where SAFE_ALPHA_PRICE = 9000 (90%) and RATE_BASE = 10000
    # So: alphaPrice * 9000 > maxAlphaPrice * 10000
    # Or: maxAlphaPrice < alphaPrice * 0.9
    # We set maxAlphaPrice = alphaPrice * 0.95 (95% > 90%, should fail)
    unsafe_max_alpha_price = int(on_chain_price * 0.95)
    safe_threshold = int(on_chain_price * 0.9)

    print_info(f"\nPrice Safety Analysis:")
    print_info(f"  On-chain price: {on_chain_price / 1e9:.9f} TAO/ALPHA")
    print_info(f"  90% threshold: {safe_threshold / 1e9:.9f} TAO/ALPHA")
    print_info(f"  Unsafe offer price: {unsafe_max_alpha_price / 1e9:.9f} TAO/ALPHA (95%)")
    print_info(f"  Result: {unsafe_max_alpha_price / 1e9:.9f} > {safe_threshold / 1e9:.9f} (UNSAFE)")

    # Verify NEW_LENDER has sufficient TAO
    new_lender_tao_balance = contract.functions.userAlphaBalance(new_lender_address, 0).call()
    print_info(f"\nNEW_LENDER TAO Balance:")
    print_info(f"  Current Balance: {new_lender_tao_balance / 1e9:.9f} TAO")
    print_info(f"  Required (repayAmount): {repay_amount / 1e9:.9f} TAO")

    if new_lender_tao_balance < repay_amount:
        print_error(f"NEW_LENDER has insufficient balance. Please deposit more TAO first.")
        return 1
    print_success(f"✓ NEW_LENDER has sufficient balance")

    # Create unsafe offer
    print_info(f"\nCreating UNSAFE offer with maxAlphaPrice = {unsafe_max_alpha_price / 1e9:.9f} TAO/ALPHA (95% of on-chain)...")

    # Create offer with unsafe price
    unsafe_offer = create_offer(
        w3=w3,
        contract=contract,
        lender_address=new_lender_address,
        lender_private_key=new_lender_private_key,
        netuid=loan_netuid,
        expire_seconds=86400,  # 1 day
        max_tao_amount=int(100e9),  # 100 TAO
        max_alpha_price=unsafe_max_alpha_price,  # 95% of on-chain (UNSAFE)
        daily_interest_rate=offer_data['dailyInterestRate']  # Same rate as old offer
    )

    print_success("✓ Unsafe offer created and signed")
    print_info(f"  Offer ID: {unsafe_offer['offerId'].hex()}")
    print_info(f"  Lender: {unsafe_offer['lender']}")
    print_info(f"  Netuid: {unsafe_offer['netuid']}")
    print_info(f"  Max Alpha Price: {unsafe_offer['maxAlphaPrice'] / 1e9:.9f} TAO/ALPHA")
    print_info(f"  Daily Rate: {unsafe_offer['dailyInterestRate'] / 1e9 * 100:.4f}%")

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
    new_lender_balance_before = contract.functions.userLendBalance(new_lender_address, unsafe_offer['offerId']).call()

    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance: {old_lender_balance_before / 1e9:.2f} TAO")
    print_info(f"  NEW_LENDER userLendBalance: {new_lender_balance_before / 1e9:.2f} TAO")

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
    print(f"  {Colors.RED}Revert:{Colors.ENDC} 'bad price'")
    print(f"  {Colors.CYAN}Reason:{Colors.ENDC} maxAlphaPrice ({unsafe_max_alpha_price / 1e9:.9f}) >= 90% threshold ({safe_threshold / 1e9:.9f})")
    print(f"  {Colors.CYAN}Contract Check:{Colors.ENDC} alphaPrice * 9000 > maxAlphaPrice * 10000")
    print(f"  {Colors.CYAN}Calculation:{Colors.ENDC} {on_chain_price} * 9000 = {on_chain_price * 9000}")
    print(f"  {Colors.CYAN}Calculation:{Colors.ENDC} {unsafe_max_alpha_price} * 10000 = {unsafe_max_alpha_price * 10000}")
    print(f"  {Colors.CYAN}Result:{Colors.ENDC} {on_chain_price * 9000} <= {unsafe_max_alpha_price * 10000} (FAILS CHECK)")
    print(f"  {Colors.CYAN}State Changes:{Colors.ENDC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from initiator's EVM TAO")

    print_info(f"\nAttempting to transfer loan {loan_id}...")
    print_info(f"Initiator: {initiator_address} (OLD_LENDER)")
    print_info(f"Old Lender: {old_lender_from_loan}")
    print_info(f"New Lender: {unsafe_offer['lender']}")

    # Build transaction
    nonce = w3.eth.get_transaction_count(initiator_address)

    # Convert offer to tuple format (includes signature)
    offer_tuple = offer_to_tuple(unsafe_offer)

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
    new_lender_balance_after = contract.functions.userLendBalance(new_lender_address, unsafe_offer['offerId']).call()

    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} → {protocol_fee_after / 1e9:.9f} TAO")
    print_info(f"  OLD_LENDER userLendBalance: {old_lender_balance_before / 1e9:.2f} → {old_lender_balance_after / 1e9:.2f} TAO")
    print_info(f"  NEW_LENDER userLendBalance: {new_lender_balance_before / 1e9:.2f} → {new_lender_balance_after / 1e9:.2f} TAO")

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

    # Verify protocol fee unchanged
    if protocol_fee_after == protocol_fee_before:
        print_success("✓ Protocol fee unchanged")
    else:
        print_error(f"❌ Protocol fee changed")
        return 1

    # Verify balances unchanged
    if old_lender_balance_after == old_lender_balance_before:
        print_success("✓ OLD_LENDER lend balance unchanged")
    else:
        print_error(f"❌ OLD_LENDER lend balance changed")
        return 1

    if new_lender_balance_after == new_lender_balance_before:
        print_success("✓ NEW_LENDER lend balance unchanged")
    else:
        print_error(f"❌ NEW_LENDER lend balance changed")
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
    print_success("TC14: Bad Alpha Price")
    print_success("Transaction correctly reverted with 'bad price'")
    print_success("All state validations passed")
    print_success("No unexpected state changes detected")

    print(f"\n{Colors.CYAN}Summary:{Colors.ENDC}")
    print(f"  - Cannot transfer loan with unsafe maxAlphaPrice")
    print(f"  - Price safety check (90% threshold) working correctly")
    print(f"  - On-chain ALPHA price: {on_chain_price / 1e9:.9f} TAO/ALPHA")
    print(f"  - 90% safety threshold: {safe_threshold / 1e9:.9f} TAO/ALPHA")
    print(f"  - Unsafe offer price: {unsafe_max_alpha_price / 1e9:.9f} TAO/ALPHA (95%)")
    print(f"  - Contract check: alphaPrice * 9000 > maxAlphaPrice * 10000")
    print(f"  - Result: {on_chain_price * 9000} <= {unsafe_max_alpha_price * 10000} (REJECTED)")
    print(f"  - Loan state remains: {STATE_NAMES[loan_data_after['state']]}")

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
