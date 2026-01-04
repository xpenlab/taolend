#!/usr/bin/env python3
"""
Balance Checker Library - Unified balance query library

This library provides complete balance query functionality with modular design:

Core Functions:
1. get_address_balances(address) - Get all balances for a single address
2. get_all_balances(addresses_with_labels) - Batch get balances for multiple addresses
3. get_contract_state() - Get contract state (fee, total balances)
4. Returns dict/json format for easy post-processing (table printing, diff, etc.)

Use Cases:
- Capture before/after state in test scripts and perform diff verification
- Display all account balances in standalone scripts
- Generate balance reports

Basic Usage:
    from balance_checker import BalanceChecker

    # Create checker
    checker = BalanceChecker(w3, contract, test_netuids=[0, 2, 3])

    # Get single address balances
    balances = checker.get_address_balances(address)

    # Batch get balances (with labels)
    addresses = [
        {"address": "0x123...", "label": "lender"},
        {"address": "0x456...", "label": "borrower"}
    ]
    all_balances = checker.get_all_balances(addresses)

    # Get contract state
    contract_state = checker.get_contract_state()

    # Combine into complete snapshot
    snapshot = {
        "balances": all_balances,
        "contract": contract_state,
        "block": w3.eth.block_number
    }

    # Save as JSON or perform diff
    import json
    print(json.dumps(snapshot, indent=2))
"""

import os
import sys
import json
from pathlib import Path
from web3 import Web3
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple

# Add scripts directory to path
sys.path.append(str(Path(__file__).parent))
from const import LENDING_POOL_V2_ADDRESS, ISTAKING_V2_ADDRESS
from balance_utils import rao_to_tao, format_tao

# ANSI Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;36m"
CYAN = "\033[0;96m"
MAGENTA = "\033[0;35m"
BOLD = "\033[1m"
NC = "\033[0m"


def ss58_to_bytes32(ss58_address: str) -> Optional[bytes]:
    """Convert SS58 address to bytes32"""
    try:
        from substrateinterface import Keypair
        keypair = Keypair(ss58_address=ss58_address)
        return Web3.to_bytes(hexstr="0x" + keypair.public_key.hex())
    except Exception as e:
        return None


def bytes32_to_ss58(bytes32_data) -> Optional[str]:
    """Convert bytes32 to SS58 address"""
    try:
        from substrateinterface import Keypair

        if isinstance(bytes32_data, str):
            if bytes32_data.startswith('0x'):
                bytes32_data = bytes32_data[2:]
            public_key_bytes = bytes.fromhex(bytes32_data)
        else:
            public_key_bytes = bytes32_data

        keypair = Keypair(public_key=public_key_bytes, ss58_format=42)
        return keypair.ss58_address
    except Exception:
        return None


def load_addresses_json() -> Optional[List[Dict]]:
    """Load addresses from addresses.json"""
    addresses_path = Path(__file__).parent.parent / "addresses.json"
    if not addresses_path.exists():
        return None

    try:
        with open(addresses_path, "r") as f:
            data = json.load(f)
        return data["accounts"]
    except Exception:
        return None


