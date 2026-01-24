"""
ProcessOS Credential Provider

Manages credential resolution from multiple sources with precedence:
1. Environment variables (highest priority)
2. System keychain (if available)
3. Local file fallback (lowest priority)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class CredentialSource(Enum):
    """Source where a credential was loaded from."""
    ENV = "env"
    KEYCHAIN = "keychain"
    FILE = "file"


@dataclass
class Credential:
    """
    Represents a credential with source tracking.

    Attributes:
        key: Credential identifier (e.g., "ANTHROPIC_API_KEY")
        value: Credential value (sensitive - never log or persist)
        source: Where the credential was loaded from
        loaded_at: When the credential was resolved
    """
    key: str
    value: str
    source: CredentialSource
    loaded_at: datetime

    def __repr__(self) -> str:
        """Safe repr that masks the value."""
        return f"Credential(key='{self.key}', source={self.source.value}, loaded_at={self.loaded_at})"

    def __str__(self) -> str:
        """Safe string representation."""
        return f"{self.key}=*** (from {self.source.value})"


class CredentialProvider:
    """
    Resolves credentials from multiple sources with configurable precedence.

    Default precedence: env > keychain > file
    """

    def __init__(self, sources: Optional[list] = None):
        """
        Initialize the credential provider.

        Args:
            sources: Ordered list of sources to check. Defaults to ["env", "keychain", "file"].
        """
        self.sources = sources or [CredentialSource.ENV, CredentialSource.KEYCHAIN, CredentialSource.FILE]
        if isinstance(self.sources[0], str):
            self.sources = [CredentialSource(s) for s in self.sources]

    def get(self, key: str) -> Optional[Credential]:
        """
        Get a credential by key, checking sources in precedence order.

        Args:
            key: The credential key to look up (e.g., "ANTHROPIC_API_KEY")

        Returns:
            Credential if found, None otherwise
        """
        for source in self.sources:
            value = self._get_from_source(key, source)
            if value is not None:
                return Credential(
                    key=key,
                    value=value,
                    source=source,
                    loaded_at=datetime.now()
                )
        return None

    def _get_from_source(self, key: str, source: CredentialSource) -> Optional[str]:
        """Get a credential from a specific source."""
        if source == CredentialSource.ENV:
            return self._get_from_env(key)
        elif source == CredentialSource.KEYCHAIN:
            return self._get_from_keychain(key)
        elif source == CredentialSource.FILE:
            return self._get_from_file(key)
        return None

    def _get_from_env(self, key: str) -> Optional[str]:
        """Get credential from environment variables."""
        import os
        return os.environ.get(key)

    def _get_from_keychain(self, key: str) -> Optional[str]:
        """Get credential from system keychain."""
        try:
            import keyring
            return keyring.get_password("processos", key)
        except ImportError:
            # keyring not installed
            return None
        except Exception:
            # Keychain access failed
            return None

    def _get_from_file(self, key: str) -> Optional[str]:
        """Get credential from local .env file."""
        try:
            from dotenv import dotenv_values
            values = dotenv_values()
            return values.get(key)
        except ImportError:
            # python-dotenv not installed, try manual parsing
            return self._manual_env_parse(key)

    def _manual_env_parse(self, key: str) -> Optional[str]:
        """Manually parse .env file without python-dotenv."""
        import os
        from pathlib import Path

        env_file = Path.cwd() / ".env"
        if not env_file.exists():
            return None

        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == key:
                            # Remove surrounding quotes if present
                            v = v.strip()
                            if (v.startswith('"') and v.endswith('"')) or \
                               (v.startswith("'") and v.endswith("'")):
                                v = v[1:-1]
                            return v
        except Exception:
            pass
        return None

    def has(self, key: str) -> bool:
        """Check if a credential exists in any source."""
        return self.get(key) is not None

    def require(self, key: str) -> Credential:
        """
        Get a credential, raising an error if not found.

        Args:
            key: The credential key to look up

        Returns:
            Credential

        Raises:
            ValueError: If credential is not found in any source
        """
        credential = self.get(key)
        if credential is None:
            sources_str = ", ".join(s.value for s in self.sources)
            raise ValueError(
                f"Required credential '{key}' not found. "
                f"Checked sources: {sources_str}. "
                f"Set {key} as an environment variable or add it to .env file."
            )
        return credential
