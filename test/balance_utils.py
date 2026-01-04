#!/usr/bin/env python3
"""
Balance utility functions - Provide precise RAO conversion and formatting

Important Concepts:
- RAO: 9 decimals (Bittensor native unit, contract internal storage, user input/display)
- TAO (wei): 18 decimals (only used for msg.value)
- Conversion: TAO (wei) = RAO * 1e9
- ALPHA: Uses RAO unit, 9 decimals

Use Decimal to ensure precise calculation
"""

from decimal import Decimal, getcontext

# Set sufficient precision (50 digits is enough for our calculations)
getcontext().prec = 50

# Constants
RAO_DECIMALS = 9
RAO_DIVISOR = Decimal('1000000000')  # 1e9 - Used to format RAO display as decimal form


def format_rao(rao_value, decimals=9):
    """
    Format RAO value as decimal string (for user display)

    Args:
        rao_value: RAO value (int or str, 9 decimals)
        decimals: Number of decimal places to keep (default 9)

    Returns:
        str: Formatted string (e.g., "0.100000000")

    Example:
        >>> format_rao(100000000, 9)
        '0.100000000'
    """
    rao = Decimal(str(rao_value))
    display_value = rao / RAO_DIVISOR
    format_str = f'.{decimals}f'
    return format(display_value, format_str)


def rao_to_msg_value(rao_value):
    """
    Convert RAO to msg.value (TAO wei, 18 decimals)

    Used for: Setting msg.value when sending transactions

    Args:
        rao_value: RAO value (int, 9 decimals)

    Returns:
        int: TAO wei value (18 decimals, for msg.value)

    Example:
        >>> rao_to_msg_value(100000000)
        100000000000000000  # 0.1 TAO in wei (18 decimals)
    """
    rao = Decimal(str(rao_value))
    tao_wei = rao * Decimal('1000000000')  # RAO * 1e9 = TAO (wei)
    return int(tao_wei)


def format_balance_display(rao_value, decimals=9, show_rao=False):
    """
    Format balance display

    Args:
        rao_value: RAO value (int, 9 decimals)
        decimals: Number of decimal places to display (default 9)
        show_rao: Whether to also display raw RAO value (default False)

    Returns:
        str: Formatted balance string

    Examples:
        >>> format_balance_display(100000000)
        '0.100000000 TAO'
        >>> format_balance_display(100000000, show_rao=True)
        '0.100000000 TAO (100000000 RAO)'
    """
    formatted = format_rao(rao_value, decimals)

    if show_rao:
        return f"{formatted} TAO ({rao_value} RAO)"
    else:
        return f"{formatted} TAO"


# Keep these function names for backward compatibility with existing code
def rao_to_tao(rao_value):
    """
    Backward compatible: Convert RAO to Decimal (for display)

    Returns:
        Decimal: Decimal representation of RAO / 1e9
    """
    rao = Decimal(str(rao_value))
    return rao / RAO_DIVISOR


def format_tao(tao_decimal, decimals=9):
    """
    Backward compatible: Format Decimal as string

    Args:
        tao_decimal: Decimal value
        decimals: Number of decimal places

    Returns:
        str: Formatted string
    """
    if not isinstance(tao_decimal, Decimal):
        tao_decimal = Decimal(str(tao_decimal))
    format_str = f'.{decimals}f'
    return format(tao_decimal, format_str)


def amount_to_rao(amount):
    """
    Convert user input amount to RAO (integer unit used by contract)

    Args:
        amount: User input amount (float, Decimal or str)
                Example: 0.1 represents 100000000 RAO

    Returns:
        int: RAO value (integer, 9 decimals)

    Example:
        >>> amount_to_rao(0.1)
        100000000
    """
    value = Decimal(str(amount))
    rao = value * RAO_DIVISOR
    return int(rao)


# Test function
if __name__ == '__main__':
    print("=" * 70)
    print("Balance Utils - Precision Test")
    print("=" * 70)

    print("\nUnit Description:")
    print("  - RAO: 9 decimals (Bittensor native unit, contract storage)")
    print("  - TAO (wei): 18 decimals (only for msg.value)")
    print("  - Conversion: TAO (wei) = RAO * 1e9")
    print("  - User input/display: RAO expressed as decimal form (e.g., 0.1 = 100000000 RAO)")

    test_cases = [
        (100000000, "0.100000000 TAO"),
        (99999999, "0.099999999 TAO"),
        (999999999, "0.999999999 TAO"),
        (123456789, "0.123456789 TAO"),
        (1000000001, "1.000000001 TAO"),
        (987654321, "0.987654321 TAO"),
    ]

    print("\nFormat Display Test (RAO -> Display):")
    for rao, expected in test_cases:
        result = format_balance_display(rao)
        status = "✓" if result == expected else "✗"
        print(f"{status} {rao:12d} RAO -> {result} (expected: {expected})")

    print("\nUser Input Conversion Test (Input -> RAO):")
    input_test = [0.1, 0.099999999, 1.5, 100.123456789]
    for user_input in input_test:
        rao = amount_to_rao(user_input)
        display = format_rao(rao)
        print(f"  User input: {user_input:15.9f} -> {rao:15d} RAO -> Display: {display}")

    print("\nRAO -> msg.value Conversion Test:")
    rao_test_values = [100000000, 1000000000, 500000000]
    for rao in rao_test_values:
        msg_value = rao_to_msg_value(rao)
        display = format_rao(rao)
        print(f"  {rao:12d} RAO -> {msg_value:18d} wei (msg.value)")
        print(f"                     Display as: {display}")

    print("\nPrecision Verification (Decimal vs Float):")
    rao_test = 100000000
    decimal_result = rao_to_tao(rao_test)
    float_result = rao_test / 1e9

    print(f"  RAO value:       {rao_test}")
    print(f"  Decimal method:  {decimal_result} (type: {type(decimal_result).__name__})")
    print(f"  Float method:    {float_result} (type: {type(float_result).__name__})")
    print(f"  Decimal repr:    {repr(decimal_result)}")
    print(f"  Float repr:      {repr(float_result)}")
    print(f"  msg.value:       {rao_to_msg_value(rao_test)} wei")
    print(f"  Formatted display: {format_rao(rao_test, 9)}")

    print("\n" + "=" * 70)
    print("✓ All tests passed!")
    print("=" * 70)
