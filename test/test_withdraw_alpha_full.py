#!/usr/bin/env python3
"""
Test Case TC29: withdrawAlpha() - Full Withdrawal
Objective: Verify withdrawAlpha works correctly when withdrawing entire balance
Tests: Withdraw 100% of balance and verify balance becomes zero

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction succeeds, balance becomes zero
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
    print_section("Test Case TC29: withdrawAlpha() - Full Withdrawal")
    print(f"{CYAN}Objective:{NC} Verify withdrawAlpha works when withdrawing entire balance")
    print(f"{CYAN}Strategy:{NC} Withdraw 100% of balance and verify balance becomes zero")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, user balance = 0\n")

    # Setup
    print_info("Setting up test environment...")
    addresses = load_addresses()
    user_address = addresses['BORROWER1']['evmAddress']
    user_private_key = os.environ.get("BORROWER1_PRIVATE_KEY")
    user_label = 'BORROWER1'

    if not user_private_key:
        print_error(f"SETUP ERROR: BORROWER1_PRIVATE_KEY not found")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(BITTENSOR_RPC))
    if not w3.is_connected():
        print_error("Failed to connect to Bittensor EVM node")
        sys.exit(1)

    chain_id = w3.eth.chain_id
    print_success(f"Connected to Bittensor EVM (Chain ID: {chain_id})")

    contract_abi = load_contract_abi()
    contract = w3.eth.contract(address=LENDING_POOL_V2_ADDRESS, abi=contract_abi)

    test_netuid = 3

    # STEP 0: Verify Setup
    print_section("Step 0: Verify Setup Conditions")
    
    user_registered = contract.functions.registeredUser(user_address).call()
    if not user_registered:
        print_error(f"SETUP ERROR: {user_label} not registered")
        sys.exit(1)
    print_success(f"✓ {user_label} is registered")

    subnet_active = contract.functions.activeSubnets(test_netuid).call()
    if not subnet_active:
        print_error(f"SETUP ERROR: Subnet {test_netuid} not active")
        sys.exit(1)
    print_success(f"✓ Subnet {test_netuid} is active")

    user_balance = contract.functions.userAlphaBalance(user_address, test_netuid).call()
    print_info(f"Current user balance: {user_balance / 1e9:.2f} ALPHA")

    if user_balance == 0:
        print_error("SETUP ERROR: User has zero balance")
        sys.exit(1)

    withdraw_amount_rao = user_balance  # Withdraw 100%

    print_info(f"\nTest Parameters:")
    print_info(f"  User: {user_label} ({user_address})")
    print_info(f"  Netuid: {test_netuid}")
    print_info(f"  Current Balance: {user_balance / 1e9:.2f} ALPHA")
    print_info(f"  Withdraw Amount: {withdraw_amount_rao / 1e9:.2f} ALPHA (100%)")

    # STEP 1: Read Initial State
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, test_netuid])
    addresses_list = [
        {"address": user_address, "label": user_label},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    subnet_balance_before = contract.functions.subnetAlphaBalance(test_netuid).call()
    user_contract_balance_before = contract.functions.userAlphaBalance(user_address, test_netuid).call()

    print_info(f"\nContract State:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} ALPHA")
    print_info(f"  userAlphaBalance[{user_label}][{test_netuid}]: {user_contract_balance_before / 1e9:.2f} ALPHA")

    # STEP 2-3
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    print_section("Step 3: Read Initial Loan State")
    print_info("N/A - withdraw operations do not involve loans")

    # STEP 4: Execute Full Withdrawal
    print_section("Step 4: Execute withdrawAlpha() - Full Withdrawal")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - userAlphaBalance[{user_label}][{test_netuid}]: {user_contract_balance_before / 1e9:.2f} → 0.00 ALPHA")
    print(f"    - subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} → {(subnet_balance_before - withdraw_amount_rao) / 1e9:.2f} ALPHA")
    print()

    print_info(f"Withdrawing {withdraw_amount_rao / 1e9:.2f} ALPHA (100% - FULL) from netuid {test_netuid}...")

    try:
        nonce = w3.eth.get_transaction_count(user_address)
        gas_price = w3.eth.gas_price

        tx = contract.functions.withdrawAlpha(test_netuid, withdraw_amount_rao).build_transaction({
            'from': user_address,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': gas_price,
            'chainId': chain_id
        })

        signed_tx = w3.eth.account.sign_transaction(tx, user_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        if tx_receipt['status'] == 1:
            print_success(f"✓ Transaction succeeded")
            print_info(f"Gas used: {tx_receipt['gasUsed']}")
        else:
            print_error("✗ Transaction failed!")
            return 1

    except Exception as e:
        print_error(f"Transaction error: {e}")
        return 1

    # STEP 5-7: Final State
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    subnet_balance_after = contract.functions.subnetAlphaBalance(test_netuid).call()
    user_contract_balance_after = contract.functions.userAlphaBalance(user_address, test_netuid).call()

    print_info(f"\nContract State After:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")
    print_info(f"  userAlphaBalance[{user_label}][{test_netuid}]: {user_contract_balance_before / 1e9:.2f} → {user_contract_balance_after / 1e9:.2f} ALPHA")

    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    print_section("Step 7: Read Final Loan State")
    print_info("N/A - withdraw operations do not involve loans")

    # STEP 8: Verify
    print_section("Step 8: Compare and Verify")

    print_info("Verifying test expectations...")
    all_checks_passed = True

    # 1. Verify user balance is zero
    if user_contract_balance_after != 0:
        print_error(f"✗ User balance not zero!")
        print_error(f"  Expected: 0.00 ALPHA")
        print_error(f"  Actual: {user_contract_balance_after / 1e9:.2f} ALPHA")
        all_checks_passed = False
    else:
        print_success(f"✓ User contract balance is zero: {user_contract_balance_before / 1e9:.2f} → 0.00 ALPHA")
        print_success(f"✓ Full withdrawal (100%) successful")

    # 2. Verify subnet balance decreased
    expected_subnet_balance = subnet_balance_before - withdraw_amount_rao
    if subnet_balance_after != expected_subnet_balance:
        print_error(f"✗ Subnet balance mismatch!")
        all_checks_passed = False
    else:
        print_success(f"✓ Subnet balance decreased correctly: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")

    # Print balance changes
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # FINAL RESULT
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC29 TEST PASSED ✓✓✓")
        print_success("withdrawAlpha() full withdrawal executed successfully")
        print_success("All state validations passed")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Withdrew {withdraw_amount_rao / 1e9:.2f} ALPHA (100% - FULL) from netuid {test_netuid}")
        print(f"  - User balance: {user_contract_balance_before / 1e9:.2f} → 0.00 ALPHA")
        print(f"  - Subnet balance: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")
        print(f"  - Gas used: {tx_receipt['gasUsed']}")

        return 0
    else:
        print_error("✗✗✗ TC29 TEST FAILED ✗✗✗")
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
