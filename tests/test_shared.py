import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "Payload_Type" / "container_registry"
sys.path.insert(0, str(PACKAGE_ROOT))

from container_registry.agent_functions.shared import (  # noqa: E402
    AUTH_SOURCE_BUILD,
    AUTH_SOURCE_FORCED_ANONYMOUS,
    AUTH_SOURCE_IMPLICIT_ANONYMOUS,
    AUTH_SOURCE_USER_SECRETS,
    CredentialConfigurationError,
    OCI_REG_PASSWORD,
    OCI_REG_USERNAME,
    credential_secrets,
    get_registry_base_url,
    get_registry_proto_url,
    normalize_registry_host,
    redact_sensitive_text,
    resolve_credentials,
    with_authentication_provenance,
)
from tests.helpers import make_task  # noqa: E402


class RegistryHostTests(unittest.TestCase):
    def test_docker_hub_aliases_are_canonicalized(self):
        cases = (
            "docker.io",
            " index.docker.io/ ",
            "https://registry-1.docker.io///",
            "docker://DOCKER.IO/",
        )
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual("docker.io", normalize_registry_host(value))

    def test_generic_host_and_port_are_preserved(self):
        self.assertEqual(
            "10.9.20.11:32000",
            normalize_registry_host(" http://10.9.20.11:32000/ "),
        )

    def test_url_helpers_control_the_scheme(self):
        self.assertEqual(
            "https://docker.io",
            get_registry_base_url("http://index.docker.io/", insecure=False),
        )
        self.assertEqual(
            "http://10.9.20.11:32000",
            get_registry_base_url("https://10.9.20.11:32000/", insecure=True),
        )
        self.assertEqual(
            "docker://docker.io",
            get_registry_proto_url("registry-1.docker.io/"),
        )

    def test_paths_and_embedded_credentials_are_rejected(self):
        for value in ("docker.io/a/path", "user:password@docker.io"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_registry_host(value)


class CredentialResolutionTests(unittest.TestCase):
    BUILD_PAIR = {"USERNAME": "build-user", "PASSWORD": "test-build-password"}
    USER_SECRET_PAIR = {
        OCI_REG_USERNAME: "secret-user",
        OCI_REG_PASSWORD: "test-user-secret-password",
    }

    def test_complete_build_pair_is_authoritative(self):
        resolved = resolve_credentials(
            make_task(
                {"USERNAME": "ignored-task-user", "PASSWORD": "ignored-task-password"},
                self.BUILD_PAIR,
                self.USER_SECRET_PAIR,
            )
        )
        self.assertEqual(("build-user", "test-build-password"), resolved.pair)
        self.assertEqual(AUTH_SOURCE_BUILD, resolved.source)

    def test_user_secrets_are_used_only_without_build_credentials(self):
        resolved = resolve_credentials(
            make_task(
                {"USERNAME": "ignored-task-user", "PASSWORD": "ignored-task-password"},
                {"USERNAME": "", "PASSWORD": "", "ANONYMOUS": False},
                self.USER_SECRET_PAIR,
            )
        )
        self.assertEqual(("secret-user", "test-user-secret-password"), resolved.pair)
        self.assertEqual(AUTH_SOURCE_USER_SECRETS, resolved.source)

    def test_partial_build_pair_rejects_user_secret_fallback(self):
        task = make_task(
            build_parameters={"USERNAME": "build-user"},
            secrets=self.USER_SECRET_PAIR,
        )
        with self.assertRaisesRegex(CredentialConfigurationError, "Build credentials"):
            resolve_credentials(task)

    def test_partial_user_secret_pair_is_rejected(self):
        task = make_task(secrets={OCI_REG_USERNAME: "secret-user"})
        with self.assertRaisesRegex(CredentialConfigurationError, "Mythic user secrets"):
            resolve_credentials(task)

    def test_forced_anonymous_ignores_both_sources(self):
        resolved = resolve_credentials(
            make_task(
                build_parameters={**self.BUILD_PAIR, "ANONYMOUS": True},
                secrets=self.USER_SECRET_PAIR,
            )
        )
        self.assertIsNone(resolved.pair)
        self.assertEqual(AUTH_SOURCE_FORCED_ANONYMOUS, resolved.source)

    def test_missing_credentials_is_implicit_anonymous(self):
        resolved = resolve_credentials(make_task())
        self.assertIsNone(resolved.pair)
        self.assertEqual(AUTH_SOURCE_IMPLICIT_ANONYMOUS, resolved.source)

    def test_task_credentials_are_ignored(self):
        resolved = resolve_credentials(
            make_task({"USERNAME": "task-user", "PASSWORD": "task-password"})
        )
        self.assertIsNone(resolved.pair)
        self.assertEqual(AUTH_SOURCE_IMPLICIT_ANONYMOUS, resolved.source)

    def test_provenance_and_redaction_candidates_are_safe(self):
        task = make_task(
            build_parameters=self.BUILD_PAIR,
            secrets=self.USER_SECRET_PAIR,
        )
        resolved = resolve_credentials(task)
        self.assertEqual(
            "Authentication: callback build credentials (legacy)\nresult",
            with_authentication_provenance("result", resolved),
        )
        self.assertEqual(
            ("test-build-password", "test-user-secret-password"),
            credential_secrets(task),
        )


class RedactionTests(unittest.TestCase):
    def test_known_and_structured_secrets_are_redacted(self):
        text = (
            "failure test-password --creds user:test-password "
            "Author" + "ization: Bearer example " + "dckr" + "_pat_not-a-real-token"
        )
        redacted = redact_sensitive_text(text, ("test-password",))
        self.assertNotIn("test-password", redacted)
        self.assertNotIn("not-a-real-token", redacted)
        self.assertIn("<redacted>", redacted)


if __name__ == "__main__":
    unittest.main()
