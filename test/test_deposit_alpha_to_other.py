#!/usr/bin/env python3
"""
Test Case TC17: depositAlpha() - Deposit to Other Address (Version 2)
Objective: Verify depositAlpha works when depositing to another user's account
Tests: depositAlpha(netuid, amount, delegateHotkey, _to) - 4 parameter version

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction succeeds, recipient balance increases, sender pays gas

Note: This tests the version 2 function with _to parameter at line 138-149
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
    print_section("Test Case TC17: depositAlpha() - Deposit to Other Address")
    print(f"{CYAN}Objective:{NC} Verify depositAlpha works when depositing to another user")
    print(f"{CYAN}Strategy:{NC} BORROWER1 deposits 100 ALPHA to BORROWER2's account")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, BORROWER2 balance increases\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()

    # Sender: BORROWER1 (has ALPHA staked)
    sender_address = addresses['BORROWER1']['evmAddress']
    sender_private_key = os.environ.get("BORROWER1_PRIVATE_KEY")
    sender_label = 'BORROWER1'

    # Recipient: BORROWER2
    recipient_address = addresses['BORROWER2']['evmAddress']
    recipient_label = 'BORROWER2'

    if not sender_private_key:
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
    deposit_amount_rao = 100 * 10**9  # 100 ALPHA

    # Use ANOTHER_HOTKEY as delegate
    delegate_hotkey_ss58 = ANOTHER_HOTKEY
    delegate_hotkey_bytes = ss58_to_bytes32(delegate_hotkey_ss58)

    print_info(f"\nTest Parameters:")
    print_info(f"  Sender: {sender_label} ({sender_address})")
    print_info(f"  Recipient: {recipient_label} ({recipient_address})")
    print_info(f"  Netuid: {test_netuid}")
    print_info(f"  Deposit Amount: {deposit_amount_rao / 1e9:.2f} ALPHA")
    print_info(f"  Delegate Hotkey: {delegate_hotkey_ss58}")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check sender is registered
    sender_registered = contract.functions.registeredUser(sender_address).call()
    if not sender_registered:
        print_error(f"SETUP ERROR: {sender_label} is not registered")
        sys.exit(1)
    print_success(f"✓ {sender_label} registered")

    # Check recipient is registered
    recipient_registered = contract.functions.registeredUser(recipient_address).call()
    if not recipient_registered:
        print_error(f"SETUP ERROR: {recipient_label} is not registered")
        print_info(f"Please register {recipient_label}:")
        print_info(f"  {YELLOW}python3 scripts/cli.py register --account {recipient_label}{NC}")
        sys.exit(1)
    print_success(f"✓ {recipient_label} registered")

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

    print_warning(f"\n⚠ IMPORTANT: This test requires {deposit_amount_rao / 1e9:.2f} ALPHA staked to {delegate_hotkey_ss58[:10]}... on netuid {test_netuid}")

    # ========================================================================
    # STEP 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(w3, contract, test_netuids=[0, test_netuid])

    addresses_list = [
        {"address": sender_address, "label": sender_label},
        {"address": recipient_address, "label": recipient_label},
        {"address": LENDING_POOL_V2_ADDRESS, "label": "CONTRACT"}
    ]

    print_info("Capturing initial state snapshot...")
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Query specific state
    subnet_balance_before = contract.functions.subnetAlphaBalance(test_netuid).call()
    sender_balance_before = contract.functions.userAlphaBalance(sender_address, test_netuid).call()
    recipient_balance_before = contract.functions.userAlphaBalance(recipient_address, test_netuid).call()

    print_info(f"\nContract State:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} ALPHA")
    print_info(f"  {sender_label} balance: {sender_balance_before / 1e9:.2f} ALPHA")
    print_info(f"  {recipient_label} balance: {recipient_balance_before / 1e9:.2f} ALPHA")

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
    # STEP 4: Execute depositAlpha() to other address
    # ========================================================================
    print_section("Step 4: Execute depositAlpha() to Other Address")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - {sender_label} pays gas (EVM TAO decreases)")
    print(f"    - {recipient_label} contract balance: +{deposit_amount_rao / 1e9:.2f} ALPHA")
    print(f"    - Contract subnetAlphaBalance[{test_netuid}]: +{deposit_amount_rao / 1e9:.2f} ALPHA")
    print(f"    - ALPHA transferred from {sender_label}'s stake to contract")
    print()

    print_info(f"{sender_label} depositing {deposit_amount_rao / 1e9:.2f} ALPHA to {recipient_label}...")

    # Execute transaction
    tx_receipt = None

    try:
        nonce = w3.eth.get_transaction_count(sender_address)
        gas_price = w3.eth.gas_price

        tx = contract.functions.depositAlpha(
            test_netuid,
            deposit_amount_rao,
            delegate_hotkey_bytes,
            recipient_address  # 4th parameter: deposit to recipient
        ).build_transaction({
            'from': sender_address,
            'nonce': nonce,
            'gas': 1500000,
            'gasPrice': gas_price,
            'chainId': chain_id
        })

        signed_tx = w3.eth.account.sign_transaction(tx, sender_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print_info(f"Transaction sent: {tx_hash.hex()}")

        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print_info(f"Transaction mined in block {tx_receipt['blockNumber']}")

        if tx_receipt['status'] == 1:
            print_success("✓ Transaction succeeded")
        else:
            print_error("✗ Transaction reverted unexpectedly!")
            sys.exit(1)

    except Exception as e:
        print_error(f"✗ Transaction failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final state
    subnet_balance_after = contract.functions.subnetAlphaBalance(test_netuid).call()
    sender_balance_after = contract.functions.userAlphaBalance(sender_address, test_netuid).call()
    recipient_balance_after = contract.functions.userAlphaBalance(recipient_address, test_netuid).call()

    print_info(f"\nContract State After:")
    print_info(f"  subnetAlphaBalance[{test_netuid}]: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")
    print_info(f"  {sender_label} balance: {sender_balance_before / 1e9:.2f} → {sender_balance_after / 1e9:.2f} ALPHA")
    print_info(f"  {recipient_label} balance: {recipient_balance_before / 1e9:.2f} → {recipient_balance_after / 1e9:.2f} ALPHA")

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

    # 1. Verify transaction succeeded
    if tx_receipt['status'] != 1:
        print_error("✗ Transaction failed unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Transaction succeeded")

    # 2. Verify subnet balance increased
    expected_subnet_balance = subnet_balance_before + deposit_amount_rao
    if subnet_balance_after != expected_subnet_balance:
        print_error(f"✗ Subnet balance incorrect!")
        print_error(f"  Expected: {expected_subnet_balance / 1e9:.2f} ALPHA")
        print_error(f"  Actual:   {subnet_balance_after / 1e9:.2f} ALPHA")
        all_checks_passed = False
    else:
        print_success(f"✓ Subnet balance increased by {deposit_amount_rao / 1e9:.2f} ALPHA")

    # 3. Verify recipient balance increased (not sender!)
    expected_recipient_balance = recipient_balance_before + deposit_amount_rao
    if recipient_balance_after != expected_recipient_balance:
        print_error(f"✗ {recipient_label} balance incorrect!")
        print_error(f"  Expected: {expected_recipient_balance / 1e9:.2f} ALPHA")
        print_error(f"  Actual:   {recipient_balance_after / 1e9:.2f} ALPHA")
        all_checks_passed = False
    else:
        print_success(f"✓ {recipient_label} balance increased by {deposit_amount_rao / 1e9:.2f} ALPHA")

    # 4. Verify sender balance unchanged
    if sender_balance_after != sender_balance_before:
        print_error(f"✗ {sender_label} balance should not change!")
        print_error(f"  Before: {sender_balance_before / 1e9:.2f} ALPHA")
        print_error(f"  After:  {sender_balance_after / 1e9:.2f} ALPHA")
        all_checks_passed = False
    else:
        print_success(f"✓ {sender_label} balance unchanged (only paid gas)")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC17 TEST PASSED ✓✓✓")
        print_success("depositAlpha() to other address executed successfully")
        print_success("All balances updated correctly")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Sender: {sender_label}")
        print(f"  - Recipient: {recipient_label}")
        print(f"  - Deposited: {deposit_amount_rao / 1e9:.2f} ALPHA")
        print(f"  - Netuid: {test_netuid}")
        print(f"  - {recipient_label} balance: {recipient_balance_before / 1e9:.2f} → {recipient_balance_after / 1e9:.2f} ALPHA")
        print(f"  - Contract subnet balance: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")
        print(f"  - Gas used: {tx_receipt['gasUsed']} units (paid by {sender_label})")

        return 0
    else:
        print_error("✗✗✗ TC17 TEST FAILED ✗✗✗")
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
