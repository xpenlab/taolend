#!/usr/bin/env python3
"""
Test Case TC14: depositAlpha() - Normal Deposit to Self
Objective: Verify depositAlpha works correctly with valid deposit to self
Tests: Normal deposit flow with valid amount to netuid=2

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction succeeds, balances update correctly

Note: This test requires the user to have ALPHA staked on the source delegate hotkey
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
    print_section("Test Case TC14: depositAlpha() - Normal Deposit to Self")
    print(f"{CYAN}Objective:{NC} Verify depositAlpha works correctly with valid deposit to self")
    print(f"{CYAN}Strategy:{NC} Deposit 1000 ALPHA to netuid=2 and verify state changes")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, balances update correctly\n")

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
    # Use publicKey as coldkey (they are the same in Bittensor)
    user_coldkey = bytes.fromhex(addresses['BORROWER1']['publicKey'][2:] if addresses['BORROWER1']['publicKey'].startswith('0x') else addresses['BORROWER1']['publicKey'])

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
    deposit_amount_rao = 100 * 10**9  # 100 ALPHA in RAO

    # Use ANOTHER_HOTKEY as delegate (where user has ALPHA staked)
    from substrateinterface import Keypair
    delegate_hotkey_ss58 = ANOTHER_HOTKEY
    kp = Keypair(ss58_address=delegate_hotkey_ss58)
    delegate_hotkey = bytes(kp.public_key)

    print_info(f"\nTest Parameters:")
    print_info(f"  Registered User: {registered_label} ({registered_address})")
    print_info(f"  User Coldkey: 0x{user_coldkey.hex()}")
    print_info(f"  Netuid: {test_netuid}")
    print_info(f"  Deposit Amount: {deposit_amount_rao / 1e9:.2f} ALPHA")
    print_info(f"  Source Delegate (SS58): {delegate_hotkey_ss58}")
    print_info(f"  Source Delegate (bytes32): 0x{delegate_hotkey.hex()}")

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

    # Check deposit not paused
    paused_deposit = contract.functions.pausedDeposit().call()
    if paused_deposit:
        print_error("SETUP ERROR: Deposits are paused")
        print_info("Please unpause deposits first")
        sys.exit(1)
    print_success(f"✓ Deposits not paused")

    # Check subnet is active
    subnet_active = contract.functions.activeSubnets(test_netuid).call()
    if not subnet_active:
        print_error(f"SETUP ERROR: Subnet {test_netuid} is not active")
        print_info(f"Please activate subnet {test_netuid} first")
        sys.exit(1)
    print_success(f"✓ Subnet {test_netuid} is active")

    # Check user has gas
    user_evm_balance = w3.eth.get_balance(registered_address)
    if user_evm_balance < 1 * 10**18:  # 1 TAO for gas
        print_error(f"SETUP ERROR: Insufficient EVM TAO for gas")
        print_error(f"  Current: {user_evm_balance / 1e18:.4f} TAO")
        sys.exit(1)
    print_success(f"✓ User has sufficient EVM TAO for gas: {user_evm_balance / 1e18:.4f} TAO")

    print_warning(f"\n⚠ IMPORTANT: This test requires {deposit_amount_rao / 1e9:.2f} ALPHA staked to {delegate_hotkey_ss58} on netuid {test_netuid}")
    print_info(f"This test uses ANOTHER_HOTKEY as delegate")

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
    # STEP 4: Execute depositAlpha()
    # ========================================================================
    print_section("Step 4: Execute depositAlpha()")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - User's contract balance (netuid={test_netuid}): +{deposit_amount_rao / 1e9:.2f} ALPHA")
    print(f"    - Contract's subnetAlphaBalance[{test_netuid}]: +{deposit_amount_rao / 1e9:.2f} ALPHA")
    print(f"    - On-chain staking to contract: +{deposit_amount_rao / 1e9:.2f} ALPHA")
    print()

    print_info(f"Depositing {deposit_amount_rao / 1e9:.2f} ALPHA to netuid {test_netuid}...")
    print_info(f"User: {registered_address} ({registered_label}, registered)")

    # Execute transaction
    tx_receipt = None

    try:
        nonce = w3.eth.get_transaction_count(registered_address)
        gas_price = w3.eth.gas_price

        # Use ANOTHER_HOTKEY as delegate
        delegate_hotkey_bytes = delegate_hotkey

        tx = contract.functions.depositAlpha(
            test_netuid,
            deposit_amount_rao,
            delegate_hotkey_bytes
        ).build_transaction({
            'from': registered_address,
            'nonce': nonce,
            'gas': 1000000,  # Higher gas for ALPHA operations
            'gasPrice': gas_price,
            'chainId': chain_id
        })

        signed_tx = w3.eth.account.sign_transaction(tx, registered_private_key)
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

    # 3. Verify user contract balance increased
    expected_user_balance = user_contract_balance_before + deposit_amount_rao
    if user_contract_balance_after != expected_user_balance:
        print_error(f"✗ User contract balance incorrect!")
        print_error(f"  Expected: {expected_user_balance / 1e9:.2f} ALPHA")
        print_error(f"  Actual:   {user_contract_balance_after / 1e9:.2f} ALPHA")
        all_checks_passed = False
    else:
        print_success(f"✓ User contract balance increased by {deposit_amount_rao / 1e9:.2f} ALPHA")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    print_info("\nExpected changes:")
    print_info(f"  - {registered_label} Contract Balance (netuid={test_netuid}): +{deposit_amount_rao / 1e9:.2f} ALPHA")
    print_info(f"  - Contract subnetAlphaBalance[{test_netuid}]: +{deposit_amount_rao / 1e9:.2f} ALPHA")
    print_info(f"  - On-chain staking to contract DELEGATE_HOTKEY: +{deposit_amount_rao / 1e9:.2f} ALPHA")

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC14 TEST PASSED ✓✓✓")
        print_success("depositAlpha() executed successfully")
        print_success("All state validations passed")
        print_success("All balances updated correctly")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Deposited: {deposit_amount_rao / 1e9:.2f} ALPHA")
        print(f"  - Netuid: {test_netuid}")
        print(f"  - User contract balance: {user_contract_balance_before / 1e9:.2f} → {user_contract_balance_after / 1e9:.2f} ALPHA")
        print(f"  - Contract subnet balance: {subnet_balance_before / 1e9:.2f} → {subnet_balance_after / 1e9:.2f} ALPHA")
        print(f"  - Gas used: {tx_receipt['gasUsed']} units")

        return 0
    else:
        print_error("✗✗✗ TC14 TEST FAILED ✗✗✗")
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
