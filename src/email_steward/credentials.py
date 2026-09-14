"""Credential storage and first-time setup with a strict secret boundary."""

from collections.abc import Callable, Mapping
import platform
from typing import Protocol

from email_steward.profile import OperatorProfile, validate_profile


_SERVICE_NAME = "email-steward"
_OS_SECURE_BACKENDS = {
    "Windows": {("keyring.backends.Windows", "WinVaultKeyring")},
    "Darwin": {("keyring.backends.macOS", "Keyring")},
}
_PROFILE_INPUT_FIELDS = (
    "name",
    "email",
    "preferred_language",
    "reply_language",
    "reply_tone",
)
_PROFILE_PROMPTS = {
    "name": "Your name: ",
    "email": "Your Alibaba Enterprise Mail address: ",
    "preferred_language": "Preferred language: ",
    "reply_language": "Default reply language: ",
    "reply_tone": "Default reply tone: ",
}


class CredentialStoreUnavailableError(RuntimeError):
    """Raised when the operating system credential provider cannot be used."""


class CredentialStoreProtocol(Protocol):
    """The minimal credential-store boundary used by setup and its tests."""

    def get(self, email: str) -> str | None: ...

    def set(self, email: str, secret: str) -> None: ...

    def delete(self, email: str) -> None: ...


class CredentialStore:
    """Store mailbox secrets only through the operating-system keyring."""

    def __init__(self) -> None:
        self._backend, self._keyring_error = _load_verified_system_backend()

    def get(self, email: str) -> str | None:
        """Return the secret for an email, if it exists in the system keyring."""
        self._validate_email(email)
        try:
            return self._backend.get_password(_SERVICE_NAME, email)
        except self._keyring_error as error:
            raise _unavailable_error() from error

    def set(self, email: str, secret: str) -> None:
        """Save a secret in the system keyring, with no filesystem fallback."""
        self._validate_email(email)
        if not isinstance(secret, str) or not secret.strip():
            raise ValueError("credential secret must be non-empty")
        try:
            self._backend.set_password(_SERVICE_NAME, email, secret)
        except self._keyring_error as error:
            raise _unavailable_error() from error

    def delete(self, email: str) -> None:
        """Remove a secret from the system keyring when it exists."""
        self._validate_email(email)
        try:
            self._backend.delete_password(_SERVICE_NAME, email)
        except self._keyring_error as error:
            raise _unavailable_error() from error

    @staticmethod
    def _validate_email(email: str) -> None:
        if not isinstance(email, str) or not email.strip():
            raise ValueError("credential email must be non-empty")


def collect_profile_and_secret(
    input_fn: Callable[[str], str],
    secret_prompt: Callable[[str], str],
    store: CredentialStoreProtocol,
    *,
    profile_prefill: Mapping[str, object] | None = None,
) -> OperatorProfile:
    """Use non-secret prefill when present, then request only missing fields and the secret."""
    values = _collect_profile_values(input_fn, profile_prefill)
    profile = validate_profile(values)
    store.get(profile.email)
    secret = secret_prompt("Alibaba third-party client password: ")
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("Alibaba third-party client password is required")
    store.set(profile.email, secret)
    return profile


def _collect_profile_values(
    input_fn: Callable[[str], str], profile_prefill: Mapping[str, object] | None
) -> dict[str, object]:
    """Keep secret-like fields out of the prefill boundary and prompt only for omissions."""
    if profile_prefill is None:
        supplied: Mapping[str, object] = {}
    elif not isinstance(profile_prefill, Mapping):
        raise ValueError("profile prefill must be a mapping of non-secret fields")
    else:
        unknown_fields = set(profile_prefill) - set(_PROFILE_INPUT_FIELDS)
        if unknown_fields:
            raise ValueError("profile prefill may contain only non-secret profile fields")
        supplied = profile_prefill

    values: dict[str, object] = {}
    for field in _PROFILE_INPUT_FIELDS:
        value = supplied.get(field)
        values[field] = value if isinstance(value, str) and value.strip() else input_fn(_PROFILE_PROMPTS[field])
    return values


def _load_verified_system_backend() -> tuple[object, type[Exception]]:
    try:
        import keyring
        from keyring.errors import KeyringError
    except ImportError as error:
        raise _unavailable_error() from error

    try:
        backend = keyring.get_keyring()
    except KeyringError as error:
        raise _unavailable_error() from error
    _validate_system_backend(backend)
    return backend, KeyringError


def _validate_system_backend(backend: object, *, platform_name: str | None = None) -> None:
    """Allow only the native Windows Credential Manager or macOS Keychain backend."""
    current_platform = platform_name if platform_name is not None else platform.system()
    backend_type = type(backend)
    backend_id = (backend_type.__module__, backend_type.__name__)
    module_name = backend_type.__module__.lower()
    if any(token in module_name for token in ("file", "plaintext", "chainer")):
        raise _unavailable_error(
            "File, plaintext, and chained credential backends are not supported."
        )
    if backend_id not in _OS_SECURE_BACKENDS.get(current_platform, set()):
        raise _unavailable_error(
            "The selected credential backend is not supported on this operating system."
        )


def _unavailable_error(detail: str | None = None) -> CredentialStoreUnavailableError:
    suffix = f" {detail}" if detail else ""
    return CredentialStoreUnavailableError(
        "Credential storage is unavailable. Install or enable the operating-system "
        f"credential provider, then run setup again. No password was saved.{suffix}"
    )
