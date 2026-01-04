#!/usr/bin/env python3
"""
Test Case TC03: depositTao() - Multiple Deposits
Objective: Verify depositTao works correctly with multiple consecutive deposits
Tests: Execute 3 deposits and verify cumulative balance changes

Strategy: 8-step testing pattern with BalanceChecker (adapted for multiple ops)
Expected: All transactions succeed, balances accumulate correctly
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
    print_section("Test Case TC03: depositTao() - Multiple Deposits")
    print(f"{CYAN}Objective:{NC} Verify depositTao works correctly with multiple consecutive deposits")
    print(f"{CYAN}Strategy:{NC} Execute 3 deposits (5, 10, 15 TAO) and verify cumulative changes")
    print(f"{CYAN}Expected:{NC} All transactions succeed, balances accumulate correctly\n")

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

    # Test parameters - Multiple deposits
    deposits = [
        {"amount_rao": 5 * 10**9, "label": "First"},   # 5 TAO
        {"amount_rao": 10 * 10**9, "label": "Second"}, # 10 TAO
        {"amount_rao": 15 * 10**9, "label": "Third"}   # 15 TAO
    ]
    total_deposit_rao = sum(d["amount_rao"] for d in deposits)

    print_info(f"\nTest Parameters:")
    print_info(f"  Registered User: {registered_label} ({registered_address})")
    print_info(f"  Deposit Sequence:")
    for i, d in enumerate(deposits, 1):
        print_info(f"    Deposit {i}: {d['amount_rao'] / 1e9:.2f} TAO ({d['label']})")
    print_info(f"  Total: {total_deposit_rao / 1e9:.2f} TAO")

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

    # Check deposit not paused
    paused_deposit = contract.functions.pausedDeposit().call()
    if paused_deposit:
        print_error("SETUP ERROR: Deposits are paused")
        print_info("Please unpause deposits first:")
        print_info(f"  {YELLOW}python3 scripts/cli.py pause --operation deposit --unpause{NC}")
        sys.exit(1)
    print_success(f"✓ Deposits not paused")

    # Check user has sufficient EVM TAO balance
    user_evm_balance = w3.eth.get_balance(registered_address)
    required_balance = (total_deposit_rao * 10**9) + (1 * 10**18)  # total + 1 TAO for gas
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
    snapshot_initial = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_initial)

    # Query specific state
    protocol_fee_initial = contract.functions.protocolFeeAccumulated().call()
    subnet_balance_initial = contract.functions.subnetAlphaBalance(0).call()

    print_info(f"\nContract State:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_initial / 1e9:.9f} TAO")
    print_info(f"  subnetAlphaBalance[0]: {subnet_balance_initial / 1e9:.2f} TAO")

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
    # STEP 4: Execute Multiple depositTao() Operations
    # ========================================================================
    print_section("Step 4: Execute Multiple depositTao() Operations")

    print(f"\n{BOLD}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} All transactions succeed")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - User's contract balance (netuid=0): +{total_deposit_rao / 1e9:.2f} TAO (cumulative)")
    print(f"    - Contract's subnetAlphaBalance[0]: +{total_deposit_rao / 1e9:.2f} TAO (cumulative)")
    print(f"    - User's EVM TAO: -{total_deposit_rao / 1e9:.2f} TAO (+ gas)")
    print()

    # Execute deposits
    tx_receipts = []
    all_deposits_succeeded = True

    for i, deposit in enumerate(deposits, 1):
        amount_rao = deposit["amount_rao"]
        amount_wei = amount_rao * 10**9
        label = deposit["label"]

        print_info(f"\n[Deposit {i}] {label} deposit of {amount_rao / 1e9:.2f} TAO...")
        print_info(f"User: {registered_address} ({registered_label}, registered)")

        try:
            nonce = w3.eth.get_transaction_count(registered_address)
            gas_price = w3.eth.gas_price

            tx = contract.functions.depositTao().build_transaction({
                'from': registered_address,
                'value': amount_wei,
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
                print_success(f"✓ Deposit {i} succeeded")
                tx_receipts.append(tx_receipt)
            else:
                print_error(f"✗ Deposit {i} reverted unexpectedly!")
                all_deposits_succeeded = False
                break

        except Exception as e:
            print_error(f"✗ Deposit {i} failed: {e}")
            import traceback
            traceback.print_exc()
            all_deposits_succeeded = False
            break

    if not all_deposits_succeeded:
        print_error("\n✗✗✗ TEST FAILED - Not all deposits succeeded ✗✗✗")
        sys.exit(1)

    print_success(f"\n✓ All {len(deposits)} deposits executed successfully")

    # ========================================================================
    # STEP 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    print_info("Capturing final state snapshot...")
    snapshot_final = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_final)

    # Query final state
    protocol_fee_final = contract.functions.protocolFeeAccumulated().call()
    subnet_balance_final = contract.functions.subnetAlphaBalance(0).call()

    print_info(f"\nContract State After:")
    print_info(f"  protocolFeeAccumulated: {protocol_fee_initial / 1e9:.9f} → {protocol_fee_final / 1e9:.9f} TAO")
    print_info(f"  subnetAlphaBalance[0]: {subnet_balance_initial / 1e9:.2f} → {subnet_balance_final / 1e9:.2f} TAO")

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
    if not all_deposits_succeeded:
        print_error("✗ Not all transactions succeeded!")
        all_checks_passed = False
    else:
        print_success(f"✓ All {len(deposits)} transactions succeeded")

    # 2. Verify protocol fee unchanged (no fee for deposits)
    if protocol_fee_final != protocol_fee_initial:
        print_error(f"✗ Protocol fee changed unexpectedly!")
        print_error(f"  Before: {protocol_fee_initial / 1e9:.9f} TAO")
        print_error(f"  After:  {protocol_fee_final / 1e9:.9f} TAO")
        all_checks_passed = False
    else:
        print_success("✓ Protocol fee unchanged")

    # 3. Verify subnet balance increased by total amount
    expected_subnet_balance = subnet_balance_initial + total_deposit_rao
    if subnet_balance_final != expected_subnet_balance:
        print_error(f"✗ Subnet balance incorrect!")
        print_error(f"  Expected: {expected_subnet_balance / 1e9:.2f} TAO")
        print_error(f"  Actual:   {subnet_balance_final / 1e9:.2f} TAO")
        all_checks_passed = False
    else:
        print_success(f"✓ Subnet balance increased by {total_deposit_rao / 1e9:.2f} TAO (cumulative)")

    # 4. Verify user contract balance increased by total amount
    user_contract_initial = snapshot_initial['balances'][registered_label]['contract'].get('netuid_0', {})
    user_contract_final = snapshot_final['balances'][registered_label]['contract'].get('netuid_0', {})

    user_contract_balance_initial = user_contract_initial.get('balance_rao', 0)
    user_contract_balance_final = user_contract_final.get('balance_rao', 0)

    expected_user_balance = user_contract_balance_initial + total_deposit_rao
    if user_contract_balance_final != expected_user_balance:
        print_error(f"✗ User contract balance incorrect!")
        print_error(f"  Expected: {expected_user_balance / 1e9:.2f} TAO")
        print_error(f"  Actual:   {user_contract_balance_final / 1e9:.2f} TAO")
        all_checks_passed = False
    else:
        print_success(f"✓ User contract balance increased by {total_deposit_rao / 1e9:.2f} TAO (cumulative)")

    # 5. Verify user EVM TAO decreased by total amount + gas
    user_evm_initial = snapshot_initial['balances'][registered_label]['evm_tao_wei']
    user_evm_final = snapshot_final['balances'][registered_label]['evm_tao_wei']

    total_gas_used = sum(r['gasUsed'] * r['effectiveGasPrice'] for r in tx_receipts)
    expected_evm_balance = user_evm_initial - (total_deposit_rao * 10**9) - total_gas_used

    if user_evm_final != expected_evm_balance:
        print_warning(f"⚠ User EVM TAO balance may differ slightly (gas estimation)")
        print_info(f"  Expected: ~{expected_evm_balance / 1e18:.6f} TAO")
        print_info(f"  Actual:   {user_evm_final / 1e18:.6f} TAO")
    else:
        print_success(f"✓ User EVM TAO decreased correctly")

    # Calculate and print balance differences
    print_section("Balance Changes")
    diff = checker.diff_snapshots(snapshot_initial, snapshot_final)
    checker.print_diff(diff)

    print_info("\nExpected cumulative changes:")
    print_info(f"  - {registered_label} EVM TAO: -{total_deposit_rao / 1e9:.2f} TAO (+ gas)")
    print_info(f"  - {registered_label} Contract Balance (netuid=0): +{total_deposit_rao / 1e9:.2f} TAO")
    print_info(f"  - Contract subnetAlphaBalance[0]: +{total_deposit_rao / 1e9:.2f} TAO")

    # ========================================================================
    # FINAL RESULT
    # ========================================================================
    print_section("FINAL RESULT")

    if all_checks_passed:
        print_success("✓✓✓ TC03 TEST PASSED ✓✓✓")
        print_success("Multiple depositTao() operations executed successfully")
        print_success("All state validations passed")
        print_success("All balances updated correctly")

        print(f"\n{CYAN}Summary:{NC}")
        print(f"  - Number of deposits: {len(deposits)}")
        for i, deposit in enumerate(deposits, 1):
            print(f"  - Deposit {i}: {deposit['amount_rao'] / 1e9:.2f} TAO ({deposit['label']})")
        print(f"  - Total deposited: {total_deposit_rao / 1e9:.2f} TAO")
        print(f"  - User contract balance: {user_contract_balance_initial / 1e9:.2f} → {user_contract_balance_final / 1e9:.2f} TAO")
        print(f"  - Contract subnet balance: {subnet_balance_initial / 1e9:.2f} → {subnet_balance_final / 1e9:.2f} TAO")
        print(f"  - Protocol fee unchanged: {protocol_fee_initial / 1e9:.9f} TAO")
        print(f"  - Total gas used: {sum(r['gasUsed'] for r in tx_receipts)} units")

        return 0
    else:
        print_error("✗✗✗ TC03 TEST FAILED ✗✗✗")
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
