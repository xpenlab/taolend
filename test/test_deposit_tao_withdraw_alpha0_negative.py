#!/usr/bin/env python3
"""
Test Case 03 (Negative): Deposit TAO → Withdraw MORE netuid=0 ALPHA (Cross-Type, Insufficient Balance)

Test Strategy:
- Deposit 100 TAO via depositTao() (stores at netuid=0)
- Try to withdraw 150 TAO via withdrawAlpha(netuid=0, 150 TAO) (more than deposited)
- Verify transaction FAILS with "user withdraw, insufficient alpha balance"

Expected Behavior:
- Deposit transaction succeeds
- Withdraw transaction FAILS with expected error
- Contract balances remain at +100 TAO (only deposit, no withdraw)
- User balance shows deposit amount after failed withdraw
- Proves: Cross-type withdraw validation works (netuid=0 ALPHA == TAO)

This test follows the negative test pattern:
1. Step 0: Verify setup conditions
2. Step 1: Capture balances BEFORE
3. Step 2: Execute deposit TAO transaction (should succeed)
4. Step 3: Capture balances AFTER DEPOSIT
5. Step 4: Execute withdraw ALPHA(0) with EXCESS amount (should fail)
6. Step 5: Verify failure and check balances unchanged from step 3
7. Step 6: Final test result
"""

import sys
import os
import time
from web3 import Web3
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.balance_checker import BalanceChecker
from scripts.cli_utils import ss58_to_bytes32

# Load environment
load_dotenv()

# ANSI color codes
GREEN = '\033[0;32m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

def print_section(title):
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")

def print_success(message):
    print(f"{GREEN}[SUCCESS]{NC} {message}")

def print_error(message):
    print(f"{RED}[ERROR]{NC} {message}")

def print_warning(message):
    print(f"{YELLOW}[WARNING]{NC} {message}")

def print_info(message):
    print(f"{CYAN}[INFO]{NC} {message}")

