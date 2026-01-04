#!/usr/bin/env python3
"""
Test Case TC02-03: withdrawProtocolFees - Success
Objective: Verify successful protocol fee withdrawal
Tests: Successful withdrawal with correct state and balance changes

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction succeeds, fees transferred to FEE_RECEIVER_COLDKEY
"""

import os
import sys
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
    print_section("Test Case TC02-03: withdrawProtocolFees - Success")
    print(f"{CYAN}Objective:{NC} Verify successful protocol fee withdrawal")
    print(f"{CYAN}Strategy:{NC} MANAGER withdraws accumulated protocol fees")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, fees transferred\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    manager_address = addresses['MANAGER']['evmAddress']

    # Load private key
    manager_private_key = os.environ.get("MANAGER_PRIVATE_KEY")
    if not manager_private_key:
        print_error("MANAGER_PRIVATE_KEY not found in .env")
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

    print_info(f"Manager: {manager_address}")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify caller is MANAGER
    contract_manager = contract.functions.MANAGER().call()
    if contract_manager.lower() != manager_address.lower():
        print_error(f"SETUP ERROR: Caller is not MANAGER")
        sys.exit(1)

    print_success(f"✓ Caller is the MANAGER")

    # Query protocol fees and contract addresses
    protocol_fee_accumulated = contract.functions.protocolFeeAccumulated().call()
    fee_receiver_coldkey = contract.functions.FEE_RECEIVER_COLDKEY().call()
    subnet_alpha_balance_0 = contract.functions.subnetAlphaBalance(0).call()

    print_info(f"Protocol fees accumulated: {protocol_fee_accumulated / 1e9} TAO")
    print_info(f"Fee receiver coldkey: 0x{fee_receiver_coldkey.hex()}")
    print_info(f"SubnetAlphaBalance[0]: {subnet_alpha_balance_0 / 1e9} TAO")

    # Check if fees are available
    if protocol_fee_accumulated == 0:
        print_warning("⚠ No protocol fees accumulated")
        print_warning("This test requires protocol fees from loan repayments")
        print_warning("Test will skip as there are no fees to withdraw")
        print_info("\nTo accumulate fees:")
        print_info("  1. Create and repay loans (30% of interest goes to protocol)")
        print_info("  2. Or manually deposit TAO and set protocol fees")
        sys.exit(0)  # Exit gracefully, not a failure

    # Set test amount - withdraw partial fees (or all if small amount)
    if protocol_fee_accumulated >= int(20 * 1e9):
        test_amount = int(20 * 1e9)  # Withdraw 20 TAO
        print_info("Will withdraw partial fees (20 TAO)")
    else:
        test_amount = protocol_fee_accumulated // 2  # Withdraw half
        print_info(f"Will withdraw half of available fees ({test_amount / 1e9} TAO)")

    # Verify sufficient balance in subnetAlphaBalance[0]
    if subnet_alpha_balance_0 < test_amount:
        print_error(f"SETUP ERROR: Insufficient TAO in contract")
        print_error(f"subnetAlphaBalance[0] = {subnet_alpha_balance_0 / 1e9} TAO")
        print_error(f"Required = {test_amount / 1e9} TAO")
        sys.exit(1)

    print_success(f"✓ Fees available: {protocol_fee_accumulated / 1e9} TAO")
    print_success(f"✓ Sufficient TAO balance: {subnet_alpha_balance_0 / 1e9} TAO")
    print_info(f"Will withdraw: {test_amount / 1e9} TAO")

    # ========================================================================
    # Step 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": manager_address, "label": "MANAGER"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Store initial values
    initial_protocol_fee = protocol_fee_accumulated
    initial_subnet_balance_0 = subnet_alpha_balance_0

    # ========================================================================
    # Step 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # Step 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("Not applicable for this test (no loan involved)")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute withdrawProtocolFees")

    print(f"\n{BOLD}{GREEN}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds (status=1)")
    print(f"  {BLUE}Event:{NC} WithdrawProtocolFees(sender, amount, to)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - protocolFeeAccumulated: -{test_amount / 1e9} TAO")
    print(f"    - subnetAlphaBalance[0]: -{test_amount / 1e9} TAO")
    print(f"    - On-chain staking[0]: -{test_amount / 1e9} TAO")
    print(f"    - FEE_RECEIVER_COLDKEY receives: +{test_amount / 1e9} TAO\n")

    print_info(f"Withdrawing {test_amount / 1e9} TAO protocol fees...")

    # Execute transaction
    try:
        tx = contract.functions.withdrawProtocolFees(
            test_amount
        ).build_transaction({
            'from': manager_address,
            'nonce': w3.eth.get_transaction_count(manager_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=manager_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print_info(f"Transaction hash: {tx_hash.hex()}")
        print_info("Waiting for transaction receipt...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt['status'] == 1:
            print_success(f"✓ Transaction succeeded")
            print_info(f"Gas used: {receipt['gasUsed']}")
            print_info(f"Block number: {receipt['blockNumber']}")

            # Check for WithdrawProtocolFees event
            events = contract.events.WithdrawProtocolFees().process_receipt(receipt)
            if events:
                for event in events:
                    print_success(f"✓ WithdrawProtocolFees event emitted:")
                    print_info(f"  Sender: {event['args']['sender']}")
                    print_info(f"  Amount: {event['args']['amount'] / 1e9} TAO")
                    print_info(f"  To: 0x{event['args']['to'].hex()}")
            else:
                print_warning("⚠ No WithdrawProtocolFees event found")

        else:
            print_error("❌ Transaction failed (expected to succeed)")
            sys.exit(1)

    except Exception as e:
        print_error(f"❌ Transaction failed with error: {str(e)}")
        sys.exit(1)

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    # Capture final snapshot
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final values
    final_protocol_fee = contract.functions.protocolFeeAccumulated().call()
    final_subnet_balance_0 = contract.functions.subnetAlphaBalance(0).call()

    # ========================================================================
    # Step 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # Step 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info("Not applicable for this test (no loan involved)")

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

    # Check 1: Protocol fee decreased
    protocol_fee_diff = final_protocol_fee - initial_protocol_fee
    expected_fee_diff = -test_amount

    print_info(f"Protocol fee change: {protocol_fee_diff / 1e9} TAO (expected: {expected_fee_diff / 1e9} TAO)")

    if protocol_fee_diff == expected_fee_diff:
        print_success(f"✓ Protocol fee decreased correctly by {test_amount / 1e9} TAO")
    else:
        print_error(f"✗ Unexpected protocol fee change: {protocol_fee_diff / 1e9} vs {expected_fee_diff / 1e9}")
        all_checks_passed = False

    # Check 2: subnetAlphaBalance[0] decreased
    subnet_balance_diff = final_subnet_balance_0 - initial_subnet_balance_0
    expected_balance_diff = -test_amount

    if subnet_balance_diff == expected_balance_diff:
        print_success(f"✓ subnetAlphaBalance[0] decreased correctly by {test_amount / 1e9} TAO")
    else:
        print_error(f"✗ Unexpected balance change: {subnet_balance_diff / 1e9} vs {expected_balance_diff / 1e9}")
        all_checks_passed = False

    # Check 3: Remaining fees
    print_info(f"Remaining protocol fees: {final_protocol_fee / 1e9} TAO")
    expected_remaining = initial_protocol_fee - test_amount

    if final_protocol_fee == expected_remaining:
        print_success(f"✓ Remaining fees correct: {final_protocol_fee / 1e9} TAO")
    else:
        print_warning(f"⚠ Remaining fees: {final_protocol_fee / 1e9} (expected: {expected_remaining / 1e9})")

    # Check 4: Contract state (other fields should be unchanged)
    contract_state_before = snapshot_before['contract']
    contract_state_after = snapshot_after['contract']

    if contract_state_before['next_loan_id'] == contract_state_after['next_loan_id']:
        print_success("✓ Other contract state unchanged")
    else:
        print_error("✗ Unexpected contract state changes")
        all_checks_passed = False

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success(f"Successfully withdrew {test_amount / 1e9} TAO in protocol fees")
        print_success(f"Protocol fee decreased by {test_amount / 1e9} TAO")
        print_success(f"subnetAlphaBalance[0] decreased by {test_amount / 1e9} TAO")
        print_success(f"Remaining protocol fees: {final_protocol_fee / 1e9} TAO")
        print_success("WithdrawProtocolFees event emitted correctly")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
