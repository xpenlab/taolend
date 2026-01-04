"""
Constants for TaoLend project - Python version

This module contains all contract addresses and constants used in the TaoLend project.
"""

# Bittensor Precompiled Contract Addresses
IMETAGRAPH_ADDRESS: str = "0x0000000000000000000000000000000000000802"
INEURON_ADDRESS: str = "0x0000000000000000000000000000000000000804"
ISUBTENSOR_BALANCE_TRANSFER_ADDRESS: str = "0x0000000000000000000000000000000000000800"
ISTAKING_V2_ADDRESS: str = "0x0000000000000000000000000000000000000805"
IALPHA_ADDRESS: str = "0x0000000000000000000000000000000000000808"
ISUBNET_ADDRESS: str = "0x0000000000000000000000000000000000000803"
IUID_LOOKUP_ADDRESS: str = "0x0000000000000000000000000000000000000806"

# Default Hotkey (SS58 format)
DEFAULT_HOTKEY: str = "5GRbhLuSANdXx5MFNF7FGHNyxoHSQbmtM6vgmASnvGoUTnhM"
ANOTHER_HOTKEY: str = "5E7618Kn65YXAkWPh3NyNyEAmSxNBxjpJpn2KEfSr6qfwuPh"

# LendingPoolV2 Contract Address
LENDING_POOL_V2_ADDRESS: str = "0x33C9c122eb602c47d6c1f1f4096550ff5d3DeDDC"


# Export all constants
__all__ = [
    "IMETAGRAPH_ADDRESS",
    "INEURON_ADDRESS",
    "ISUBTENSOR_BALANCE_TRANSFER_ADDRESS",
    "ISTAKING_V2_ADDRESS",
    "IALPHA_ADDRESS",
    "ISUBNET_ADDRESS",
    "IUID_LOOKUP_ADDRESS",
    "DEFAULT_HOTKEY",
    "LENDING_POOL_V2_ADDRESS",
]


if __name__ == "__main__":
    """Print all constants when run as a script"""
    print("=== TaoLend Constants ===")
    print(f"\nPrecompiled Contract Addresses:")
    print(f"  IMetagraph:                {IMETAGRAPH_ADDRESS}")
    print(f"  INeuron:                   {INEURON_ADDRESS}")
    print(f"  ISubtensorBalanceTransfer: {ISUBTENSOR_BALANCE_TRANSFER_ADDRESS}")
    print(f"  IStakingV2:                {ISTAKING_V2_ADDRESS}")
    print(f"  IAlpha:                    {IALPHA_ADDRESS}")
    print(f"  ISubnet:                   {ISUBNET_ADDRESS}")
    print(f"  IUidLookup:                {IUID_LOOKUP_ADDRESS}")
    print(f"\nDefault Configuration:")
    print(f"  Default Hotkey:            {DEFAULT_HOTKEY}")
    print(f"\nDeployed Contracts:")
    print(f"  LendingPoolV2:             {LENDING_POOL_V2_ADDRESS}")