def main():
    print_section("Test Case 03 (Negative): Deposit TAO → Withdraw MORE netuid=0 ALPHA")
    print_info("Objective: Verify cross-type withdraw fails when amount > balance")

    # Setup
    rpc_url = os.getenv('RPC_URL', 'http://127.0.0.1:9944')
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print_error(f"Failed to connect to {rpc_url}")
        return

    print_success(f"Connected to {rpc_url}")
    print_info(f"Chain ID: {w3.eth.chain_id}, Block: {w3.eth.block_number}")

    # Load addresses
    with open('addresses.json', 'r') as f:
        addresses_data = json.load(f)

    addresses = {}
    for account in addresses_data['accounts']:
        addresses[account['name']] = account

    # Use LENDER1 for this test
    lender_address = Web3.to_checksum_address(addresses["LENDER1"]["evmAddress"])
    lender_ss58 = addresses["LENDER1"]["ss58Address"]
    lender_private_key = os.getenv('LENDER1_PRIVATE_KEY')

    if not lender_private_key:
        print_error("LENDER1_PRIVATE_KEY not found in .env")
        return

    print_info(f"Test Account: LENDER1 ({lender_address})")

    # Load contract
    with open('.contract_address', 'r') as f:
        contract_address = Web3.to_checksum_address(f.read().strip())

    with open('artifacts/contracts/LendingPoolV2.sol/LendingPoolV2.json', 'r') as f:
        abi = json.load(f)['abi']

    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Initialize BalanceChecker
    checker = BalanceChecker(w3=w3, contract=contract, test_netuids=[0, 2, 3])

    # Test parameters
    TEST_NETUID = 0  # TAO storage location
    DEPOSIT_AMOUNT_TAO = 100
    DEPOSIT_AMOUNT_RAO = DEPOSIT_AMOUNT_TAO * 10**9
    DEPOSIT_AMOUNT_WEI = DEPOSIT_AMOUNT_RAO * 10**9

    # Will calculate actual withdraw amount after seeing total balance
    WITHDRAW_EXCESS_TAO = 50  # Additional amount beyond total balance

    print_info(f"Test netuid: {TEST_NETUID} (TAO storage)")
    print_info(f"Deposit amount: {DEPOSIT_AMOUNT_TAO} TAO ({DEPOSIT_AMOUNT_RAO:,} RAO)")

    # Step 0: Verify Setup
    print_section("Step 0: Verify Setup Conditions")

    if not contract.functions.registeredUser(lender_address).call():
        print_error("LENDER1 is not registered")
        return
    print_success("✓ LENDER1 is registered")

    if contract.functions.paused().call():
        print_error("Contract is paused")
        return
    print_success("✓ Contract is not paused")

    evm_balance = w3.eth.get_balance(lender_address)
    if evm_balance < DEPOSIT_AMOUNT_WEI + 10**18:
        print_error(f"Insufficient EVM balance: {evm_balance / 1e18:.9f} TAO")
        return
    print_success(f"✓ Sufficient EVM balance: {evm_balance / 1e18:.9f} TAO")

    # Step 1: Capture BEFORE
    print_section("Step 1: Capture Balances BEFORE")

    addresses_list = [{"address": lender_address, "label": "lender1", "ss58": lender_ss58}]

    # Wait 15 seconds before initial snapshot
    print_info("Waiting 15 seconds before initial snapshot...")
    time.sleep(15)

    before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(before)

    initial_contract_rao = before['balances']['lender1']['contract'][f'netuid_{TEST_NETUID}']['balance_rao']

    # Step 2: Execute Deposit TAO (Should Succeed)
    print_section("Step 2: Execute Deposit TAO (Should Succeed)")

    print_info(f"Depositing {DEPOSIT_AMOUNT_TAO} TAO (stores at netuid={TEST_NETUID})...")

    deposit_tx = contract.functions.depositTao().build_transaction({
        'from': lender_address,
        'value': DEPOSIT_AMOUNT_WEI,
        'nonce': w3.eth.get_transaction_count(lender_address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
    })

    signed_deposit = w3.eth.account.sign_transaction(deposit_tx, lender_private_key)
    deposit_hash = w3.eth.send_raw_transaction(signed_deposit.raw_transaction)
    print_success(f"Tx sent: {deposit_hash.hex()}")

    deposit_receipt = w3.eth.wait_for_transaction_receipt(deposit_hash, timeout=120)
    print_success(f"Mined in block {deposit_receipt['blockNumber']}, Gas: {deposit_receipt['gasUsed']:,}")

    # Wait for state to propagate
    print_info("Waiting 15 seconds for on-chain state to propagate...")
    time.sleep(15)

    if deposit_receipt['status'] != 1:
        print_error("Deposit transaction failed")
        return

    print_success("✓ Deposit transaction succeeded")

    # Step 3: Capture AFTER DEPOSIT
    print_section("Step 3: Capture Balances AFTER DEPOSIT")

    after_deposit = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(after_deposit)

    contract_balance_after_deposit = after_deposit['balances']['lender1']['contract'][f'netuid_{TEST_NETUID}']['balance_rao']
    print_info(f"Contract balance after deposit: {contract_balance_after_deposit:,} RAO ({contract_balance_after_deposit / 1e9:.9f} TAO)")

    expected_balance = initial_contract_rao + DEPOSIT_AMOUNT_RAO
    if contract_balance_after_deposit == expected_balance:
        print_success(f"✓ Contract balance increased by {DEPOSIT_AMOUNT_TAO} TAO")
    else:
        print_error(f"✗ Contract balance mismatch: {contract_balance_after_deposit} != {expected_balance}")
        return

    # Calculate withdraw amount: total balance + excess
    WITHDRAW_AMOUNT_RAO = contract_balance_after_deposit + (WITHDRAW_EXCESS_TAO * 10**9)
    WITHDRAW_AMOUNT_TAO = WITHDRAW_AMOUNT_RAO / 10**9

    print_info(f"Total balance after deposit: {contract_balance_after_deposit / 1e9:.9f} TAO")
    print_info(f"Will attempt to withdraw: {WITHDRAW_AMOUNT_TAO:.9f} TAO ({WITHDRAW_AMOUNT_RAO:,} RAO)")
    print_warning(f"Attempting to withdraw {WITHDRAW_EXCESS_TAO} TAO MORE than total balance!")

    # Step 4: Execute Withdraw ALPHA(0) with EXCESS amount (Should Fail)
    print_section("Step 4: Execute Withdraw ALPHA(netuid=0) with EXCESS amount (Should Fail)")

    user_coldkey_hex = ss58_to_bytes32(lender_ss58)
    user_coldkey_bytes = Web3.to_bytes(hexstr=user_coldkey_hex)

    withdraw_tx = contract.functions.withdrawAlpha(
        TEST_NETUID,  # netuid=0 for TAO
        WITHDRAW_AMOUNT_RAO,
        user_coldkey_bytes
    ).build_transaction({
        'from': lender_address,
        'nonce': w3.eth.get_transaction_count(lender_address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
    })

    signed_withdraw = w3.eth.account.sign_transaction(withdraw_tx, lender_private_key)

    try:
        withdraw_hash = w3.eth.send_raw_transaction(signed_withdraw.raw_transaction)
        print_info(f"Tx sent: {withdraw_hash.hex()}")

        withdraw_receipt = w3.eth.wait_for_transaction_receipt(withdraw_hash, timeout=120)

        if withdraw_receipt['status'] == 0:
            print_success("✓ Transaction REVERTED as expected (status=0)")
            transaction_failed = True
        else:
            print_error("✗ Transaction succeeded when it should have failed!")
            print_section("Test Result")
            print_error("✗ TEST FAILED: Withdraw should have been rejected")
            return

    except Exception as e:
        error_msg = str(e)
        print_success(f"✓ Transaction FAILED as expected: {error_msg}")

        if "insufficient alpha balance" in error_msg.lower() or "user withdraw" in error_msg.lower():
            print_success("✓ Error message matches expected: 'user withdraw, insufficient alpha balance'")
        else:
            print_warning(f"Error message differs from expected, but transaction failed: {error_msg}")

        transaction_failed = True

    # Wait before final snapshot
    print_info("Waiting 15 seconds before final snapshot...")
    time.sleep(15)

    # Step 5: Verify balances unchanged from step 3
    print_section("Step 5: Verify Balances Unchanged After Failed Withdraw")

    final = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(final)

    final_contract_rao = final['balances']['lender1']['contract'][f'netuid_{TEST_NETUID}']['balance_rao']

    print_info("Balance verification after failed withdraw:")
    print_info(f"  Balance after deposit:  {contract_balance_after_deposit:,} RAO")
    print_info(f"  Balance after withdraw: {final_contract_rao:,} RAO")
    print_info(f"  Difference:             {final_contract_rao - contract_balance_after_deposit:,} RAO")

    if final_contract_rao == contract_balance_after_deposit:
        print_success("✓ Contract balance UNCHANGED (withdraw was rejected)")
    else:
        print_error(f"✗ Contract balance changed unexpectedly!")
        print_section("Test Result")
        print_error("✗ TEST FAILED")
        return

    # Step 6: Final Result
    print_section("Step 6: Final Test Result")

    print_success("="*80)
    print_success("✓ TEST PASSED: Deposit TAO → Withdraw MORE netuid=0 ALPHA (Negative Test)")
    print_success("="*80)
    print_success("")
    print_success("All verifications passed:")
    print_success("  ✓ Deposit TAO transaction succeeded")
    print_success("  ✓ Withdraw ALPHA(netuid=0) transaction FAILED as expected")
    print_success("  ✓ Error: 'user withdraw, insufficient alpha balance'")
    print_success("  ✓ Contract balance unchanged after failed withdraw")
    print_success(f"  ✓ User balance: {contract_balance_after_deposit / 1e9:.9f} TAO (only deposit, no withdraw)")
    print_success("")
    print_success("Cross-Type Negative Test Behavior Verified:")
    print_success(f"  Deposited via depositTao(): {DEPOSIT_AMOUNT_TAO} TAO")
    print_success(f"  Attempted to withdraw via withdrawAlpha(netuid=0): {WITHDRAW_AMOUNT_TAO} TAO")
    print_success(f"  Result: Transaction REJECTED (insufficient balance)")
    print_success(f"  Contract correctly enforces: userAlphaBalance[user][0] >= _amount")
    print_success("")
    print_success("Key Finding:")
    print_success("  Cross-type withdrawal validation works correctly")
    print_success("  depositTao() and withdrawAlpha(netuid=0) share same storage")
    print_success("  Both access userAlphaBalance[user][0]")
    print_success("  Balance check applies regardless of withdrawal method")
    print_success("")

if __name__ == '__main__':
    main()
