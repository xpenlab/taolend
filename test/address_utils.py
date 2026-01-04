"""
Address utility functions for converting between EVM (H160) and Substrate (SS58) addresses.
Python equivalent of address-utils.ts using substrate-interface library.
"""

from substrateinterface import Keypair
from substrateinterface.utils.ss58 import ss58_encode, ss58_decode
import hashlib


def convert_h160_to_ss58(eth_address: str, ss58_format: int = 42) -> str:
    """
    Convert Ethereum H160 address to SS58 address.

    Args:
        eth_address: Ethereum address (with or without 0x prefix)
        ss58_format: SS58 address format (default: 42 for generic Substrate)

    Returns:
        SS58 encoded address
    """
    prefix = b"evm:"

    # Remove 0x prefix if present
    if eth_address.startswith("0x") or eth_address.startswith("0X"):
        eth_address = eth_address[2:]

    # Convert hex string to bytes
    address_bytes = bytes.fromhex(eth_address)

    # Concatenate prefix and Ethereum address
    combined = prefix + address_bytes

    # Hash the combined data using blake2b (32 bytes output)
    hash_obj = hashlib.blake2b(combined, digest_size=32)
    public_key = hash_obj.digest()

    # Convert to SS58 format
    ss58_address = ss58_encode(public_key, ss58_format=ss58_format)

    return ss58_address


def ss58_to_public_key(ss58_address: str) -> bytes:
    """
    Decode SS58 address to get the public key bytes.

    Args:
        ss58_address: SS58 encoded address

    Returns:
        Public key as bytes (32 bytes)
    """
    public_key = ss58_decode(ss58_address)
    return bytes.fromhex(public_key)


def public_key_to_hex(public_key: bytes) -> str:
    """
    Convert public key bytes to hex string with 0x prefix.

    Args:
        public_key: Public key as bytes

    Returns:
        Hex string with 0x prefix
    """
    return "0x" + public_key.hex()


def ss58_to_h160(ss58_address: str) -> str:
    """
    Convert SS58 address to Ethereum H160 address.
    Takes the first 20 bytes of the decoded public key.

    Args:
        ss58_address: SS58 encoded address

    Returns:
        Ethereum address with 0x prefix
    """
    public_key = ss58_to_public_key(ss58_address)

    # Take the first 20 bytes for Ethereum address
    ethereum_address_bytes = public_key[:20]

    # Convert to hex string with 0x prefix
    ethereum_address = "0x" + ethereum_address_bytes.hex()

    return ethereum_address


if __name__ == "__main__":
    # Example usage
    eth_address = "0x9C7BC14e8a4B054e98C6DB99B9f1Ea2797BAee7B"

    print(f"EVM Address: {eth_address}")

    ss58_address = convert_h160_to_ss58(eth_address)
    print(f"SS58 Address: {ss58_address}")

    public_key = ss58_to_public_key(ss58_address)
    public_key_hex = public_key_to_hex(public_key)
    print(f"Public Key: {public_key_hex}")

    # Convert back
    recovered_h160 = ss58_to_h160(ss58_address)
    print(f"Recovered H160: {recovered_h160}")
