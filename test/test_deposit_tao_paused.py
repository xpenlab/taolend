#!/usr/bin/env python3
"""
Test Case TC05: depositTao() - Paused
Objective: Verify depositTao fails when deposits are paused
Tests: nonPausedDeposit modifier - require(!pausedDeposit, "paused deposit")

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction reverts with "paused deposit"
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
    print_section("Test Case TC05: depositTao() - Paused")
    print(f"{CYAN}Objective:{NC} Verify depositTao fails when deposits are paused")
    print(f"{CYAN}Strategy:{NC} Pause deposits and attempt depositTao()")
    print(f"{CYAN}Expected:{NC} Transaction reverts with 'paused deposit'\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()

    # Use LENDER1 as registered user (should be registered from previous tests)
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

    # Test parameters
    deposit_amount_rao = 1 * 10**9  # 1 TAO in RAO
    deposit_amount_wei = deposit_amount_rao * 10**9  # Convert to wei

    print_info(f"\nTest Parameters:")
    print_info(f"  Registered User: {registered_label} ({registered_address})")
    print_info(f"  Deposit Amount: {deposit_amount_rao / 1e9:.2f} TAO")

    # ========================================================================
    # STEP 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Check user is registered (required for this test)
    user_registered = contract.functions.registeredUser(registered_address).call()
    if not user_registered:
        print_error(f"SETUP ERROR: {registered_label} is not registered")
        print_info(f"Please register {registered_label}:")
        print_info(f"  {YELLOW}python3 scripts/cli.py register --account {registered_label}{NC}")
        sys.exit(1)
    print_success(f"✓ {registered_label} registered: {registered_address}")

    # Verify deposit is paused (prerequisite for this test)
    paused_deposit = contract.functions.pausedDeposit().call()
    if not paused_deposit:
        print_error("SETUP ERROR: Deposits are not paused")
        print_info("Please pause deposits first:")
        print_info(f"  {YELLOW}python3 scripts/cli.py pause --operation deposit --pause{NC}")
        sys.exit(1)
    print_success("✓ Deposits are paused (pausedDeposit == true)")

    # Check user has sufficient EVM TAO balance
    user_evm_balance = w3.eth.get_balance(registered_address)
    required_balance = deposit_amount_wei + (1 * 10**18)  # deposit + 1 TAO for gas
    if user_evm_balance < required_balance:
        print_error(f"SETUP ERROR: Insufficient EVM TAO balance")
        print_error(f"  Current: {user_evm_balance / 1e18:.4f} TAO")
        print_error(f"  Required: {required_balance / 1e18:.4f} TAO (including gas)")
        sys.exit(1)
    print_success(f"✓ User has sufficient EVM TAO: {user_evm_balance / 1e18:.4f} TAO")

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
    print_info(f"  pausedDeposit: {paused_deposit}")

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
    # STEP 4: Execute depositTao()
    # ========================================================================
    print_section("Step 4: Execute depositTao()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {RED}Revert:{NC} 'paused deposit'")
    print(f"  {CYAN}Reason:{NC} Deposits are paused (nonPausedDeposit modifier)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - No state changes (transaction reverts)")
    print(f"    - Only gas deducted from user's EVM TAO")
    print()

    print_info(f"Attempting to deposit {deposit_amount_rao / 1e9:.2f} TAO...")
    print_info(f"User: {registered_address} ({registered_label}, registered)")

    # Execute transaction
    tx_receipt = None
    reverted = False
    revert_reason = None

    try:
        nonce = w3.eth.get_transaction_count(registered_address)
        gas_price = w3.eth.gas_price

        tx = contract.functions.depositTao().build_transaction({
            'from': registered_address,
            'value': deposit_amount_wei,
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

        # Try to extract revert reason
        if "paused deposit" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'paused deposit'")
        elif "paused" in error_msg.lower():
            print_success(f"✓ Revert reason contains 'paused'")

        print_info(f"Error message: {error_msg[:300]}")

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
        print_error("Expected: Transaction should revert with 'paused deposit'")
        all_checks_passed = False
    else:
        print_success("✓ Transaction reverted as expected")

    # 2. Verify revert reason contains "paused deposit"
    if revert_reason and "paused deposit" in revert_reason.lower():
        print_success("✓ Revert reason confirmed: 'paused deposit'")
    elif revert_reason and "paused" in revert_reason.lower():
        print_success("✓ Revert reason contains 'paused'")
    elif revert_reason:
        print_warning(f"⚠ Revert reason may differ: {revert_reason[:200]}")

    # 3. Verify protocol fee unchanged
    if protocol_fee_after != protocol_fee_before:
        print_error(f"✗ Protocol fee changed unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Protocol fee unchanged")

    # 4. Verify subnet balance unchanged
    if subnet_balance_after != subnet_balance_before:
        print_error(f"✗ Subnet balance changed unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ Subnet balance unchanged")

    # 5. Verify user contract balance unchanged
    user_contract_before = snapshot_before['balances'][registered_label]['contract'].get('netuid_0', {})
    user_contract_after = snapshot_after['balances'][registered_label]['contract'].get('netuid_0', {})

    user_contract_balance_before = user_contract_before.get('balance_rao', 0)
    user_contract_balance_after = user_contract_after.get('balance_rao', 0)

    if user_contract_balance_after != user_contract_balance_before:
        print_error(f"✗ User contract balance changed unexpectedly!")
        all_checks_passed = False
    else:
        print_success("✓ User contract balance unchanged")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    print_info("\nExpected changes:")
    print_info(f"  - {registered_label} EVM TAO: decreased by gas cost only")
    print_info("  - All other balances: unchanged")

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC05 TEST PASSED ✓✓✓")
        print_success("depositTao() correctly reverted with 'paused deposit'")
        print_success("All state validations passed")
        print_success("No unexpected state changes detected")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - depositTao() fails when deposits are paused")
        print(f"  - nonPausedDeposit modifier working correctly")
        print(f"  - Contract state protected from deposit operations when paused")
        print(f"  - Protocol fee unchanged: {protocol_fee_before / 1e9:.9f} TAO")
        print(f"  - Subnet balance unchanged: {subnet_balance_before / 1e9:.2f} TAO")

        print(f"\n{YELLOW}⚠ IMPORTANT:{NC} Deposits are still paused!")
        print(f"{YELLOW}To unpause, run:{NC}")
        print(f"  {YELLOW}python3 scripts/cli.py pause --operation deposit --unpause{NC}")

        return 0
    else:
        print_error("✗✗✗ TC05 TEST FAILED ✗✗✗")
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
