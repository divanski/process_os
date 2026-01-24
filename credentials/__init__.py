"""
ProcessOS Credentials Module

Secure credential management with multiple storage backends.
Supports environment variables, system keychain, and local files.
"""

from .keychain import (
    KeychainError,
    KeychainProvider,
    get_keychain,
    keychain_available,
)
from .provider import (
    Credential,
    CredentialProvider,
    CredentialSource,
)

__all__ = [
    # Provider
    "Credential",
    "CredentialProvider",
    "CredentialSource",
    # Keychain
    "KeychainProvider",
    "KeychainError",
    "get_keychain",
    "keychain_available",
]
