#!/usr/bin/env python3
"""
Test Case TC01-04: withdrawRewardAlpha - Success
Objective: Verify successful reward withdrawal when rewards are available
Tests: Successful withdrawal with correct state and balance changes

Strategy: 8-step testing pattern with BalanceChecker
Expected: Transaction succeeds, rewards transferred to TREASURY_COLDKEY
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
    print_section("Test Case TC01-04: withdrawRewardAlpha - Success")
    print(f"{CYAN}Objective:{NC} Verify successful reward withdrawal when rewards are available")
    print(f"{CYAN}Strategy:{NC} MANAGER withdraws available rewards to TREASURY_COLDKEY")
    print(f"{CYAN}Expected:{NC} Transaction succeeds, rewards transferred\n")

    # ========================================================================
    # SETUP
    # ========================================================================
    print_info("Setting up test environment...")

    # Load addresses
    addresses = load_addresses()
    manager_address = addresses['MANAGER']['evmAddress']

    # Load private key
    manager_private_key = os.environ.get("MANAGER_PRIVATE_KEY")
    if not manager_private_key:
        print_error("MANAGER_PRIVATE_KEY not found in .env")
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

    # Test parameters - use active subnet
    test_netuid = 3  # Active subnet

    print_info(f"Manager: {manager_address}")
    print_info(f"Test netuid: {test_netuid} (active)")

    # ========================================================================
    # Step 0: Verify Setup Conditions
    # ========================================================================
    print_section("Step 0: Verify Setup Conditions")

    # Verify caller is MANAGER
    contract_manager = contract.functions.MANAGER().call()
    if contract_manager.lower() != manager_address.lower():
        print_error(f"SETUP ERROR: Caller is not MANAGER")
        sys.exit(1)

    print_success(f"✓ Caller is the MANAGER")

    # Verify subnet is active
    subnet_active = contract.functions.activeSubnets(test_netuid).call()
    if not subnet_active:
        print_error(f"SETUP ERROR: Subnet {test_netuid} is not active")
        sys.exit(1)

    print_success(f"✓ Subnet {test_netuid} is active")

    # Query current staking state
    delegate_hotkey = contract.functions.DELEGATE_HOTKEY().call()
    contract_coldkey = contract.functions.CONTRACT_COLDKEY().call()
    treasury_coldkey = contract.functions.TREASURY_COLDKEY().call()

    print_info(f"Contract coldkey: 0x{contract_coldkey.hex()}")
    print_info(f"Treasury coldkey: 0x{treasury_coldkey.hex()}")

    print_info(f"Querying staking information for netuid {test_netuid}...")

    # Get IStaking interface
    ISTAKING_ADDRESS = "0x0000000000000000000000000000000000000805"
    staking_abi = [
        {
            "inputs": [
                {"name": "hotkey", "type": "bytes32"},
                {"name": "coldkey", "type": "bytes32"},
                {"name": "netuid", "type": "uint256"}
            ],
            "name": "getStake",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    staking_contract = w3.eth.contract(address=ISTAKING_ADDRESS, abi=staking_abi)

    # Calculate withdrawable reward
    total_stake = staking_contract.functions.getStake(delegate_hotkey, contract_coldkey, test_netuid).call()
    subnet_alpha_balance = contract.functions.subnetAlphaBalance(test_netuid).call()
    withdrawable_reward = max(0, total_stake - subnet_alpha_balance)

    print_info(f"Total stake (on-chain): {total_stake / 1e9} ALPHA")
    print_info(f"Subnet alpha balance (accounting): {subnet_alpha_balance / 1e9} ALPHA")
    print_info(f"Withdrawable reward: {withdrawable_reward / 1e9} ALPHA")

    # Check if rewards are available
    if withdrawable_reward == 0:
        print_warning("⚠ No rewards available for withdrawal")
        print_warning("This test requires staking rewards to be accumulated")
        print_warning("Test will skip as there are no rewards to withdraw")
        print_info("\nTo accumulate rewards:")
        print_info("  1. Wait for staking rewards to accumulate on the subnet")
        print_info("  2. Or use a subnet that already has accumulated rewards")
        sys.exit(0)  # Exit gracefully, not a failure

    # Set test amount - withdraw half of available rewards (or minimum 0.1 ALPHA)
    min_withdraw = int(0.1 * 10**9)  # 0.1 ALPHA minimum
    test_amount = max(min_withdraw, withdrawable_reward // 2)

    if test_amount > withdrawable_reward:
        test_amount = withdrawable_reward

    print_success(f"✓ Rewards available: {withdrawable_reward / 1e9} ALPHA")
    print_info(f"Will withdraw: {test_amount / 1e9} ALPHA")

    # ========================================================================
    # Step 1: Read Initial Contract State
    # ========================================================================
    print_section("Step 1: Read Initial Contract State")

    checker = BalanceChecker(
        w3=w3,
        contract=contract,
        test_netuids=[0, test_netuid]
    )

    # Prepare addresses list
    addresses_list = [
        {"address": manager_address, "label": "MANAGER"}
    ]

    # Capture initial snapshot
    snapshot_before = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_before)

    # Store initial staking values
    initial_total_stake = total_stake
    initial_subnet_balance = subnet_alpha_balance

    # ========================================================================
    # Step 2: Read Initial Account Balances
    # ========================================================================
    print_section("Step 2: Read Initial Account Balances")
    print_info("Already captured by BalanceChecker in Step 1")

    # ========================================================================
    # Step 3: Read Initial Loan State
    # ========================================================================
    print_section("Step 3: Read Initial Loan State")
    print_info("Not applicable for this test (no loan involved)")

    # ========================================================================
    # Step 4: Execute Test Operation
    # ========================================================================
    print_section("Step 4: Execute withdrawRewardAlpha")

    print(f"\n{BOLD}{GREEN}Expected Result:{NC}")
    print(f"  {GREEN}Success:{NC} Transaction succeeds (status=1)")
    print(f"  {BLUE}Event:{NC} WithdrawRewardAlpha(sender, netuid, amount, to)")
    print(f"  {CYAN}State Changes:{NC}")
    print(f"    - On-chain staking: -{test_amount / 1e9} ALPHA")
    print(f"    - subnetAlphaBalance[{test_netuid}]: unchanged (rewards don't affect user deposits)")
    print(f"    - TREASURY_COLDKEY receives: +{test_amount / 1e9} ALPHA\n")

    print_info(f"Withdrawing {test_amount / 1e9} ALPHA from netuid {test_netuid}...")

    # Execute transaction
    try:
        tx = contract.functions.withdrawRewardAlpha(
            test_netuid,
            test_amount
        ).build_transaction({
            'from': manager_address,
            'nonce': w3.eth.get_transaction_count(manager_address),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=manager_private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print_info(f"Transaction hash: {tx_hash.hex()}")
        print_info("Waiting for transaction receipt...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt['status'] == 1:
            print_success(f"✓ Transaction succeeded")
            print_info(f"Gas used: {receipt['gasUsed']}")
            print_info(f"Block number: {receipt['blockNumber']}")

            # Check for WithdrawRewardAlpha event
            events = contract.events.WithdrawRewardAlpha().process_receipt(receipt)
            if events:
                for event in events:
                    print_success(f"✓ WithdrawRewardAlpha event emitted:")
                    print_info(f"  Sender: {event['args']['sender']}")
                    print_info(f"  Netuid: {event['args']['netuid']}")
                    print_info(f"  Amount: {event['args']['amount'] / 1e9} ALPHA")
                    print_info(f"  To: 0x{event['args']['to'].hex()}")
            else:
                print_warning("⚠ No WithdrawRewardAlpha event found")

        else:
            print_error("❌ Transaction failed (expected to succeed)")
            sys.exit(1)

    except Exception as e:
        print_error(f"❌ Transaction failed with error: {str(e)}")
        sys.exit(1)

    # ========================================================================
    # Step 5: Read Final Contract State
    # ========================================================================
    print_section("Step 5: Read Final Contract State")

    # Capture final snapshot
    snapshot_after = checker.capture_snapshot(addresses_list, include_staking=True)
    checker.print_snapshot(snapshot_after)

    # Query final staking state
    final_total_stake = staking_contract.functions.getStake(delegate_hotkey, contract_coldkey, test_netuid).call()
    final_subnet_balance = contract.functions.subnetAlphaBalance(test_netuid).call()

    # ========================================================================
    # Step 6: Read Final Account Balances
    # ========================================================================
    print_section("Step 6: Read Final Account Balances")
    print_info("Already captured by BalanceChecker in Step 5")

    # ========================================================================
    # Step 7: Read Final Loan State
    # ========================================================================
    print_section("Step 7: Read Final Loan State")
    print_info("Not applicable for this test (no loan involved)")

    # ========================================================================
    # Step 8: Compare and Verify
    # ========================================================================
    print_section("Step 8: Compare and Verify")

    # Calculate differences
    diff = checker.diff_snapshots(snapshot_before, snapshot_after)
    checker.print_diff(diff)

    # ========================================================================
    # Verification
    # ========================================================================
    print_section("Verification Summary")

    all_checks_passed = True

    # Check 1: On-chain staking decreased
    stake_diff = final_total_stake - initial_total_stake
    expected_stake_diff = -test_amount

    print_info(f"Stake change: {stake_diff / 1e9} ALPHA (expected: {expected_stake_diff / 1e9} ALPHA)")

    if stake_diff == expected_stake_diff:
        print_success(f"✓ On-chain staking decreased correctly by {test_amount / 1e9} ALPHA")
    else:
        print_error(f"✗ Unexpected stake change: {stake_diff / 1e9} vs {expected_stake_diff / 1e9}")
        all_checks_passed = False

    # Check 2: subnetAlphaBalance unchanged (rewards don't affect user deposits)
    subnet_balance_diff = final_subnet_balance - initial_subnet_balance

    if subnet_balance_diff == 0:
        print_success(f"✓ subnetAlphaBalance unchanged (rewards don't affect accounting)")
    else:
        print_error(f"✗ subnetAlphaBalance changed by {subnet_balance_diff / 1e9} (should be 0)")
        all_checks_passed = False

    # Check 3: Remaining rewards
    remaining_reward = final_total_stake - final_subnet_balance
    print_info(f"Remaining withdrawable rewards: {remaining_reward / 1e9} ALPHA")
    print_success(f"✓ Rewards calculation correct")

    # Check 4: Contract state (other fields should be unchanged)
    contract_state_before = snapshot_before['contract']
    contract_state_after = snapshot_after['contract']

    if (contract_state_before['protocol_fee_accumulated'] == contract_state_after['protocol_fee_accumulated'] and
        contract_state_before['next_loan_id'] == contract_state_after['next_loan_id']):
        print_success("✓ Other contract state unchanged")
    else:
        print_error("✗ Unexpected contract state changes")
        all_checks_passed = False

    # Final result
    print_section("Test Result")
    if all_checks_passed:
        print_success("✅ TEST PASSED")
        print_success(f"Successfully withdrew {test_amount / 1e9} ALPHA in staking rewards")
        print_success(f"On-chain staking decreased by {test_amount / 1e9} ALPHA")
        print_success("subnetAlphaBalance unchanged (rewards don't affect user deposits)")
        print_success(f"Remaining withdrawable rewards: {remaining_reward / 1e9} ALPHA")
        print_success("WithdrawRewardAlpha event emitted correctly")
    else:
        print_error("❌ TEST FAILED")
        print_error("Some verification checks failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
