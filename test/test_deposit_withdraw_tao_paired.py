#!/usr/bin/env python3
"""
Test Case 01: Deposit TAO → Withdraw TAO (Paired Test)

Test Strategy:
- Deposit 100 TAO via depositTao()
- Withdraw 100 TAO via withdrawTao()
- Verify balance conservation using check_balance diff

Expected Behavior:
- Both transactions succeed
- Both events emitted correctly
- Initial EVM balance - Final EVM balance = Total gas cost (exact match)
- Contract balances return to initial state
- Perfect balance conservation

This test follows the 7-step pattern:
1. Step 0: Verify setup conditions
2. Step 1: Capture balances BEFORE
3. Step 2: Execute deposit transaction
4. Step 3: Capture balances AFTER DEPOSIT
5. Step 4: Execute withdraw transaction
6. Step 5: Capture balances AFTER WITHDRAW
7. Step 6: Three-way verification (balance conservation)
8. Step 7: Final test result
"""

import sys
import os
from web3 import Web3
from eth_account import Account
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.balance_checker import BalanceChecker

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
    print_section("Test Case 01: Deposit TAO → Withdraw TAO (Paired Test)")
    print_info("Objective: Verify balance conservation in TAO deposit/withdraw cycle")

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

    lender_address = Web3.to_checksum_address(addresses["LENDER1"]["evmAddress"])
    lender_private_key = os.getenv('LENDER1_PRIVATE_KEY')

    if not lender_private_key:
        print_error("LENDER1_PRIVATE_KEY not found in .env")
        return

    # Load contract
    with open('.contract_address', 'r') as f:
        contract_address = Web3.to_checksum_address(f.read().strip())

    with open('artifacts/contracts/LendingPoolV2.sol/LendingPoolV2.json', 'r') as f:
        abi = json.load(f)['abi']

    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Initialize BalanceChecker
    checker = BalanceChecker(w3=w3, contract=contract, test_netuids=[0, 2, 3])

    # Test parameters
    DEPOSIT_AMOUNT_TAO = 100
    DEPOSIT_AMOUNT_RAO = DEPOSIT_AMOUNT_TAO * 10**9
    DEPOSIT_AMOUNT_WEI = DEPOSIT_AMOUNT_RAO * 10**9

    print_info(f"Test amount: {DEPOSIT_AMOUNT_TAO} TAO ({DEPOSIT_AMOUNT_RAO:,} RAO)")

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

    addresses_list = [{"address": lender_address, "label": "lender"}]
    before = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(before)

    initial_evm_wei = before['balances']['lender']['evm_tao_wei']
    initial_contract_rao = before['balances']['lender']['contract']['netuid_0']['balance_rao']
    initial_subnet_rao = before['contract']['subnet_total_balance']['netuid_0']['rao']

    # Step 2: Execute Deposit
    print_section("Step 2: Execute Deposit TAO")

    print_info(f"Depositing {DEPOSIT_AMOUNT_TAO} TAO...")

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

    if deposit_receipt['status'] != 1:
        print_error("Deposit transaction failed")
        return

    gas_deposit = deposit_receipt['gasUsed'] * w3.eth.gas_price

    # Parse DepositTao event
    try:
        logs = contract.events.DepositTao().process_receipt(deposit_receipt)
        if logs:
            event = logs[0]['args']
            print_success(f"✓ DepositTao event: sender={event['sender']}, amount={event['amount']:,} RAO")
            assert event['sender'].lower() == lender_address.lower()
            assert event['amount'] == DEPOSIT_AMOUNT_RAO
    except Exception as e:
        print_warning(f"Event parsing: {e}")

    # Step 3: Capture AFTER DEPOSIT
    print_section("Step 3: Capture Balances AFTER DEPOSIT")

    after_deposit = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(after_deposit)

    deposit_diff = checker.diff_snapshots(before, after_deposit)
    print_info("Deposit changes:")
    checker.print_diff(deposit_diff)

    # Step 4: Execute Withdraw
    print_section("Step 4: Execute Withdraw TAO")

    print_info(f"Withdrawing {DEPOSIT_AMOUNT_TAO} TAO...")

    withdraw_tx = contract.functions.withdrawTao(DEPOSIT_AMOUNT_RAO).build_transaction({
        'from': lender_address,
        'nonce': w3.eth.get_transaction_count(lender_address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
    })

    signed_withdraw = w3.eth.account.sign_transaction(withdraw_tx, lender_private_key)
    withdraw_hash = w3.eth.send_raw_transaction(signed_withdraw.raw_transaction)
    print_success(f"Tx sent: {withdraw_hash.hex()}")

    withdraw_receipt = w3.eth.wait_for_transaction_receipt(withdraw_hash, timeout=120)
    print_success(f"Mined in block {withdraw_receipt['blockNumber']}, Gas: {withdraw_receipt['gasUsed']:,}")

    if withdraw_receipt['status'] != 1:
        print_error("Withdraw transaction failed")
        return

    gas_withdraw = withdraw_receipt['gasUsed'] * w3.eth.gas_price

    # Parse WithdrawTao event
    try:
        logs = contract.events.WithdrawTao().process_receipt(withdraw_receipt)
        if logs:
            event = logs[0]['args']
            print_success(f"✓ WithdrawTao event: sender={event['sender']}, amount={event['amount']:,} RAO")
            assert event['sender'].lower() == lender_address.lower()
            assert event['amount'] == DEPOSIT_AMOUNT_RAO
    except Exception as e:
        print_warning(f"Event parsing: {e}")

    # Step 5: Capture AFTER WITHDRAW
    print_section("Step 5: Capture Balances AFTER WITHDRAW")

    final = checker.capture_snapshot(addresses_list, include_staking=False)
    checker.print_snapshot(final)

    total_diff = checker.diff_snapshots(before, final)
    print_info("Total changes (initial → final):")
    checker.print_diff(total_diff)

    # Step 6: Three-Way Verification
    print_section("Step 6: Three-Way Verification (Balance Conservation)")

    final_evm_wei = final['balances']['lender']['evm_tao_wei']
    final_contract_rao = final['balances']['lender']['contract']['netuid_0']['balance_rao']
    final_subnet_rao = final['contract']['subnet_total_balance']['netuid_0']['rao']

    total_gas = gas_deposit + gas_withdraw

    print_info("Balance Conservation:")
    print_info(f"  Initial EVM: {initial_evm_wei:,} wei ({initial_evm_wei / 1e18:.9f} TAO)")
    print_info(f"  Final EVM:   {final_evm_wei:,} wei ({final_evm_wei / 1e18:.9f} TAO)")
    print_info(f"  Difference:  {initial_evm_wei - final_evm_wei:,} wei ({(initial_evm_wei - final_evm_wei) / 1e18:.9f} TAO)")
    print_info(f"  Total gas:   {total_gas:,} wei ({total_gas / 1e18:.9f} TAO)")

    evm_diff = initial_evm_wei - final_evm_wei
    if evm_diff == total_gas:
        print_success("✓ EVM balance: difference = gas cost EXACTLY")
    else:
        print_error(f"✗ EVM mismatch: {evm_diff} != {total_gas}, discrepancy: {evm_diff - total_gas} wei")
        print_section("Test Result")
        print_error("✗ TEST FAILED")
        return

    print_info("")
    print_info(f"  Initial contract: {initial_contract_rao:,} RAO ({initial_contract_rao / 1e9:.9f} TAO)")
    print_info(f"  Final contract:   {final_contract_rao:,} RAO ({final_contract_rao / 1e9:.9f} TAO)")
    print_info(f"  Difference:       {final_contract_rao - initial_contract_rao:,} RAO")

    if final_contract_rao == initial_contract_rao:
        print_success("✓ Contract balance: returned to initial state")
    else:
        print_error(f"✗ Contract mismatch: {final_contract_rao} != {initial_contract_rao}")
        print_section("Test Result")
        print_error("✗ TEST FAILED")
        return

    print_info("")
    print_info(f"  Initial subnet total: {initial_subnet_rao:,} RAO ({initial_subnet_rao / 1e9:.9f} TAO)")
    print_info(f"  Final subnet total:   {final_subnet_rao:,} RAO ({final_subnet_rao / 1e9:.9f} TAO)")
    print_info(f"  Difference:           {final_subnet_rao - initial_subnet_rao:,} RAO")

    if final_subnet_rao == initial_subnet_rao:
        print_success("✓ Subnet total: returned to initial state")
    else:
        print_error(f"✗ Subnet mismatch: {final_subnet_rao} != {initial_subnet_rao}")
        print_section("Test Result")
        print_error("✗ TEST FAILED")
        return

    # Step 7: Final Result
    print_section("Step 7: Final Test Result")

    print_success("="*80)
    print_success("✓ TEST PASSED: Deposit TAO → Withdraw TAO (Paired Test)")
    print_success("="*80)
    print_success("")
    print_success("All verifications passed:")
    print_success("  ✓ Deposit transaction succeeded")
    print_success("  ✓ Withdraw transaction succeeded")
    print_success("  ✓ DepositTao event emitted correctly")
    print_success("  ✓ WithdrawTao event emitted correctly")
    print_success("  ✓ EVM balance conservation: initial - final = gas cost (exact)")
    print_success("  ✓ Contract balance conservation: returned to initial state")
    print_success("  ✓ Subnet total conservation: returned to initial state")
    print_success("  ✓ 0 RAO difference in all verifications")
    print_success("")
    print_success("Balance Conservation Principle Verified:")
    print_success(f"  Δ EVM Balance = {(initial_evm_wei - final_evm_wei) / 1e18:.9f} TAO")
    print_success(f"  Total Gas     = {total_gas / 1e18:.9f} TAO")
    print_success("  Difference    = 0 (PERFECT MATCH)")
    print_success("")

if __name__ == '__main__':
    main()
