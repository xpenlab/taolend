#!/usr/bin/env python3
"""
Test Case TC10: withdrawTao() - Multiple Withdrawals
Objective: Verify withdrawTao works correctly with multiple sequential withdrawals
Tests: Perform 3 withdrawals in sequence by same user

Strategy: 8-step testing pattern with BalanceChecker
Expected: All transactions succeed, balances update correctly
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
    print_section("Test Case TC10: withdrawTao() - Multiple Withdrawals")
    print(f"{CYAN}Objective:{NC} Verify withdrawTao works correctly with multiple sequential withdrawals")
    print(f"{CYAN}Strategy:{NC} Perform 3 withdrawals of 2 TAO each and verify state changes")
    print(f"{CYAN}Expected:{NC} All transactions succeed, balances update correctly\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()

    # Use LENDER1 as registered user
    registered_address = addresses['LENDER1']['evmAddress']
    registered_private_key = os.environ.get("LENDER1_PRIVATE_KEY")
    registered_label = 'LENDER1'

    if not registered_private_key:
        print_error(f"SETUP ERROR: LENDER1_PRIVATE_KEY not found in .env")
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

    # Test parameters - Multiple withdrawals
    num_withdrawals = 3
    withdraw_amount_rao = 2 * 10**9  # 2 TAO per withdrawal
    total_withdraw_rao = withdraw_amount_rao * num_withdrawals  # 6 TAO total

    print_info(f"\nTest Parameters:")
    print_info(f"  Registered User: {registered_label} ({registered_address})")
    print_info(f"  Number of Withdrawals: {num_withdrawals}")
    print_info(f"  Amount per Withdrawal: {withdraw_amount_rao / 1e9:.2f} TAO")
    print_info(f"  Total Withdrawal: {total_withdraw_rao / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check user is registered
    user_registered = contract.functions.registeredUser(registered_address).call()
    if not user_registered:
        print_error(f"SETUP ERROR: {registered_label} is not registered")
        print_info(f"Please register {registered_label}:")
        print_info(f"  {YELLOW}python3 scripts/cli.py register --account {registered_label}{NC}")
        sys.exit(1)
    print_success(f"✓ {registered_label} registered: {registered_address}")

    # Check user has sufficient balance
    user_contract_balance = contract.functions.userAlphaBalance(registered_address, 0).call()
    if user_contract_balance < total_withdraw_rao:
        print_error(f"SETUP ERROR: Insufficient contract balance for multiple withdrawals")
        print_error(f"  Current balance: {user_contract_balance / 1e9:.2f} TAO")
        print_error(f"  Required balance: {total_withdraw_rao / 1e9:.2f} TAO")
        print_info(f"Please deposit more TAO first:")
        print_info(f"  {YELLOW}python3 scripts/cli.py deposit-tao --account {registered_label} --amount 10{NC}")
        sys.exit(1)
    print_success(f"✓ User has sufficient contract balance: {user_contract_balance / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0])

    addresses_list = [
        {"address": registered_address, "label": registered_label},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    protocol_fee_before = contract.functions.protocolFeeAccumulated().call()
    subnet_balance_before = contract.functions.subnetAlphaBalance(0).call()

    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} TAO")
    print_info(f"  subnetAlphaBalance[0]: {subnet_balance_before / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("N/A - withdrawal operations do not involve loans")

    # ========================================================================
    # STEP 4: Execute Multiple withdrawTao()
    # ========================================================================
    print_section("Step 4: Execute Multiple withdrawTao()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} All {num_withdrawals} transactions succeed")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - User's contract balance: -{total_withdraw_rao / 1e9:.2f} TAO total")
    print(f"    - Contract's subnetAlphaBalance[0]: -{total_withdraw_rao / 1e9:.2f} TAO total")
    print(f"    - User's EVM TAO: +{total_withdraw_rao / 1e9:.2f} TAO (minus gas)")
    print()

    tx_receipts = []
    total_gas_used = 0

    for i in range(num_withdrawals):
        print_info(f"\n{'=' * 60}")
        print_info(f"Withdrawal #{i+1}/{num_withdrawals}: {withdraw_amount_rao / 1e9:.2f} TAO")
        print_info(f"{'=' * 60}")

        try:
            nonce = w3.eth.get_transaction_count(registered_address)
            gas_price = w3.eth.gas_price

            tx = contract.functions.withdrawTao(withdraw_amount_rao).build_transaction({
                'from': registered_address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': chain_id
            })

            signed_tx = w3.eth.account.sign_transaction(tx, registered_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print_info(f"Transaction sent: {tx_hash.hex()}")

            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

            if tx_receipt['status'] == 1:
                print_success(f"✓ Withdrawal #{i+1} succeeded")
                tx_receipts.append(tx_receipt)
                total_gas_used += tx_receipt['gasUsed'] * tx_receipt['effectiveGasPrice']
            else:
                print_error(f"✗ Withdrawal #{i+1} reverted unexpectedly!")
                sys.exit(1)

        except Exception as e:
            print_error(f"✗ Withdrawal #{i+1} failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print_success(f"\n✓ All {num_withdrawals} withdrawals completed successfully")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final state
    protocol_fee_after = contract.functions.protocolFeeAccumulated().call()
    subnet_balance_after = contract.functions.subnetAlphaBalance(0).call()

    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_before / 1e9:.9f} → {protocol_fee_after / 1e9:.9f} TAO")
    print_info(f"  subnetAlphaBalance[0]: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info("N/A - withdrawal operations do not involve loans")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    print_info("Verifying test expectations...")

    all_checks_passed = True

    # 1. Verify all transactions succeeded
    if len(tx_receipts) != num_withdrawals:
        print_error(f"✗ Not all transactions completed!")
        print_error(f"  Expected: {num_withdrawals} withdrawals")
        print_error(f"  Completed: {len(tx_receipts)} withdrawals")
        all_checks_passed = False
    else:
        print_success(f"✓ All {num_withdrawals} withdrawals succeeded")

    # 2. Verify protocol fee unchanged
    if protocol_fee_after != protocol_fee_before:
        print_error(f"✗ Protocol fee changed unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Protocol fee unchanged")

    # 3. Verify total user balance decreased by total amount
    user_contract_before = snapshot_before['balances'][registered_label]['contract'].get('netuid_0', {})
    user_contract_after = snapshot_after['balances'][registered_label]['contract'].get('netuid_0', {})

    user_balance_before = user_contract_before.get('balance_rao', 0)
    user_balance_after = user_contract_after.get('balance_rao', 0)

    expected_user_balance = user_balance_before - total_withdraw_rao

    if user_balance_after != expected_user_balance:
        print_error(f"✗ User contract balance incorrect!")
        print_error(f"  Expected: {expected_user_balance / 1e9:.2f} TAO")
        print_error(f"  Actual:   {user_balance_after / 1e9:.2f} TAO")
        all_checks_passed = False
    else:
        print_success(f"✓ User contract balance decreased by {total_withdraw_rao / 1e9:.2f} TAO total")

    # 4. Verify subnet balance decreased correctly
    expected_subnet_balance = subnet_balance_before - total_withdraw_rao
    if subnet_balance_after != expected_subnet_balance:
        print_error(f"✗ Subnet balance incorrect!")
        print_error(f"  Expected: {expected_subnet_balance / 1e9:.2f} TAO")
        print_error(f"  Actual:   {subnet_balance_after / 1e9:.2f} TAO")
        all_checks_passed = False
    else:
        print_success(f"✓ Subnet balance decreased by {total_withdraw_rao / 1e9:.2f} TAO total")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC10 TEST PASSED ✓✓✓")
        print_success("Multiple withdrawTao() executed successfully")
        print_success("All state validations passed")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Number of withdrawals: {num_withdrawals}")
        print(f"  - Amount per withdrawal: {withdraw_amount_rao / 1e9:.2f} TAO")
        print(f"  - Total withdrawn: {total_withdraw_rao / 1e9:.2f} TAO")
        print(f"  - User balance: {user_balance_before / 1e9:.2f} → {user_balance_after / 1e9:.2f} TAO")
        print(f"  - Subnet balance: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} TAO")
        print(f"  - Total gas used: {sum(r['gasUsed'] for r in tx_receipts)} units")

        return 0
    else:
        print_error("✗✗✗ TC10 TEST FAILED ✗✗✗")
        print_error("Some verifications failed")
        return 1

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
