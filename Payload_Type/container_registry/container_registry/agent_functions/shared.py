import re
from typing import Any, Iterable
from urllib.parse import urlparse

from mythic_container.MythicCommandBase import PTTaskMessageAllData


DOCKER_HUB_ALIASES = {
    "docker.io",
    "index.docker.io",
    "registry-1.docker.io",
}


class CredentialConfigurationError(ValueError):
    """Raised when a credential source contains only half of a pair."""


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


def resolve_credentials(
    task_data: PTTaskMessageAllData,
    command_username_key: str = "USERNAME",
    command_password_key: str = "PASSWORD",
) -> tuple[str, str] | None:
    """Resolve one complete command or build credential pair without mixing."""
    command_username = None
    command_password = None
    if task_data.args.has_arg(command_username_key):
        command_username = _normalized_credential(task_data.args.get_arg(command_username_key))
    if task_data.args.has_arg(command_password_key):
        command_password = _normalized_credential(task_data.args.get_arg(command_password_key))

    if command_username or command_password:
        if not command_username or not command_password:
            raise CredentialConfigurationError(
                "Command credentials must include both username and password/token"
            )
        return command_username, command_password

    build_username = _normalized_credential(get_build_info(task_data, "USERNAME"))
    build_password = _normalized_credential(get_build_info(task_data, "PASSWORD"))
    if build_username or build_password:
        if not build_username or not build_password:
            raise CredentialConfigurationError(
                "Build credentials must include both username and password/token"
            )
        return build_username, build_password

    return None


def credential_secrets(
    task_data: PTTaskMessageAllData,
    command_password_key: str = "PASSWORD",
) -> tuple[str, ...]:
    """Collect password values solely for redacting failures and diagnostics."""
    values: list[str] = []
    if task_data.args.has_arg(command_password_key):
        command_password = _normalized_credential(task_data.args.get_arg(command_password_key))
        if command_password:
            values.append(command_password)

    build_password = _normalized_credential(get_build_info(task_data, "PASSWORD"))
    if build_password and build_password not in values:
        values.append(build_password)
    return tuple(values)


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
