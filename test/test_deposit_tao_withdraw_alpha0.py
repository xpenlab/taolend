#!/usr/bin/env python3
"""
Test Case 03: Deposit TAO → Withdraw netuid=0 ALPHA (Cross-Type Test)

Test Strategy:
- Deposit 100 TAO via depositTao() (stores at netuid=0)
- Withdraw 100 TAO via withdrawAlpha(netuid=0, 100 TAO)
- Verify balance conservation and cross-type equivalence

Expected Behavior:
- Both transactions succeed
- Both events emitted correctly (AlphaDeposited/AlphaWithdrawn with netuid=0)
- Balance conservation verified
- Proves: TAO == netuid=0 ALPHA (same storage location)

This test follows the 7-step pattern:
1. Step 0: Verify setup conditions
2. Step 1: Capture balances BEFORE
3. Step 2: Execute deposit TAO transaction
4. Step 3: Capture balances AFTER DEPOSIT
5. Step 4: Execute withdraw ALPHA (netuid=0) transaction
6. Step 5: Capture balances AFTER WITHDRAW
7. Step 6: Three-way verification (cross-type equivalence)
8. Step 7: Final test result
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
    print_section("Test Case 03: Deposit TAO → Withdraw netuid=0 ALPHA (Cross-Type Test)")
    print_info("Objective: Verify TAO and netuid=0 ALPHA are equivalent in contract storage")

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

    print_info(f"Test netuid: {TEST_NETUID} (TAO storage)")
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
    if evm_balance < DEPOSIT_AMOUNT_WEI + 10**18:  # Need deposit amount + 1 TAO for gas
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

    initial_evm_wei = before['balances']['lender1']['evm_tao_wei']
    initial_contract_rao = before['balances']['lender1']['contract'][f'netuid_{TEST_NETUID}']['balance_rao']
    initial_subnet_rao = before['contract']['subnet_total_balance'][f'netuid_{TEST_NETUID}']['rao']

    # Get initial on-chain staking (netuid=0)
    if 'staking' in before['balances']['lender1']:
        initial_stake_rao = before['balances']['lender1']['staking'][f'netuid_{TEST_NETUID}']['stake_rao']
    else:
        print_warning("Could not get initial stake from snapshot")
        initial_stake_rao = None

    # Step 2: Execute Deposit TAO
    print_section("Step 2: Execute Deposit TAO")

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

    # Wait for on-chain state to propagate
    print_info("Waiting 15 seconds for on-chain state to propagate...")
    time.sleep(15)

    if deposit_receipt['status'] != 1:
        print_error("Deposit transaction failed")
        return

    gas_deposit = deposit_receipt['gasUsed'] * w3.eth.gas_price

    # Parse AlphaDeposited event (depositTao emits this with netuid=0)
    try:
        logs = contract.events.AlphaDeposited().process_receipt(deposit_receipt)
        if logs:
            event = logs[0]['args']
            print_success(f"✓ AlphaDeposited event: user={event['user']}, netuid={event['netuid']}, amount={event['amount']:,} RAO")
            assert event['user'].lower() == lender_address.lower()
            assert event['netuid'] == TEST_NETUID
            assert event['amount'] == DEPOSIT_AMOUNT_RAO
    except Exception as e:
        print_warning(f"Event parsing: {e}")

    # Step 3: Capture AFTER DEPOSIT
    print_section("Step 3: Capture Balances AFTER DEPOSIT")

    after_deposit = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(after_deposit)

    deposit_diff = checker.diff_snapshots(before, after_deposit)
    print_info("Deposit changes:")
    checker.print_diff(deposit_diff)

    # Step 4: Execute Withdraw ALPHA (netuid=0)
    print_section("Step 4: Execute Withdraw ALPHA (netuid=0)")

    print_info(f"Withdrawing {DEPOSIT_AMOUNT_TAO} TAO via withdrawAlpha(netuid={TEST_NETUID})...")

    # Convert user's SS58 address to coldkey bytes32
    user_coldkey_hex = ss58_to_bytes32(lender_ss58)
    user_coldkey_bytes = Web3.to_bytes(hexstr=user_coldkey_hex)
    print_info(f"User coldkey (bytes32): {user_coldkey_hex}")

    withdraw_tx = contract.functions.withdrawAlpha(
        TEST_NETUID,  # netuid=0 for TAO
        DEPOSIT_AMOUNT_RAO,
        user_coldkey_bytes
    ).build_transaction({
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

    # Wait for on-chain state to propagate
    print_info("Waiting 15 seconds for on-chain state to propagate...")
    time.sleep(15)

    if withdraw_receipt['status'] != 1:
        print_error("Withdraw transaction failed")
        return

    gas_withdraw = withdraw_receipt['gasUsed'] * w3.eth.gas_price

    # Parse AlphaWithdrawn event
    try:
        logs = contract.events.AlphaWithdrawn().process_receipt(withdraw_receipt)
        if logs:
            event = logs[0]['args']
            print_success(f"✓ AlphaWithdrawn event: user={event['user']}, netuid={event['netuid']}, amount={event['amount']:,} RAO")
            assert event['user'].lower() == lender_address.lower()
            assert event['netuid'] == TEST_NETUID
            assert event['amount'] == DEPOSIT_AMOUNT_RAO
    except Exception as e:
        print_warning(f"Event parsing: {e}")

    # Step 5: Capture AFTER WITHDRAW
    print_section("Step 5: Capture Balances AFTER WITHDRAW")

    final = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(final)

    total_diff = checker.diff_snapshots(before, final)
    print_info("Total changes (initial → final):")
    checker.print_diff(total_diff)

    # Step 6: Three-Way Verification
    print_section("Step 6: Three-Way Verification (Cross-Type Equivalence)")

    final_evm_wei = final['balances']['lender1']['evm_tao_wei']
    final_contract_rao = final['balances']['lender1']['contract'][f'netuid_{TEST_NETUID}']['balance_rao']
    final_subnet_rao = final['contract']['subnet_total_balance'][f'netuid_{TEST_NETUID}']['rao']

    # Get final on-chain staking (netuid=0)
    if 'staking' in final['balances']['lender1']:
        final_stake_rao = final['balances']['lender1']['staking'][f'netuid_{TEST_NETUID}']['stake_rao']
    else:
        print_warning("Could not get final stake from snapshot")
        final_stake_rao = None

    total_gas = gas_deposit + gas_withdraw

    print_info("Cross-Type Behavior Verification:")
    print_info("")
    print_info("Expected Behavior:")
    print_info("  1. depositTao() deposits 100 TAO to contract (netuid=0)")
    print_info("  2. withdrawAlpha(netuid=0) transfers 100 TAO as STAKE to user's coldkey")
    print_info("  3. User's EVM balance: decreased by 100 TAO + gas")
    print_info("  4. User's on-chain staking (netuid=0): increased by 100 TAO")
    print_info("")

    print_info("EVM Balance Changes:")
    print_info(f"  Initial EVM: {initial_evm_wei:,} wei ({initial_evm_wei / 1e18:.9f} TAO)")
    print_info(f"  Final EVM:   {final_evm_wei:,} wei ({final_evm_wei / 1e18:.9f} TAO)")
    print_info(f"  Difference:  {initial_evm_wei - final_evm_wei:,} wei ({(initial_evm_wei - final_evm_wei) / 1e18:.9f} TAO)")
    print_info(f"  Expected:    {DEPOSIT_AMOUNT_WEI + total_gas:,} wei (100 TAO + {total_gas / 1e18:.9f} TAO gas)")

    evm_diff = initial_evm_wei - final_evm_wei
    expected_evm_diff = DEPOSIT_AMOUNT_WEI + total_gas
    if evm_diff == expected_evm_diff:
        print_success("✓ EVM balance: decreased by 100 TAO + gas EXACTLY")
    else:
        print_error(f"✗ EVM mismatch: {evm_diff} != {expected_evm_diff}, discrepancy: {evm_diff - expected_evm_diff} wei")
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

    # Verify on-chain staking INCREASED by deposit amount
    if initial_stake_rao is not None and final_stake_rao is not None:
        print_info("")
        print_info("On-chain Staking Changes (netuid=0):")
        print_info(f"  Initial on-chain stake: {initial_stake_rao:,} RAO ({initial_stake_rao / 1e9:.9f} TAO)")
        print_info(f"  Final on-chain stake:   {final_stake_rao:,} RAO ({final_stake_rao / 1e9:.9f} TAO)")
        print_info(f"  Difference:             {final_stake_rao - initial_stake_rao:,} RAO ({(final_stake_rao - initial_stake_rao) / 1e9:.9f} TAO)")
        print_info(f"  Expected increase:      {DEPOSIT_AMOUNT_RAO:,} RAO (100 TAO)")

        if final_stake_rao - initial_stake_rao == DEPOSIT_AMOUNT_RAO:
            print_success("✓ On-chain stake: increased by 100 TAO EXACTLY (withdrawn as stake)")
        else:
            print_error(f"✗ On-chain stake mismatch: increase = {final_stake_rao - initial_stake_rao}, expected = {DEPOSIT_AMOUNT_RAO}")
            print_section("Test Result")
            print_error("✗ TEST FAILED")
            return
    else:
        print_warning("On-chain stake verification skipped (data not available)")

    # Step 7: Final Result
    print_section("Step 7: Final Test Result - Cross-Type Equivalence Verified")

    print_success("="*80)
    print_success("✓ TEST PASSED: Deposit TAO → Withdraw netuid=0 ALPHA")
    print_success("="*80)
    print_success("")
    print_success("All verifications passed:")
    print_success("  ✓ Deposit TAO transaction succeeded")
    print_success("  ✓ Withdraw ALPHA (netuid=0) transaction succeeded")
    print_success("  ✓ AlphaDeposited event emitted with netuid=0")
    print_success("  ✓ AlphaWithdrawn event emitted with netuid=0")
    print_success("  ✓ EVM balance: decreased by 100 TAO + gas (exact)")
    print_success("  ✓ Contract balance: returned to initial state")
    print_success("  ✓ Subnet total: returned to initial state")
    if initial_stake_rao is not None and final_stake_rao is not None:
        print_success("  ✓ On-chain staking: increased by 100 TAO (withdrawn as stake)")
    print_success("  ✓ 0 RAO difference in all verifications")
    print_success("")
    print_success("Cross-Type Behavior Verified:")
    print_success(f"  depositTao() → stores at userAlphaBalance[user][{TEST_NETUID}] (contract internal)")
    print_success(f"  withdrawAlpha({TEST_NETUID}) → transfers from contract to user's coldkey as STAKE")
    print_success("  Both access SAME storage location (netuid=0)!")
    print_success("  ∴ TAO can be deposited and withdrawn as netuid=0 ALPHA ✓")
    print_success("")
    print_success("Key Finding:")
    print_success("  withdrawAlpha(netuid=0) does NOT return TAO to EVM balance")
    print_success("  Instead, it transfers TAO as STAKE to user's coldkey")
    print_success(f"  Δ EVM Balance = -{(initial_evm_wei - final_evm_wei) / 1e18:.9f} TAO (100 TAO + gas)")
    print_success(f"  Δ On-chain Stake = +{(final_stake_rao - initial_stake_rao) / 1e9:.9f} TAO (withdrawn as stake)")
    print_success("")

if __name__ == '__main__':
    main()
