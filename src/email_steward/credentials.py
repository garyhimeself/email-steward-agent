"""Credential storage and first-time setup with a strict secret boundary."""

from collections.abc import Callable
from typing import Protocol

from email_steward.profile import OperatorProfile, validate_profile


_SERVICE_NAME = "email-steward"


class CredentialStoreUnavailableError(RuntimeError):
    """Raised when the operating system credential provider cannot be used."""


class CredentialStoreProtocol(Protocol):
    """The minimal credential-store boundary used by setup and its tests."""

    def get(self, email: str) -> str | None: ...

    def set(self, email: str, secret: str) -> None: ...

    def delete(self, email: str) -> None: ...


class CredentialStore:
    """Store mailbox secrets only through the operating-system keyring."""

    def __init__(self, *, backend: object | None = None) -> None:
        self._backend = backend if backend is not None else self._load_system_keyring()

    def get(self, email: str) -> str | None:
        """Return the secret for an email, if it exists in the system keyring."""
        self._validate_email(email)
        try:
            return self._backend.get_password(_SERVICE_NAME, email)
        except Exception as error:
            raise _unavailable_error() from error

    def set(self, email: str, secret: str) -> None:
        """Save a secret in the system keyring, with no filesystem fallback."""
        self._validate_email(email)
        if not isinstance(secret, str) or not secret.strip():
            raise ValueError("credential secret must be non-empty")
        try:
            self._backend.set_password(_SERVICE_NAME, email, secret)
        except Exception as error:
            raise _unavailable_error() from error

    def delete(self, email: str) -> None:
        """Remove a secret from the system keyring when it exists."""
        self._validate_email(email)
        try:
            self._backend.delete_password(_SERVICE_NAME, email)
        except Exception as error:
            raise _unavailable_error() from error

    @staticmethod
    def _load_system_keyring() -> object:
        try:
            import keyring
        except ImportError as error:
            raise _unavailable_error() from error
        return keyring

    @staticmethod
    def _validate_email(email: str) -> None:
        if not isinstance(email, str) or not email.strip():
            raise ValueError("credential email must be non-empty")


def collect_profile_and_secret(
    input_fn: Callable[[str], str],
    secret_prompt: Callable[[str], str],
    store: CredentialStoreProtocol,
) -> OperatorProfile:
    """Collect non-secret preferences, then send only the secret to the store."""
    profile = validate_profile(
        {
            "name": input_fn("Your name: "),
            "email": input_fn("Your Alibaba Enterprise Mail address: "),
            "preferred_language": input_fn("Preferred language: "),
            "reply_language": input_fn("Default reply language: "),
            "reply_tone": input_fn("Default reply tone: "),
        }
    )
    secret = secret_prompt("Alibaba third-party client password: ")
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("Alibaba third-party client password is required")
    store.set(profile.email, secret)
    return profile


def _unavailable_error() -> CredentialStoreUnavailableError:
    return CredentialStoreUnavailableError(
        "Credential storage is unavailable. Install or enable the operating-system "
        "credential provider, then run setup again. No password was saved."
    )
