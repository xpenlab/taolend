#!/usr/bin/env python3
"""
Test Case TC19: depositAlpha() - Multiple Deposits
Objective: Verify depositAlpha works correctly with multiple deposits to same netuid
Tests: Multiple sequential deposits and balance accumulation

Strategy: 8-step testing pattern with BalanceChecker
Expected: All transactions succeed, balances accumulate correctly

Note: Modified from original "multiple netuids" test since only subnet 3 is active.
      Tests multiple deposits to netuid=3 to verify balance accumulation.
"""

import os
import sys
from pathlib import Path
from web3 import Web3

# Setup paths and imports
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from const import LENDING_POOL_V2_ADDRESS, ANOTHER_HOTKEY
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

def ss58_to_bytes32(ss58_address):
    """Convert SS58 address to bytes32"""
    from substrateinterface import Keypair
    kp = Keypair(ss58_address=ss58_address)
    return bytes(kp.public_key)

def main():
    print_section("Test Case TC19: depositAlpha() - Multiple Deposits")
    print(f"{CYAN}Objective:{NC} Verify depositAlpha works correctly with multiple deposits")
    print(f"{CYAN}Strategy:{NC} Perform 3 sequential deposits (50 + 30 + 20 = 100 ALPHA total)")
    print(f"{CYAN}Expected:{NC} All transactions succeed, balances accumulate correctly\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()

    # Use BORROWER1 as registered user
    registered_address = addresses['BORROWER1']['evmAddress']
    registered_private_key = os.environ.get("BORROWER1_PRIVATE_KEY")
    registered_label = 'BORROWER1'

    if not registered_private_key:
        print_error(f"SETUP ERROR: BORROWER1_PRIVATE_KEY not found in .env")
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

    # Test parameters
    test_netuid = 3  # Subnet 3
    deposit_amounts = [50 * 10**9, 30 * 10**9, 20 * 10**9]  # 50, 30, 20 ALPHA
    total_deposit = sum(deposit_amounts)

    # Use ANOTHER_HOTKEY as delegate
    delegate_hotkey_ss58 = ANOTHER_HOTKEY
    delegate_hotkey_bytes = ss58_to_bytes32(delegate_hotkey_ss58)

    print_info(f"\nTest Parameters:")
    print_info(f"  User: {registered_label} ({registered_address})")
    print_info(f"  Netuid: {test_netuid}")
    print_info(f"  Deposit 1: {deposit_amounts[0] / 1e9:.2f} ALPHA")
    print_info(f"  Deposit 2: {deposit_amounts[1] / 1e9:.2f} ALPHA")
    print_info(f"  Deposit 3: {deposit_amounts[2] / 1e9:.2f} ALPHA")
    print_info(f"  Total: {total_deposit / 1e9:.2f} ALPHA")
    print_info(f"  Delegate Hotkey: {delegate_hotkey_ss58}")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check user is registered
    user_registered = contract.functions.registeredUser(registered_address).call()
    if not user_registered:
        print_error(f"SETUP ERROR: {registered_label} is not registered")
        sys.exit(1)
    print_success(f"✓ {registered_label} registered")

    # Check deposit not paused
    paused_deposit = contract.functions.pausedDeposit().call()
    if paused_deposit:
        print_error("SETUP ERROR: Deposits are paused")
        sys.exit(1)
    print_success(f"✓ Deposits not paused")

    # Check subnet is active
    subnet_active = contract.functions.activeSubnets(test_netuid).call()
    if not subnet_active:
        print_error(f"SETUP ERROR: Subnet {test_netuid} is not active")
        sys.exit(1)
    print_success(f"✓ Subnet {test_netuid} is active")

    print_warning(f"\n⚠ IMPORTANT: This test requires {total_deposit / 1e9:.2f} ALPHA staked to {delegate_hotkey_ss58[:10]}... on netuid {test_netuid}")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, test_netuid])

    addresses_list = [
        {"address": registered_address, "label": registered_label},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    subnet_balance_before = contract.functions.subnetAlphaBalance(test_netuid).call()
    user_contract_balance_before = contract.functions.userAlphaBalance(registered_address, test_netuid).call()

    print_info(f"\nContract State:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} ALPHA")
    print_info(f"  userAlphaBalance[{registered_label}][{test_netuid}]: {user_contract_balance_before / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # STEP 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("N/A - deposit operations do not involve loans")

    # ========================================================================
    # STEP 4: Execute Multiple depositAlpha() Calls
    # ========================================================================
    print_section("Step 4: Execute Multiple depositAlpha() Calls")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} All 3 transactions succeed")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - User's contract balance: +{total_deposit / 1e9:.2f} ALPHA (accumulated)")
    print(f"    - Contract's subnetAlphaBalance[{test_netuid}]: +{total_deposit / 1e9:.2f} ALPHA")
    print()

    tx_receipts = []
    gas_used_total = 0

    for i, amount in enumerate(deposit_amounts, 1):
        print_info(f"\nDeposit {i}/{len(deposit_amounts)}: {amount / 1e9:.2f} ALPHA")

        try:
            nonce = w3.eth.get_transaction_count(registered_address)
            gas_price = w3.eth.gas_price

            tx = contract.functions.depositAlpha(
                test_netuid,
                amount,
                delegate_hotkey_bytes
            ).build_transaction({
                'from': registered_address,
                'nonce': nonce,
                'gas': 1000000,
                'gasPrice': gas_price,
                'chainId': chain_id
            })

            signed_tx = w3.eth.account.sign_transaction(tx, registered_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print_info(f"  Transaction sent: {tx_hash.hex()}")

            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            print_info(f"  Transaction mined in block {tx_receipt['blockNumber']}")

            if tx_receipt['status'] == 1:
                print_success(f"  ✓ Deposit {i} succeeded (Gas: {tx_receipt['gasUsed']} units)")
                tx_receipts.append(tx_receipt)
                gas_used_total += tx_receipt['gasUsed']
            else:
                print_error(f"  ✗ Deposit {i} reverted!")
                sys.exit(1)

        except Exception as e:
            print_error(f"  ✗ Deposit {i} failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print_success(f"\n✓ All {len(deposit_amounts)} deposits completed successfully")
    print_info(f"Total gas used: {gas_used_total} units")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final state
    subnet_balance_after = contract.functions.subnetAlphaBalance(test_netuid).call()
    user_contract_balance_after = contract.functions.userAlphaBalance(registered_address, test_netuid).call()

    print_info(f"\nContract State After:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")
    print_info(f"  userAlphaBalance[{registered_label}][{test_netuid}]: {user_contract_balance_before / 1e9:.2f} → {user_contract_balance_after / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # STEP 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info("N/A - deposit operations do not involve loans")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    print_info("Verifying test expectations...")

    all_checks_passed = True

    # 1. Verify all transactions succeeded
    if len(tx_receipts) != len(deposit_amounts):
        print_error(f"✗ Not all transactions completed!")
        all_checks_passed = False
    else:
        print_success(f"✓ All {len(deposit_amounts)} transactions succeeded")

    # 2. Verify subnet balance increased by total
    expected_subnet_balance = subnet_balance_before + total_deposit
    if subnet_balance_after != expected_subnet_balance:
        print_error(f"✗ Subnet balance incorrect!")
        print_error(f"  Expected: {expected_subnet_balance / 1e9:.2f} ALPHA")
        print_error(f"  Actual:   {subnet_balance_after / 1e9:.2f} ALPHA")
        all_checks_passed = False
    else:
        print_success(f"✓ Subnet balance increased by {total_deposit / 1e9:.2f} ALPHA (accumulated)")

    # 3. Verify user contract balance increased by total
    expected_user_balance = user_contract_balance_before + total_deposit
    if user_contract_balance_after != expected_user_balance:
        print_error(f"✗ User contract balance incorrect!")
        print_error(f"  Expected: {expected_user_balance / 1e9:.2f} ALPHA")
        print_error(f"  Actual:   {user_contract_balance_after / 1e9:.2f} ALPHA")
        all_checks_passed = False
    else:
        print_success(f"✓ User contract balance increased by {total_deposit / 1e9:.2f} ALPHA (accumulated)")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC19 TEST PASSED ✓✓✓")
        print_success("Multiple depositAlpha() calls executed successfully")
        print_success("All state validations passed")
        print_success("Balance accumulation works correctly")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Number of deposits: {len(deposit_amounts)}")
        print(f"  - Deposit amounts: {', '.join([f'{amt/1e9:.2f}' for amt in deposit_amounts])} ALPHA")
        print(f"  - Total deposited: {total_deposit / 1e9:.2f} ALPHA")
        print(f"  - Netuid: {test_netuid}")
        print(f"  - User contract balance: {user_contract_balance_before / 1e9:.2f} → {user_contract_balance_after / 1e9:.2f} ALPHA")
        print(f"  - Contract subnet balance: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")
        print(f"  - Total gas used: {gas_used_total} units")

        return 0
    else:
        print_error("✗✗✗ TC19 TEST FAILED ✗✗✗")
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