class BalanceChecker:
    """
    Modular Balance Checker

    Design Philosophy:
    1. Core function: get_address_balances() - Get all balances for a single address
    2. Batch query: get_all_balances() - Query multiple addresses
    3. Contract state: get_contract_state() - Query contract fee and total balances
    4. Returns dict: All functions return dict/json for easy post-processing
    """

    def __init__(self, w3: Web3, contract: Any,
                 test_netuids: Optional[List[int]] = None):
        """
        Initialize balance checker

        Args:
            w3: Web3 instance
            contract: LendingPoolV2 contract instance
            test_netuids: List of netuids to track (default: [0, 2, 3])
        """
        self.w3 = w3
        self.contract = contract
        self.test_netuids = test_netuids or [0, 2, 3]

        # Get contract info
        try:
            self.contract_coldkey_bytes = contract.functions.CONTRACT_COLDKEY().call()
            self.delegate_hotkey_bytes = contract.functions.DELEGATE_HOTKEY().call()
        except Exception as e:
            print(f"{RED}[ERROR] Failed to get contract info: {e}{NC}")
            raise

        # Create staking contract interface
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
        self.staking_contract = w3.eth.contract(address=ISTAKING_V2_ADDRESS, abi=staking_abi)

        # Load addresses.json for coldkey lookup
        self.addresses_info = {}
        accounts = load_addresses_json()
        if accounts:
            for acc in accounts:
                self.addresses_info[acc["evmAddress"]] = acc

    def _query_stake(self, hotkey_bytes: bytes, coldkey_bytes: bytes, netuid: int) -> int:
        """Query on-chain stake (returns rao)"""
        try:
            stake_rao = self.staking_contract.functions.getStake(
                hotkey_bytes,
                coldkey_bytes,
                netuid
            ).call()
            return stake_rao
        except Exception:
            return 0

    def get_address_balances(self, address: str,
                            include_staking: bool = True,
                            ss58_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all balances for a single address

        Args:
            address: EVM address
            include_staking: Whether to include on-chain staking balances (requires ss58_address)
            ss58_address: Optional SS58 address (for querying staking)

        Returns:
            {
                "address": "0x...",
                "evm_tao_wei": 123,  # EVM wallet TAO balance (wei unit)
                "evm_tao": 0.123,    # EVM wallet TAO balance (TAO unit)
                "contract": {
                    "netuid_0": {
                        "balance_rao": 456,  # Contract internal balance (rao unit)
                        "balance_tao": 0.456  # Contract internal balance (TAO unit)
                    },
                    "netuid_2": {...},
                    "netuid_3": {...}
                },
                "staking": {  # If include_staking=True and ss58_address is provided
                    "netuid_0": {
                        "stake_rao": 789,
                        "stake_tao": 0.789
                    },
                    "netuid_2": {...},
                    "netuid_3": {...}
                }
            }
        """
        result = {
            "address": address,
            "contract": {},
        }

        # 1. EVM TAO balance (in wei)
        try:
            evm_balance_wei = self.w3.eth.get_balance(address)
            result["evm_tao_wei"] = evm_balance_wei
            result["evm_tao"] = float(self.w3.from_wei(evm_balance_wei, 'ether'))
        except Exception as e:
            result["evm_tao_wei"] = 0
            result["evm_tao"] = 0.0
            result["evm_error"] = str(e)

        # 2. Contract internal balances (userAlphaBalance)
        for netuid in self.test_netuids:
            netuid_key = f"netuid_{netuid}"
            try:
                balance_rao = self.contract.functions.userAlphaBalance(address, netuid).call()
                result["contract"][netuid_key] = {
                    "balance_rao": balance_rao,
                    "balance_tao": float(rao_to_tao(balance_rao))
                }
            except Exception as e:
                result["contract"][netuid_key] = {
                    "balance_rao": 0,
                    "balance_tao": 0.0,
                    "error": str(e)
                }

        # 3. On-chain staking balances (if requested)
        if include_staking:
            result["staking"] = {}

            # Try to get ss58 address
            if ss58_address is None and address in self.addresses_info:
                ss58_address = self.addresses_info[address].get("ss58Address")

            if ss58_address:
                coldkey_bytes = ss58_to_bytes32(ss58_address)
                if coldkey_bytes:
                    for netuid in self.test_netuids:
                        netuid_key = f"netuid_{netuid}"
                        stake_rao = self._query_stake(
                            self.delegate_hotkey_bytes,
                            coldkey_bytes,
                            netuid
                        )
                        result["staking"][netuid_key] = {
                            "stake_rao": stake_rao,
                            "stake_tao": float(rao_to_tao(stake_rao))
                        }
                else:
                    result["staking_error"] = "Failed to convert SS58 to bytes32"
            else:
                result["staking_error"] = "No SS58 address provided"

        return result

    def get_all_balances(self, addresses_with_labels: List[Dict[str, str]],
                        include_staking: bool = True) -> Dict[str, Any]:
        """
        Batch get balances for multiple addresses

        Args:
            addresses_with_labels: Address list in format:
                [
                    {"address": "0x123...", "label": "lender"},
                    {"address": "0x456...", "label": "borrower"}
                ]
                Or auto-load from addresses.json (if None)
            include_staking: Whether to include on-chain staking balances

        Returns:
            {
                "lender": {
                    "address": "0x123...",
                    "evm_tao_wei": ...,
                    "contract": {...},
                    "staking": {...}
                },
                "borrower": {...}
            }
        """
        result = {}

        for item in addresses_with_labels:
            address = item["address"]
            label = item["label"]

            # Try to get ss58 address from addresses.json
            ss58_address = None
            if address in self.addresses_info:
                ss58_address = self.addresses_info[address].get("ss58Address")

            balances = self.get_address_balances(
                address,
                include_staking=include_staking,
                ss58_address=ss58_address
            )

            # Add label to result
            balances["label"] = label
            result[label] = balances

        return result

    def get_contract_state(self) -> Dict[str, Any]:
        """
        Get contract state (protocol fee, total balances, staking, etc.)

        Returns:
            {
                "address": "0x...",
                "block_number": 123,
                "evm_balance": {
                    "wei": 456,
                    "tao": 0.456
                },
                "protocol_fee_accumulated": {
                    "fee_rao": 789,
                    "fee_tao": 0.789
                },
                "subnet_total_balance": {  # subnetAlphaBalance
                    "netuid_0": {"rao": 100, "tao": 0.1},
                    "netuid_2": {"rao": 200, "tao": 0.2},
                    "netuid_3": {"rao": 300, "tao": 0.3}
                },
                "subnet_staking": {  # Contract's actual on-chain stake
                    "netuid_0": {"rao": 120, "tao": 0.12},
                    "netuid_2": {"rao": 220, "tao": 0.22},
                    "netuid_3": {"rao": 320, "tao": 0.32}
                },
                "next_loan_id": 5
            }
        """
        result = {
            "address": LENDING_POOL_V2_ADDRESS,
            "block_number": self.w3.eth.block_number,
        }

        # 1. Contract EVM balance
        try:
            evm_balance = self.w3.eth.get_balance(LENDING_POOL_V2_ADDRESS)
            result["evm_balance"] = {
                "wei": evm_balance,
                "tao": float(self.w3.from_wei(evm_balance, 'ether'))
            }
        except Exception as e:
            result["evm_balance"] = {"wei": 0, "tao": 0.0, "error": str(e)}

        # 2. Protocol Fee Accumulated (protocolFeeAccumulated)
        try:
            fee_rao = self.contract.functions.protocolFeeAccumulated().call()
            result["protocol_fee_accumulated"] = {
                "fee_rao": fee_rao,
                "fee_tao": float(rao_to_tao(fee_rao))
            }
        except Exception as e:
            result["protocol_fee_accumulated"] = {"fee_rao": 0, "fee_tao": 0.0, "error": str(e)}

        # 3. Subnet total balances (subnetAlphaBalance) - Contract internal accounting
        result["subnet_total_balance"] = {}
        for netuid in self.test_netuids:
            netuid_key = f"netuid_{netuid}"
            try:
                balance_rao = self.contract.functions.subnetAlphaBalance(netuid).call()
                result["subnet_total_balance"][netuid_key] = {
                    "rao": balance_rao,
                    "tao": float(rao_to_tao(balance_rao))
                }
            except Exception as e:
                result["subnet_total_balance"][netuid_key] = {
                    "rao": 0,
                    "tao": 0.0,
                    "error": str(e)
                }

        # 4. Contract staking (Contract's actual on-chain stake)
        result["subnet_staking"] = {}
        for netuid in self.test_netuids:
            netuid_key = f"netuid_{netuid}"
            stake_rao = self._query_stake(
                self.delegate_hotkey_bytes,
                self.contract_coldkey_bytes,
                netuid
            )
            result["subnet_staking"][netuid_key] = {
                "rao": stake_rao,
                "tao": float(rao_to_tao(stake_rao))
            }

        # 5. Next loan ID
        try:
            result["next_loan_id"] = self.contract.functions.nextLoanId().call()
        except Exception as e:
            result["next_loan_id"] = 0
            result["next_loan_id_error"] = str(e)

        return result

    def capture_snapshot(self,
                        addresses_with_labels: Optional[List[Dict[str, str]]] = None,
                        include_staking: bool = True) -> Dict[str, Any]:
        """
        Capture complete snapshot (combine all information)

        Args:
            addresses_with_labels: Address list (if None, load from addresses.json)
            include_staking: Whether to include staking information

        Returns:
            {
                "block_number": 123,
                "timestamp": 1234567890,
                "contract": {...},  # Contract state
                "balances": {...}   # All address balances
            }
        """
        # Load addresses if not provided
        if addresses_with_labels is None:
            accounts = load_addresses_json()
            if accounts:
                addresses_with_labels = [
                    {"address": acc["evmAddress"], "label": acc["name"]}
                    for acc in accounts
                ]
            else:
                addresses_with_labels = []

        snapshot = {
            "block_number": self.w3.eth.block_number,
            "timestamp": self.w3.eth.get_block('latest')['timestamp'],
            "contract": self.get_contract_state(),
            "balances": self.get_all_balances(addresses_with_labels, include_staking)
        }

        return snapshot

    def print_snapshot(self, snapshot: Dict[str, Any]):
        """
        Print snapshot in readable format

        Args:
            snapshot: Snapshot dict returned by capture_snapshot()
        """
        print(f"\n{BOLD}{CYAN}{'=' * 100}{NC}")
        print(f"{BOLD}{CYAN}Balance Snapshot{NC}")
        print(f"{BOLD}{CYAN}{'=' * 100}{NC}")
        print(f"{BOLD}Block Number:{NC} {snapshot['block_number']}")
        print(f"{BOLD}Timestamp:{NC} {snapshot['timestamp']}")

        # Contract state
        print(f"\n{BOLD}{'─' * 100}{NC}")
        print(f"{BOLD}Contract State ({LENDING_POOL_V2_ADDRESS}):{NC}")
        print(f"{BOLD}{'─' * 100}{NC}")

        contract = snapshot["contract"]
        print(f"  EVM Balance:              {contract['evm_balance']['tao']:>20.9f} TAO")
        print(f"  Protocol Fee Accumulated: {contract['protocol_fee_accumulated']['fee_tao']:>20.9f} TAO")
        print(f"  Next Loan ID:             {contract['next_loan_id']:>20}")

        print(f"\n  {BOLD}Internal Accounting (subnetAlphaBalance):{NC}")
        for netuid_key in sorted(contract['subnet_total_balance'].keys()):
            data = contract['subnet_total_balance'][netuid_key]
            netuid = int(netuid_key.split('_')[1])
            unit = "TAO" if netuid == 0 else "ALPHA"
            label = f"netuid={netuid} ({unit}):"
            print(f"    {label:<20} {data['tao']:>20.9f} {unit}")

        print(f"\n  {BOLD}On-chain Staking:{NC}")
        for netuid_key in sorted(contract['subnet_staking'].keys()):
            data = contract['subnet_staking'][netuid_key]
            netuid = int(netuid_key.split('_')[1])
            unit = "TAO" if netuid == 0 else "ALPHA"
            label = f"netuid={netuid} ({unit}):"
            print(f"    {label:<20} {data['tao']:>20.9f} {unit}")

        # User balances
        print(f"\n{BOLD}{'─' * 100}{NC}")
        print(f"{BOLD}User Balances:{NC}")
        print(f"{BOLD}{'─' * 100}{NC}")

        for label, data in snapshot["balances"].items():
            print(f"\n  {BOLD}{label} ({data['address']}):{NC}")
            print(f"    EVM Balance:              {data['evm_tao']:>20.9f} TAO")

            print(f"    {BOLD}Contract Balances:{NC}")
            for netuid_key in sorted(data['contract'].keys()):
                contract_data = data['contract'][netuid_key]
                netuid = int(netuid_key.split('_')[1])
                unit = "TAO" if netuid == 0 else "ALPHA"
                label_text = f"netuid={netuid} ({unit}):"
                print(f"      {label_text:<18} {contract_data['balance_tao']:>20.9f} {unit}")

            if "staking" in data and data["staking"]:
                print(f"    {BOLD}{MAGENTA}On-chain Staking:{NC}")
                for netuid_key in sorted(data['staking'].keys()):
                    stake_data = data['staking'][netuid_key]
                    netuid = int(netuid_key.split('_')[1])
                    unit = "TAO" if netuid == 0 else "ALPHA"
                    label_text = f"netuid={netuid} ({unit}):"
                    print(f"      {label_text:<18} {stake_data['stake_tao']:>20.9f} {unit}")

        print(f"\n{BOLD}{CYAN}{'=' * 100}{NC}\n")

    def diff_snapshots(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate difference between two snapshots

        Args:
            before: Before snapshot
            after: After snapshot

        Returns:
            {
                "block_diff": 5,
                "contract": {
                    "evm_balance_diff_wei": 100,
                    "evm_balance_diff_tao": 0.0001,
                    "fee_diff_rao": 50,
                    "fee_diff_tao": 0.00005,
                    "next_loan_id_diff": 1,
                    "subnet_total_balance_diff": {...},
                    "subnet_staking_diff": {...}
                },
                "balances": {
                    "lender": {
                        "evm_tao_diff_wei": -100,
                        "evm_tao_diff": -0.0001,
                        "contract": {
                            "netuid_0": {"diff_rao": 50, "diff_tao": 0.00005},
                            ...
                        },
                        "staking": {...}
                    },
                    ...
                }
            }
        """
        diff = {
            "block_diff": after["block_number"] - before["block_number"],
            "timestamp_diff": after["timestamp"] - before["timestamp"],
            "contract": {},
            "balances": {}
        }

        # Contract state diff
        c_before = before["contract"]
        c_after = after["contract"]

        diff["contract"]["evm_balance_diff_wei"] = c_after["evm_balance"]["wei"] - c_before["evm_balance"]["wei"]
        diff["contract"]["evm_balance_diff_tao"] = c_after["evm_balance"]["tao"] - c_before["evm_balance"]["tao"]
        diff["contract"]["protocol_fee_diff_rao"] = c_after["protocol_fee_accumulated"]["fee_rao"] - c_before["protocol_fee_accumulated"]["fee_rao"]
        diff["contract"]["protocol_fee_diff_tao"] = c_after["protocol_fee_accumulated"]["fee_tao"] - c_before["protocol_fee_accumulated"]["fee_tao"]
        diff["contract"]["next_loan_id_diff"] = c_after["next_loan_id"] - c_before["next_loan_id"]

        # Subnet balance diffs
        diff["contract"]["subnet_total_balance_diff"] = {}
        for netuid_key in c_before["subnet_total_balance"].keys():
            before_val = c_before["subnet_total_balance"][netuid_key]
            after_val = c_after["subnet_total_balance"][netuid_key]
            diff["contract"]["subnet_total_balance_diff"][netuid_key] = {
                "diff_rao": after_val["rao"] - before_val["rao"],
                "diff_tao": after_val["tao"] - before_val["tao"]
            }

        # Subnet staking diffs
        diff["contract"]["subnet_staking_diff"] = {}
        for netuid_key in c_before["subnet_staking"].keys():
            before_val = c_before["subnet_staking"][netuid_key]
            after_val = c_after["subnet_staking"][netuid_key]
            diff["contract"]["subnet_staking_diff"][netuid_key] = {
                "diff_rao": after_val["rao"] - before_val["rao"],
                "diff_tao": after_val["tao"] - before_val["tao"]
            }

        # User balance diffs
        for label in before["balances"].keys():
            if label not in after["balances"]:
                continue

            b_before = before["balances"][label]
            b_after = after["balances"][label]

            user_diff = {
                "address": b_before["address"],
                "evm_tao_diff_wei": b_after["evm_tao_wei"] - b_before["evm_tao_wei"],
                "evm_tao_diff": b_after["evm_tao"] - b_before["evm_tao"],
                "contract": {},
            }

            # Contract balance diffs
            for netuid_key in b_before["contract"].keys():
                before_val = b_before["contract"][netuid_key]
                after_val = b_after["contract"][netuid_key]
                user_diff["contract"][netuid_key] = {
                    "diff_rao": after_val["balance_rao"] - before_val["balance_rao"],
                    "diff_tao": after_val["balance_tao"] - before_val["balance_tao"]
                }

            # Staking diffs (if available)
            if "staking" in b_before and "staking" in b_after:
                user_diff["staking"] = {}
                for netuid_key in b_before["staking"].keys():
                    before_val = b_before["staking"][netuid_key]
                    after_val = b_after["staking"][netuid_key]
                    user_diff["staking"][netuid_key] = {
                        "diff_rao": after_val["stake_rao"] - before_val["stake_rao"],
                        "diff_tao": after_val["stake_tao"] - before_val["stake_tao"]
                    }

            diff["balances"][label] = user_diff

        return diff

    def print_diff(self, diff: Dict[str, Any], show_zero_changes: bool = False):
        """
        Print difference in readable format

        Args:
            diff: Difference dict returned by diff_snapshots()
            show_zero_changes: Whether to show items with no changes
        """
        print(f"\n{BOLD}{CYAN}{'=' * 100}{NC}")
        print(f"{BOLD}{CYAN}Balance Changes{NC}")
        print(f"{BOLD}{CYAN}{'=' * 100}{NC}")
        print(f"{BOLD}Block Diff:{NC} {diff['block_diff']}")
        print(f"{BOLD}Time Diff:{NC} {diff['timestamp_diff']} seconds")

        # Contract changes
        print(f"\n{BOLD}{'─' * 100}{NC}")
        print(f"{BOLD}Contract State Changes:{NC}")
        print(f"{BOLD}{'─' * 100}{NC}")

        contract_diff = diff["contract"]

        # EVM balance
        evm_diff = contract_diff["evm_balance_diff_tao"]
        if evm_diff != 0 or show_zero_changes:
            color = GREEN if evm_diff > 0 else RED if evm_diff < 0 else NC
            sign = "+" if evm_diff > 0 else ""
            print(f"  EVM Balance:              {color}{sign}{evm_diff:>20.9f} TAO{NC}")

        # Protocol Fee Accumulated
        fee_diff = contract_diff["protocol_fee_diff_tao"]
        if fee_diff != 0 or show_zero_changes:
            color = GREEN if fee_diff > 0 else RED if fee_diff < 0 else NC
            sign = "+" if fee_diff > 0 else ""
            print(f"  Protocol Fee Accumulated: {color}{sign}{fee_diff:>20.9f} TAO{NC}")

        # Next loan ID
        loan_id_diff = contract_diff["next_loan_id_diff"]
        if loan_id_diff != 0 or show_zero_changes:
            color = GREEN if loan_id_diff > 0 else NC
            sign = "+" if loan_id_diff > 0 else ""
            print(f"  Next Loan ID:             {color}{sign}{loan_id_diff:>20}{NC}")

        # Subnet balance diffs
        print(f"\n  {BOLD}Internal Accounting Changes:{NC}")
        for netuid_key in sorted(contract_diff["subnet_total_balance_diff"].keys()):
            data = contract_diff["subnet_total_balance_diff"][netuid_key]
            netuid = int(netuid_key.split('_')[1])
            unit = "TAO" if netuid == 0 else "ALPHA"
            diff_val = data["diff_tao"]
            if diff_val != 0 or show_zero_changes:
                color = GREEN if diff_val > 0 else RED if diff_val < 0 else NC
                sign = "+" if diff_val > 0 else ""
                label = f"netuid={netuid} ({unit}):"
                print(f"    {label:<20} {color}{sign}{diff_val:>20.9f} {unit}{NC}")

        # Subnet staking diffs
        print(f"\n  {BOLD}On-chain Staking Changes:{NC}")
        for netuid_key in sorted(contract_diff["subnet_staking_diff"].keys()):
            data = contract_diff["subnet_staking_diff"][netuid_key]
            netuid = int(netuid_key.split('_')[1])
            unit = "TAO" if netuid == 0 else "ALPHA"
            diff_val = data["diff_tao"]
            if diff_val != 0 or show_zero_changes:
                color = GREEN if diff_val > 0 else RED if diff_val < 0 else NC
                sign = "+" if diff_val > 0 else ""
                label = f"netuid={netuid} ({unit}):"
                print(f"    {label:<20} {color}{sign}{diff_val:>20.9f} {unit}{NC}")

        # User balance changes
        print(f"\n{BOLD}{'─' * 100}{NC}")
        print(f"{BOLD}User Balance Changes:{NC}")
        print(f"{BOLD}{'─' * 100}{NC}")

        for label, data in diff["balances"].items():
            # Check if user has any changes
            has_changes = False
            if data["evm_tao_diff"] != 0:
                has_changes = True
            for netuid_key, contract_data in data["contract"].items():
                if contract_data["diff_tao"] != 0:
                    has_changes = True
            if "staking" in data:
                for netuid_key, stake_data in data["staking"].items():
                    if stake_data["diff_tao"] != 0:
                        has_changes = True

            if not has_changes and not show_zero_changes:
                continue

            print(f"\n  {BOLD}{label} ({data['address']}):{NC}")

            # EVM balance change
            evm_diff = data["evm_tao_diff"]
            if evm_diff != 0 or show_zero_changes:
                color = GREEN if evm_diff > 0 else RED if evm_diff < 0 else NC
                sign = "+" if evm_diff > 0 else ""
                print(f"    EVM Balance:              {color}{sign}{evm_diff:>20.9f} TAO{NC}")

            # Contract balance changes
            print(f"    {BOLD}Contract Balance Changes:{NC}")
            for netuid_key in sorted(data["contract"].keys()):
                contract_data = data["contract"][netuid_key]
                netuid = int(netuid_key.split('_')[1])
                unit = "TAO" if netuid == 0 else "ALPHA"
                diff_val = contract_data["diff_tao"]
                if diff_val != 0 or show_zero_changes:
                    color = GREEN if diff_val > 0 else RED if diff_val < 0 else NC
                    sign = "+" if diff_val > 0 else ""
                    label_text = f"netuid={netuid} ({unit}):"
                    print(f"      {label_text:<18} {color}{sign}{diff_val:>20.9f} {unit}{NC}")

            # Staking changes
            if "staking" in data:
                has_stake_changes = any(
                    stake_data["diff_tao"] != 0
                    for stake_data in data["staking"].values()
                )
                if has_stake_changes or show_zero_changes:
                    print(f"    {BOLD}{MAGENTA}Staking Changes:{NC}")
                    for netuid_key in sorted(data["staking"].keys()):
                        stake_data = data["staking"][netuid_key]
                        netuid = int(netuid_key.split('_')[1])
                        unit = "TAO" if netuid == 0 else "ALPHA"
                        diff_val = stake_data["diff_tao"]
                        if diff_val != 0 or show_zero_changes:
                            color = GREEN if diff_val > 0 else RED if diff_val < 0 else NC
                            sign = "+" if diff_val > 0 else ""
                            label_text = f"netuid={netuid} ({unit}):"
                            print(f"      {label_text:<18} {color}{sign}{diff_val:>20.9f} {unit}{NC}")

        print(f"\n{BOLD}{CYAN}{'=' * 100}{NC}\n")


# ============================================================================
# Convenience functions
# ============================================================================

def create_checker(w3: Web3, contract: Any,
                  test_netuids: Optional[List[int]] = None) -> BalanceChecker:
    """
    Convenience function: Create BalanceChecker instance

    Args:
        w3: Web3 instance
        contract: LendingPoolV2 contract instance
        test_netuids: List of netuids (default: [0, 2, 3])
    """
    return BalanceChecker(w3, contract, test_netuids)


if __name__ == "__main__":
    print("This is a library module. Import it in your scripts.")
    print("\nExample usage:")
    print("=" * 80)
    print("""
from balance_checker import BalanceChecker

# Create checker
checker = BalanceChecker(w3, contract, test_netuids=[0, 2, 3])

# Method 1: Get single address balances
balances = checker.get_address_balances("0x123...")
print(json.dumps(balances, indent=2))

# Method 2: Get multiple addresses with labels
addresses = [
    {"address": "0x123...", "label": "lender"},
    {"address": "0x456...", "label": "borrower"}
]
all_balances = checker.get_all_balances(addresses)

# Method 3: Get contract state
contract_state = checker.get_contract_state()

# Method 4: Capture full snapshot
snapshot = checker.capture_snapshot(addresses)
checker.print_snapshot(snapshot)

# Method 5: Compare two snapshots
before = checker.capture_snapshot(addresses)
# ... do something ...
after = checker.capture_snapshot(addresses)
diff = checker.diff_snapshots(before, after)
checker.print_diff(diff)
""")
