import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "Payload_Type" / "container_registry"
sys.path.insert(0, str(PACKAGE_ROOT))

from container_registry.agent_functions.shared import (  # noqa: E402
    CredentialConfigurationError,
    get_registry_base_url,
    get_registry_proto_url,
    normalize_registry_host,
    redact_sensitive_text,
    resolve_credentials,
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

    def test_complete_build_pair_is_fallback(self):
        task = make_task(
            {"USERNAME": "", "PASSWORD": ""},
            self.BUILD_PAIR,
        )
        self.assertEqual(
            ("build-user", "test-build-password"),
            resolve_credentials(task),
        )

    def test_complete_command_pair_overrides_build_pair(self):
        task = make_task(
            {"USERNAME": " command-user ", "PASSWORD": " test-command-password "},
            self.BUILD_PAIR,
        )
        self.assertEqual(
            ("command-user", "test-command-password"),
            resolve_credentials(task),
        )

    def test_partial_command_pair_never_mixes_with_build_pair(self):
        task = make_task({"USERNAME": "command-user", "PASSWORD": ""}, self.BUILD_PAIR)
        with self.assertRaisesRegex(CredentialConfigurationError, "Command credentials"):
            resolve_credentials(task)

    def test_partial_build_pair_is_rejected(self):
        task = make_task({"USERNAME": "", "PASSWORD": ""}, {"USERNAME": "build-user"})
        with self.assertRaisesRegex(CredentialConfigurationError, "Build credentials"):
            resolve_credentials(task)

    def test_no_credentials_is_allowed(self):
        self.assertIsNone(resolve_credentials(make_task()))


class RedactionTests(unittest.TestCase):
    def test_known_and_structured_secrets_are_redacted(self):
        text = (
            "failure test-password --creds user:test-password "
            "Authorization: Bearer example " + "dckr" + "_pat_not-a-real-token"
        )
        redacted = redact_sensitive_text(text, ("test-password",))
        self.assertNotIn("test-password", redacted)
        self.assertNotIn("not-a-real-token", redacted)
        self.assertIn("<redacted>", redacted)


if __name__ == "__main__":
    unittest.main()
