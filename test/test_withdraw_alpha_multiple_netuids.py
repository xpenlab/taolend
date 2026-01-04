#!/usr/bin/env python3
"""
Test Case TC30: withdrawAlpha() - Multiple Netuids
Objective: Verify withdrawAlpha works correctly across multiple netuids
Tests: Withdraw from netuid=2 and netuid=3, verify both succeed independently

Strategy: 8-step testing pattern with BalanceChecker
Expected: Both withdrawals succeed, balances update correctly per netuid
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

def main():
    print_section("Test Case TC30: withdrawAlpha() - Multiple Netuids")
    print(f"{CYAN}Objective:{NC} Verify withdrawAlpha works correctly across multiple netuids")
    print(f"{CYAN}Strategy:{NC} Withdraw from netuid=2 and netuid=3, verify both succeed")
    print(f"{CYAN}Expected:{NC} Both withdrawals succeed independently\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
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

    # Test parameters - withdraw from two different netuids
    test_netuids = [2, 3]
    withdraw_amounts = {
        2: 30 * 10**9,  # 30 ALPHA from netuid 2
        3: 40 * 10**9   # 40 ALPHA from netuid 3
    }

    print_info(f"\nTest Parameters:")
    print_info(f"  User: {user_label} ({user_address})")
    print_info(f"  Netuids: {test_netuids}")
    print_info(f"  Withdraw from netuid=2: {withdraw_amounts[2] / 1e9:.2f} ALPHA")
    print_info(f"  Withdraw from netuid=3: {withdraw_amounts[3] / 1e9:.2f} ALPHA")

    # ========================================================================
    # STEP 0: Verify Setup & Prepare
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions & Preparation")

    user_registered = contract.functions.registeredUser(user_address).call()
    if not user_registered:
        print_error(f"SETUP ERROR: {user_label} not registered")
        sys.exit(1)
    print_success(f"✓ {user_label} is registered")

    # Check and prepare balances for both netuids
    from substrateinterface import Keypair
    delegate_hotkey_ss58 = ANOTHER_HOTKEY
    kp = Keypair(ss58_address=delegate_hotkey_ss58)
    delegate_hotkey = bytes(kp.public_key)

    for netuid in test_netuids:
        subnet_active = contract.functions.activeSubnets(netuid).call()
        if not subnet_active:
            print_error(f"SETUP ERROR: Subnet {netuid} not active")
            sys.exit(1)
        print_success(f"✓ Subnet {netuid} is active")

        user_balance = contract.functions.userAlphaBalance(user_address, netuid).call()
        withdraw_amount = withdraw_amounts[netuid]

        print_info(f"Netuid {netuid} balance: {user_balance / 1e9:.2f} ALPHA")

        if user_balance < withdraw_amount:
            print_warning(f"⚠ Insufficient balance in netuid {netuid}, depositing...")
            deposit_amount = 100 * 10**9

            try:
                nonce = w3.eth.get_transaction_count(user_address)
                tx = contract.functions.depositAlpha(
                    netuid, deposit_amount, delegate_hotkey
                ).build_transaction({
                    'from': user_address,
                    'nonce': nonce,
                    'gas': 500000,
                    'gasPrice': w3.eth.gas_price,
                    'chainId': chain_id
                })
                signed_tx = w3.eth.account.sign_transaction(tx, user_private_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

                if receipt['status'] == 1:
                    print_success(f"✓ Deposited {deposit_amount / 1e9:.2f} ALPHA to netuid {netuid}")
                else:
                    print_error(f"Deposit failed for netuid {netuid}")
                    sys.exit(1)
            except Exception as e:
                print_error(f"Failed to deposit to netuid {netuid}: {e}")
                sys.exit(1)

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0] + test_netuids)
    addresses_list = [
        {"address": user_address, "label": user_label},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Query initial state for both netuids
    initial_state = {}
    for netuid in test_netuids:
        initial_state[netuid] = {
            'subnet_balance': contract.functions.subnetAlphaBalance(netuid).call(),
            'user_balance': contract.functions.userAlphaBalance(user_address, netuid).call()
        }
        print_info(f"\nNetuid {netuid} Initial State:")
        print_info(f"  subnetAlphaBalance[{netuid}]: {initial_state[netuid]['subnet_balance'] / 1e9:.2f} ALPHA")
        print_info(f"  userAlphaBalance[{user_label}][{netuid}]: {initial_state[netuid]['user_balance'] / 1e9:.2f} ALPHA")

    # STEP 2-3
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    print_section("Step 3: Read Initial Loan State")
    print_info("N/A - withdraw operations do not involve loans")

    # ========================================================================
    # STEP 4: Execute withdrawAlpha() from Multiple Netuids
    # ========================================================================
    print_section("Step 4: Execute withdrawAlpha() from Multiple Netuids")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Both withdrawals succeed")
    for netuid in test_netuids:
        print(f"  {CYAN}Netuid {netuid}:{NC}")
        print(f"    - userAlphaBalance: {initial_state[netuid]['user_balance'] / 1e9:.2f} → {(initial_state[netuid]['user_balance'] - withdraw_amounts[netuid]) / 1e9:.2f} ALPHA")
        print(f"    - subnetAlphaBalance: {initial_state[netuid]['subnet_balance'] / 1e9:.2f} → {(initial_state[netuid]['subnet_balance'] - withdraw_amounts[netuid]) / 1e9:.2f} ALPHA")
    print()

    tx_receipts = {}

    # Withdraw from netuid 2
    print_info(f"[1/2] Withdrawing {withdraw_amounts[2] / 1e9:.2f} ALPHA from netuid 2...")
    try:
        nonce = w3.eth.get_transaction_count(user_address)
        tx = contract.functions.withdrawAlpha(2, withdraw_amounts[2]).build_transaction({
            'from': user_address,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price,
            'chainId': chain_id
        })
        signed_tx = w3.eth.account.sign_transaction(tx, user_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        tx_receipts[2] = receipt

        if receipt['status'] == 1:
            print_success(f"✓ Withdrawal from netuid 2 succeeded (block {receipt['blockNumber']}, gas: {receipt['gasUsed']})")
        else:
            print_error("✗ Withdrawal from netuid 2 failed!")
            return 1
    except Exception as e:
        print_error(f"Error withdrawing from netuid 2: {e}")
        return 1

    # Withdraw from netuid 3
    print_info(f"[2/2] Withdrawing {withdraw_amounts[3] / 1e9:.2f} ALPHA from netuid 3...")
    try:
        nonce = w3.eth.get_transaction_count(user_address)
        tx = contract.functions.withdrawAlpha(3, withdraw_amounts[3]).build_transaction({
            'from': user_address,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price,
            'chainId': chain_id
        })
        signed_tx = w3.eth.account.sign_transaction(tx, user_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        tx_receipts[3] = receipt

        if receipt['status'] == 1:
            print_success(f"✓ Withdrawal from netuid 3 succeeded (block {receipt['blockNumber']}, gas: {receipt['gasUsed']})")
        else:
            print_error("✗ Withdrawal from netuid 3 failed!")
            return 1
    except Exception as e:
        print_error(f"Error withdrawing from netuid 3: {e}")
        return 1

    # ========================================================================
    # STEP 5-7: Final State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final state
    final_state = {}
    for netuid in test_netuids:
        final_state[netuid] = {
            'subnet_balance': contract.functions.subnetAlphaBalance(netuid).call(),
            'user_balance': contract.functions.userAlphaBalance(user_address, netuid).call()
        }
        print_info(f"\nNetuid {netuid} Final State:")
        print_info(f"  subnetAlphaBalance: {initial_state[netuid]['subnet_balance'] / 1e9:.2f} → {final_state[netuid]['subnet_balance'] / 1e9:.2f} ALPHA")
        print_info(f"  userAlphaBalance: {initial_state[netuid]['user_balance'] / 1e9:.2f} → {final_state[netuid]['user_balance'] / 1e9:.2f} ALPHA")

    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    print_section("Step 7: Read Final Loan State")
    print_info("N/A - withdraw operations do not involve loans")

    # ========================================================================
    # STEP 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    print_info("Verifying test expectations...")
    all_checks_passed = True

    # Verify each netuid independently
    for netuid in test_netuids:
        print_info(f"\nVerifying netuid {netuid}:")

        # User balance
        expected_user = initial_state[netuid]['user_balance'] - withdraw_amounts[netuid]
        actual_user = final_state[netuid]['user_balance']
        if actual_user != expected_user:
            print_error(f"✗ User balance mismatch for netuid {netuid}!")
            print_error(f"  Expected: {expected_user / 1e9:.2f} ALPHA")
            print_error(f"  Actual: {actual_user / 1e9:.2f} ALPHA")
            all_checks_passed = False
        else:
            print_success(f"✓ User balance correct: {initial_state[netuid]['user_balance'] / 1e9:.2f} → {actual_user / 1e9:.2f} ALPHA")

        # Subnet balance
        expected_subnet = initial_state[netuid]['subnet_balance'] - withdraw_amounts[netuid]
        actual_subnet = final_state[netuid]['subnet_balance']
        if actual_subnet != expected_subnet:
            print_error(f"✗ Subnet balance mismatch for netuid {netuid}!")
            all_checks_passed = False
        else:
            print_success(f"✓ Subnet balance correct: {initial_state[netuid]['subnet_balance'] / 1e9:.2f} → {actual_subnet / 1e9:.2f} ALPHA")

    # Print balance changes
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC30 TEST PASSED ✓✓✓")
        print_success("withdrawAlpha() from multiple netuids executed successfully")
        print_success("All state validations passed")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Withdrew from 2 different netuids independently")
        print(f"  - Netuid 2: {withdraw_amounts[2] / 1e9:.2f} ALPHA (gas: {tx_receipts[2]['gasUsed']})")
        print(f"  - Netuid 3: {withdraw_amounts[3] / 1e9:.2f} ALPHA (gas: {tx_receipts[3]['gasUsed']})")
        print(f"  - Both withdrawals succeeded independently")

        return 0
    else:
        print_error("✗✗✗ TC30 TEST FAILED ✗✗✗")
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
