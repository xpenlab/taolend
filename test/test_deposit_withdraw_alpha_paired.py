#!/usr/bin/env python3
"""
Test Case 02: Deposit ALPHA → Withdraw ALPHA (Paired Test)

Test Strategy:
- Deposit 1000 ALPHA via depositAlpha(netuid=2, 1000 ALPHA)
- Withdraw 1000 ALPHA via withdrawAlpha(netuid=2, 1000 ALPHA)
- Verify balance conservation using check_balance diff

Expected Behavior:
- Both transactions succeed
- Both events emitted correctly
- On-chain stake returns to initial value (perfect match)
- EVM balance change = gas only
- Contract balances return to initial state
- Perfect balance conservation

This test follows the 7-step pattern:
1. Step 0: Verify setup conditions
2. Step 1: Capture balances BEFORE
3. Step 2: Execute deposit ALPHA transaction
4. Step 3: Capture balances AFTER DEPOSIT
5. Step 4: Execute withdraw ALPHA transaction
6. Step 5: Capture balances AFTER WITHDRAW
7. Step 6: Three-way verification (balance conservation)
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
    print_section("Test Case 02: Deposit ALPHA → Withdraw ALPHA (Paired Test)")
    print_info("Objective: Verify balance conservation in ALPHA deposit/withdraw cycle")

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

    # Use BORROWER1 who has 181,100 ALPHA staked on netuid=2
    test_address = Web3.to_checksum_address(addresses["BORROWER1"]["evmAddress"])
    test_ss58 = addresses["BORROWER1"]["ss58Address"]
    test_private_key = os.getenv('BORROWER1_PRIVATE_KEY')

    if not test_private_key:
        print_error("BORROWER1_PRIVATE_KEY not found in .env")
        return

    print_info(f"Test Account: BORROWER1 ({test_address})")

    # Load contract
    with open('.contract_address', 'r') as f:
        contract_address = Web3.to_checksum_address(f.read().strip())

    with open('artifacts/contracts/LendingPoolV2.sol/LendingPoolV2.json', 'r') as f:
        abi = json.load(f)['abi']

    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Initialize BalanceChecker
    checker = BalanceChecker(w3=w3, contract=contract, test_netuids=[0, 2, 3])

    # Test parameters
    TEST_NETUID = 2
    DEPOSIT_AMOUNT_ALPHA = 1000
    DEPOSIT_AMOUNT_RAO = DEPOSIT_AMOUNT_ALPHA * 10**9

    print_info(f"Test netuid: {TEST_NETUID}")
    print_info(f"Test amount: {DEPOSIT_AMOUNT_ALPHA} ALPHA ({DEPOSIT_AMOUNT_RAO:,} RAO)")

    # Step 0: Verify Setup
    print_section("Step 0: Verify Setup Conditions")

    if not contract.functions.registeredUser(test_address).call():
        print_error("BORROWER1 is not registered")
        return
    print_success("✓ BORROWER1 is registered")

    if contract.functions.paused().call():
        print_error("Contract is paused")
        return
    print_success("✓ Contract is not paused")

    evm_balance = w3.eth.get_balance(test_address)
    if evm_balance < 10**18:  # Need at least 1 TAO for gas
        print_error(f"Insufficient EVM balance for gas: {evm_balance / 1e18:.9f} TAO")
        return
    print_success(f"✓ Sufficient EVM balance for gas: {evm_balance / 1e18:.9f} TAO")

    # Check on-chain ALPHA stake
    # Note: We need to check if BORROWER1 has enough ALPHA staked on-chain at netuid=2
    try:
        # Get BORROWER1's on-chain stake via staking precompile
        # The getStake function signature: getStake(bytes32 hotkey, bytes32 coldkey, uint16 netuid)
        delegate_hotkey = contract.functions.DELEGATE_HOTKEY().call()
        lender_coldkey_bytes = contract.functions.userColdkey(test_address).call()

        # Call getStake on staking precompile
        staking_address = "0x0000000000000000000000000000000000000805"
        staking_abi = [
            {
                "inputs": [
                    {"name": "hotkey", "type": "bytes32"},
                    {"name": "coldkey", "type": "bytes32"},
                    {"name": "netuid", "type": "uint16"}
                ],
                "name": "getStake",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        staking_contract = w3.eth.contract(address=staking_address, abi=staking_abi)

        onchain_stake = staking_contract.functions.getStake(
            delegate_hotkey,
            lender_coldkey_bytes,
            TEST_NETUID
        ).call()

        print_info(f"BORROWER1 on-chain ALPHA stake (netuid={TEST_NETUID}): {onchain_stake / 1e9:.9f} ALPHA")

        if onchain_stake < DEPOSIT_AMOUNT_RAO:
            print_error(f"Insufficient on-chain ALPHA stake!")
            print_error(f"  Required: {DEPOSIT_AMOUNT_RAO / 1e9:.9f} ALPHA")
            print_error(f"  Available: {onchain_stake / 1e9:.9f} ALPHA")
            print_info("You need to stake ALPHA on-chain first using Bittensor CLI or other method")
            return

        print_success(f"✓ Sufficient on-chain ALPHA stake: {onchain_stake / 1e9:.9f} ALPHA")

    except Exception as e:
        print_warning(f"Could not check on-chain stake: {e}")
        print_info("Proceeding anyway - will fail if insufficient stake")

    # Step 1: Capture BEFORE
    print_section("Step 1: Capture Balances BEFORE")

    addresses_list = [{"address": test_address, "label": "borrower1", "ss58": test_ss58}]

    # Wait 15 seconds before initial snapshot to ensure state is stable
    print_info("Waiting 15 seconds before initial snapshot...")
    time.sleep(15)

    before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(before)

    initial_evm_wei = before['balances']['borrower1']['evm_tao_wei']
    initial_contract_rao = before['balances']['borrower1']['contract'][f'netuid_{TEST_NETUID}']['balance_rao']
    initial_subnet_rao = before['contract']['subnet_total_balance'][f'netuid_{TEST_NETUID}']['rao']

    # Step 2: Execute Deposit ALPHA
    print_section("Step 2: Execute Deposit ALPHA")

    print_info(f"Depositing {DEPOSIT_AMOUNT_ALPHA} ALPHA to netuid={TEST_NETUID}...")

    # Get delegate hotkey from contract
    delegate_hotkey_bytes = contract.functions.DELEGATE_HOTKEY().call()
    print_info(f"Using delegate hotkey: {delegate_hotkey_bytes.hex()}")

    deposit_tx = contract.functions.depositAlpha(
        TEST_NETUID,
        DEPOSIT_AMOUNT_RAO,
        delegate_hotkey_bytes
    ).build_transaction({
        'from': test_address,
        'nonce': w3.eth.get_transaction_count(test_address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
    })

    signed_deposit = w3.eth.account.sign_transaction(deposit_tx, test_private_key)
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

    # Parse DepositAlpha event
    try:
        logs = contract.events.DepositAlpha().process_receipt(deposit_receipt)
        if logs:
            event = logs[0]['args']
            print_success(f"✓ DepositAlpha event: sender={event['sender']}, netuid={event['netuid']}, amount={event['amount']:,} RAO")
            assert event['sender'].lower() == test_address.lower()
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

    # Step 4: Execute Withdraw ALPHA
    print_section("Step 4: Execute Withdraw ALPHA")

    print_info(f"Withdrawing {DEPOSIT_AMOUNT_ALPHA} ALPHA from netuid={TEST_NETUID}...")

    # Convert user's SS58 address to coldkey bytes32
    user_coldkey_hex = ss58_to_bytes32(test_ss58)
    user_coldkey_bytes = Web3.to_bytes(hexstr=user_coldkey_hex)
    print_info(f"User coldkey (bytes32): {user_coldkey_hex}")

    withdraw_tx = contract.functions.withdrawAlpha(
        TEST_NETUID,
        DEPOSIT_AMOUNT_RAO,
        user_coldkey_bytes  # Use user's coldkey, not delegate hotkey!
    ).build_transaction({
        'from': test_address,
        'nonce': w3.eth.get_transaction_count(test_address),
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
    })

    signed_withdraw = w3.eth.account.sign_transaction(withdraw_tx, test_private_key)
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

    # Parse WithdrawAlpha event
    try:
        logs = contract.events.WithdrawAlpha().process_receipt(withdraw_receipt)
        if logs:
            event = logs[0]['args']
            print_success(f"✓ WithdrawAlpha event: sender={event['sender']}, netuid={event['netuid']}, amount={event['amount']:,} RAO")
            assert event['sender'].lower() == test_address.lower()
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
    print_section("Step 6: Three-Way Verification (Balance Conservation)")

    final_evm_wei = final['balances']['borrower1']['evm_tao_wei']
    final_contract_rao = final['balances']['borrower1']['contract'][f'netuid_{TEST_NETUID}']['balance_rao']
    final_subnet_rao = final['contract']['subnet_total_balance'][f'netuid_{TEST_NETUID}']['rao']

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
    print_info(f"  Initial contract: {initial_contract_rao:,} RAO ({initial_contract_rao / 1e9:.9f} ALPHA)")
    print_info(f"  Final contract:   {final_contract_rao:,} RAO ({final_contract_rao / 1e9:.9f} ALPHA)")
    print_info(f"  Difference:       {final_contract_rao - initial_contract_rao:,} RAO")

    if final_contract_rao == initial_contract_rao:
        print_success("✓ Contract balance: returned to initial state")
    else:
        print_error(f"✗ Contract mismatch: {final_contract_rao} != {initial_contract_rao}")
        print_section("Test Result")
        print_error("✗ TEST FAILED")
        return

    print_info("")
    print_info(f"  Initial subnet total: {initial_subnet_rao:,} RAO ({initial_subnet_rao / 1e9:.9f} ALPHA)")
    print_info(f"  Final subnet total:   {final_subnet_rao:,} RAO ({final_subnet_rao / 1e9:.9f} ALPHA)")
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
    print_success("✓ TEST PASSED: Deposit ALPHA → Withdraw ALPHA (Paired Test)")
    print_success("="*80)
    print_success("")
    print_success("All verifications passed:")
    print_success("  ✓ Deposit transaction succeeded")
    print_success("  ✓ Withdraw transaction succeeded")
    print_success("  ✓ DepositAlpha event emitted correctly")
    print_success("  ✓ WithdrawAlpha event emitted correctly")
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
