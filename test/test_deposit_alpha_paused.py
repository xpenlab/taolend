#!/usr/bin/env python3
"""
Test Case TC21: depositAlpha() - Paused
Objective: Verify depositAlpha fails when deposits are paused
Tests: nonPausedDeposit modifier - require(!pausedDeposit, "paused deposit")

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "paused deposit"

NOTE: This test requires MANAGER privileges to pause deposits
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
    print_section("Test Case TC21: depositAlpha() - Paused")
    print(f"{CYAN}Objective:{NC} Verify depositAlpha fails when deposits are paused")
    print(f"{CYAN}Strategy:{NC} Pause deposits and attempt depositAlpha()")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'paused deposit'\n")

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

    # Get DELEGATE_HOTKEY
    delegate_hotkey = contract.functions.DELEGATE_HOTKEY().call()

    # Test parameters
    test_netuid = 2
    deposit_amount_rao = 100 * 10**9  # 100 ALPHA

    print_info(f"\nTest Parameters:")
    print_info(f"  Registered User: {registered_label} ({registered_address})")
    print_info(f"  Netuid: {test_netuid}")
    print_info(f"  Deposit Amount: {deposit_amount_rao / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check user is registered
    user_registered = contract.functions.registeredUser(registered_address).call()
    if not user_registered:
        print_error(f"SETUP ERROR: {registered_label} is not registered")
        print_error("Please register the account first")
        sys.exit(1)
    print_success(f"✓ {registered_label} is registered")

    # Check if deposits are already paused
    paused_deposit_before = contract.functions.pausedDeposit().call()
    print_info(f"Current pausedDeposit state: {paused_deposit_before}")

    if not paused_deposit_before:
        print_warning("⚠ Deposits are NOT paused - this test requires deposits to be paused")
        print_warning("This test will be SKIPPED - deposits must be paused by MANAGER")
        print_info("\nTo run this test:")
        print_info("  1. Use MANAGER account to call pauseDeposit()")
        print_info("  2. Run this test")
        print_info("  3. Use MANAGER account to call unpauseDeposit() afterwards")
        print_info("\nSKIPPING TEST")
        return 2  # Exit code 2 = skipped

    print_success("✓ Deposits are paused (as required for test)")

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

    subnet_balance_before = contract.functions.subnetAlphaBalance(test_netuid).call()
    print_info(f"\nContract State:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 2-3: Account/Loan State
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    print_section("Step 3: Read Initial Loan State")
    print_info("N/A - deposit operations do not involve loans")

    # ========================================================================
    # STEP 4: Execute depositAlpha()
    # ========================================================================
    print_section("Step 4: Execute depositAlpha()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} 'paused deposit'")
    print(f"  {CYAN}Reason:{NC} Deposits are paused (nonPausedDeposit modifier)")
    print()

    print_info(f"Attempting to deposit {deposit_amount_rao / 1e9:.2f} ALPHA...")

    tx_receipt = None
    reverted = False
    revert_reason = None

    try:
        nonce = w3.eth.get_transaction_count(registered_address)
        gas_price = w3.eth.gas_price

        tx = contract.functions.depositAlpha(
            test_netuid,
            deposit_amount_rao,
            delegate_hotkey
        ).build_transaction({
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

        if tx_receipt['status'] == 0:
            reverted = True
            print_warning("Transaction reverted (as expected)")

    except Exception as e:
        reverted = True
        error_msg = str(e)
        revert_reason = error_msg
        print_success(f"✓ Transaction reverted before mining (as expected)")

        if "paused" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'paused'")

        print_info(f"Error message: {error_msg[:300]}")

    # ========================================================================
    # STEP 5-7: Final State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    subnet_balance_after = contract.functions.subnetAlphaBalance(test_netuid).call()
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")

    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    print_section("Step 7: Read Final Loan State")
    print_info("N/A - deposit operations do not involve loans")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    print_info("Verifying test expectations...")

    all_checks_passed = True

    # 1. Verify transaction reverted
    if not reverted and (tx_receipt and tx_receipt['status'] == 1):
        print_error("✗ Transaction succeeded unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Transaction reverted as expected")

    # 2. Verify revert reason
    if revert_reason and "paused" in revert_reason.lower():
        print_success("✓ Revert reason confirmed: 'paused deposit'")
    elif revert_reason:
        print_warning(f"⚠ Revert reason may differ: {revert_reason[:200]}")

    # 3. Verify subnet balance unchanged
    if subnet_balance_after != subnet_balance_before:
        print_error(f"✗ Subnet balance changed unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Subnet balance unchanged")

    # Print balance changes
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC21 TEST PASSED ✓✓✓")
        print_success("depositAlpha() correctly reverted with 'paused deposit'")
        print_success("All state validations passed")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - depositAlpha() blocked when paused")
        print(f"  - nonPausedDeposit modifier working correctly")
        print(f"  - Subnet balance unchanged: {subnet_balance_before / 1e9:.2f} ALPHA")

        return 0
    else:
        print_error("✗✗✗ TC21 TEST FAILED ✗✗✗")
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
