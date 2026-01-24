"""
ProcessOS Keychain Integration

Provides secure credential storage using the system keychain.
Uses the 'keyring' package which supports Windows Credential Locker,
macOS Keychain, and Linux Secret Service.
"""

from typing import Optional


class KeychainError(Exception):
    """Error accessing the system keychain."""
    pass


class KeychainProvider:
    """
    Provides secure credential storage via system keychain.

    Supports:
    - Windows: Credential Locker
    - macOS: Keychain
    - Linux: Secret Service (libsecret)
    """

    SERVICE_NAME = "processos"

    def __init__(self):
        """Initialize the keychain provider."""
        self._keyring = None
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if keyring is available."""
        try:
            import keyring
            self._keyring = keyring
            # Try a simple operation to verify backend works
            keyring.get_keyring()
            return True
        except ImportError:
            return False
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        """Check if keychain is available on this system."""
        return self._available

    def get(self, key: str) -> Optional[str]:
        """
        Retrieve a credential from the keychain.

        Args:
            key: Credential identifier (e.g., "ANTHROPIC_API_KEY")

        Returns:
            Credential value if found, None otherwise
        """
        if not self._available or self._keyring is None:
            return None

        try:
            return self._keyring.get_password(self.SERVICE_NAME, key)
        except Exception:
            return None

    def set(self, key: str, value: str) -> bool:
        """
        Store a credential in the keychain.

        Args:
            key: Credential identifier
            value: Credential value

        Returns:
            True if successful, False otherwise
        """
        if not self._available or self._keyring is None:
            return False

        try:
            self._keyring.set_password(self.SERVICE_NAME, key, value)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """
        Remove a credential from the keychain.

        Args:
            key: Credential identifier

        Returns:
            True if successful, False otherwise
        """
        if not self._available or self._keyring is None:
            return False

        try:
            self._keyring.delete_password(self.SERVICE_NAME, key)
            return True
        except Exception:
            return False

    def has(self, key: str) -> bool:
        """
        Check if a credential exists in the keychain.

        Args:
            key: Credential identifier

        Returns:
            True if credential exists
        """
        return self.get(key) is not None


# Global keychain provider instance
_keychain: Optional[KeychainProvider] = None


def get_keychain() -> KeychainProvider:
    """Get the global keychain provider instance."""
    global _keychain
    if _keychain is None:
        _keychain = KeychainProvider()
    return _keychain


def keychain_available() -> bool:
    """Check if keychain is available."""
    return get_keychain().is_available
