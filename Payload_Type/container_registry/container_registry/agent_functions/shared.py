import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

from mythic_container.MythicCommandBase import PTTaskMessageAllData


DOCKER_HUB_ALIASES = {
    "docker.io",
    "index.docker.io",
    "registry-1.docker.io",
}

OCI_REG_USERNAME = "OCI_REG_USERNAME"
OCI_REG_PASSWORD = "OCI_REG_PASSWORD"

AUTH_SOURCE_BUILD = "callback build credentials (legacy)"
AUTH_SOURCE_USER_SECRETS = "Mythic user secrets (OCI_REG_USERNAME/OCI_REG_PASSWORD)"
AUTH_SOURCE_FORCED_ANONYMOUS = "anonymous (forced by ANONYMOUS=true)"
AUTH_SOURCE_IMPLICIT_ANONYMOUS = "anonymous (no credentials configured)"


class CredentialConfigurationError(ValueError):
    """Raised when a credential source contains only half of a pair."""


@dataclass(frozen=True)
class ResolvedCredentials:
    """A complete credential pair or an explicit anonymous resolution."""

    username: str | None
    password: str | None
    source: str

    @property
    def pair(self) -> tuple[str, str] | None:
        if self.username is None or self.password is None:
            return None
        return self.username, self.password

    @property
    def provenance(self) -> str:
        return f"Authentication: {self.source}"


def get_build_info(all_data: PTTaskMessageAllData, key_requested: str) -> Any | None:
    """Return an exact build parameter, with suffix fallback for DEST_* keys."""
    for build_param in all_data.BuildParameters:
        if build_param.Name == key_requested:
            return build_param.Value

    for build_param in all_data.BuildParameters:
        if key_requested.endswith(build_param.Name):
            return build_param.Value

    return None


def get_arg_or_build_value(task_data: PTTaskMessageAllData, key_requested: str) -> Any:
    """Return a command value when set, otherwise its matching build value."""
    initial_value = None
    if task_data.args.has_arg(key_requested):
        initial_value = task_data.args.get_arg(key_requested)

    if isinstance(initial_value, bool):
        return initial_value

    if initial_value:
        return initial_value

    return get_build_info(task_data, key_requested)


def normalize_registry_host(value: Any) -> str:
    """Normalize a registry base host without retaining a URL scheme or slash."""
    if value is None:
        raise ValueError("A registry base host is required")

    raw_value = str(value).strip()
    if not raw_value:
        raise ValueError("A registry base host is required")

    parsed = urlparse(raw_value if "://" in raw_value else f"//{raw_value}")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("The registry base host must not contain credentials, a query, or a fragment")

    host = parsed.netloc.rstrip("/")
    path = parsed.path.strip("/")
    if not host:
        raise ValueError("The registry base host is invalid")
    if path:
        raise ValueError("The registry base host must not contain a path")

    host = host.lower()
    if host in DOCKER_HUB_ALIASES:
        return "docker.io"
    return host


def get_registry_base_url(
    provide_url: str | None = None,
    insecure: bool = False,
    taskData: PTTaskMessageAllData | None = None,
) -> str:
    if provide_url is None:
        if taskData is None:
            raise ValueError("Task data is required when no registry host is supplied")
        provide_url = get_arg_or_build_value(taskData, "BASE_HOST")

    scheme = "http" if insecure else "https"
    return f"{scheme}://{normalize_registry_host(provide_url)}"


def get_registry_proto_url(
    provide_url: str | None = None,
    taskData: PTTaskMessageAllData | None = None,
) -> str:
    if provide_url is None:
        if taskData is None:
            raise ValueError("Task data is required when no registry host is supplied")
        provide_url = get_arg_or_build_value(taskData, "BASE_HOST")

    return f"docker://{normalize_registry_host(provide_url)}"


def _normalized_credential(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _build_anonymous(task_data: PTTaskMessageAllData) -> bool:
    value = get_build_info(task_data, "ANONYMOUS")
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_credentials(task_data: PTTaskMessageAllData) -> ResolvedCredentials:
    """Resolve forced anonymous, build, user-secret, or implicit anonymous auth."""
    if _build_anonymous(task_data):
        return ResolvedCredentials(None, None, AUTH_SOURCE_FORCED_ANONYMOUS)

    build_username = _normalized_credential(get_build_info(task_data, "USERNAME"))
    build_password = _normalized_credential(get_build_info(task_data, "PASSWORD"))
    if build_username or build_password:
        if not build_username or not build_password:
            raise CredentialConfigurationError(
                "Build credentials must include both username and password/token"
            )
        return ResolvedCredentials(build_username, build_password, AUTH_SOURCE_BUILD)

    user_secrets = getattr(task_data, "Secrets", None) or {}
    secret_username = _normalized_credential(user_secrets.get(OCI_REG_USERNAME))
    secret_password = _normalized_credential(user_secrets.get(OCI_REG_PASSWORD))
    if secret_username or secret_password:
        if not secret_username or not secret_password:
            raise CredentialConfigurationError(
                "Mythic user secrets must include both OCI_REG_USERNAME and OCI_REG_PASSWORD"
            )
        return ResolvedCredentials(
            secret_username,
            secret_password,
            AUTH_SOURCE_USER_SECRETS,
        )

    return ResolvedCredentials(None, None, AUTH_SOURCE_IMPLICIT_ANONYMOUS)


def credential_secrets(task_data: PTTaskMessageAllData) -> tuple[str, ...]:
    """Collect password values solely for redacting failures and diagnostics."""
    values: list[str] = []
    build_password = _normalized_credential(get_build_info(task_data, "PASSWORD"))
    if build_password:
        values.append(build_password)

    user_secrets = getattr(task_data, "Secrets", None) or {}
    secret_password = _normalized_credential(user_secrets.get(OCI_REG_PASSWORD))
    if secret_password and secret_password not in values:
        values.append(secret_password)
    return tuple(values)


def with_authentication_provenance(
    message: Any,
    credentials: ResolvedCredentials,
) -> str:
    """Prefix a task result with the safe authentication-source label."""
    return f"{credentials.provenance}\n{message}"


def redact_sensitive_text(text: Any, secrets: Iterable[str] = ()) -> str:
    """Remove known secrets and common credential forms from external text."""
    redacted = str(text)
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")

    docker_pat_pattern = r"dckr" + r"_pat_[A-Za-z0-9_-]+"
    redacted = re.sub(docker_pat_pattern, "<redacted>", redacted)
    redacted = re.sub(
        r"(?i)(--(?:dest-)?creds(?:=|\s+))\S+",
        r"\1<redacted>",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(authorization\s*:\s*)[^\r\n]+",
        r"\1<redacted>",
        redacted,
    )
    return redacted
