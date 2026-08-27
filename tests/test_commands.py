import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "Payload_Type" / "container_registry"
sys.path.insert(0, str(PACKAGE_ROOT))

from container_registry.agent_functions import copy as copy_module  # noqa: E402
from container_registry.agent_functions import delete as delete_module  # noqa: E402
from container_registry.agent_functions import inspect as inspect_module  # noqa: E402
from container_registry.agent_functions import list_catalog as catalog_module  # noqa: E402
from container_registry.agent_functions import list_tags as tags_module  # noqa: E402
from tests.helpers import FakeProcess, make_task  # noqa: E402


BUILD_PAIR = {"BASE_HOST": " registry-1.docker.io/ ", "USERNAME": "build-user", "PASSWORD": "test-password", "INSECURE": False}


def response_text(response_mock):
    message = response_mock.await_args.args[0]
    return message.Response.decode()


def command_instance(command_class):
    return command_class(PROJECT_ROOT, PACKAGE_ROOT, PROJECT_ROOT)


class SkopeoCommandTests(unittest.IsolatedAsyncioTestCase):
    async def _run_skopeo_command(self, module, command_class, arguments, process):
        task = make_task(arguments, BUILD_PAIR)
        response_mock = AsyncMock()
        process_mock = AsyncMock(return_value=process)
        with patch.object(module, "SendMythicRPCResponseCreate", response_mock), patch.object(
            module.asyncio, "create_subprocess_exec", process_mock
        ):
            result = await command_instance(command_class).create_go_tasking(task)
        return result, process_mock.await_args.args, response_mock

    async def test_inspect_uses_creds_and_canonical_docker_hub_host(self):
        result, argv, _ = await self._run_skopeo_command(
            inspect_module,
            inspect_module.Inspect,
            {"image_name": "username/testing:qa", "USERNAME": "", "PASSWORD": "", "INSECURE": False, "raw": False},
            FakeProcess(stdout=b"{}"),
        )
        self.assertTrue(result.Success)
        self.assertEqual("--creds", argv[2])
        self.assertEqual("build-user:test-password", argv[3])
        self.assertNotIn("--tls-verify=false", argv)
        self.assertEqual("docker://docker.io/username/testing:qa", argv[-1])

    async def test_delete_and_list_tags_use_creds_and_tls_flag(self):
        cases = (
            (delete_module, delete_module.Delete, {"image_name": "repo:tag", "USERNAME": "", "PASSWORD": "", "INSECURE": True}, b""),
            (tags_module, tags_module.ListTags, {"image_name": "repo", "USERNAME": "", "PASSWORD": "", "INSECURE": True}, b'{"Repository":"repo","Tags":[]}'),
        )
        for module, command_class, arguments, output in cases:
            with self.subTest(command=command_class.cmd):
                result, argv, _ = await self._run_skopeo_command(
                    module, command_class, arguments, FakeProcess(stdout=output)
                )
                self.assertTrue(result.Success)
                self.assertIn("--creds", argv)
                self.assertIn("--tls-verify=false", argv)
                self.assertNotIn("--dest-creds", argv)

    async def test_copy_uses_dest_creds_and_dest_tls_flag(self):
        task = make_task(
            {
                "source": "container_wrapper.tar - QA wrapper",
                "destination_name": "temporary/repo:qa",
                "DEST_USERNAME": "",
                "DEST_PASSWORD": "",
                "DEST_INSECURE": True,
            },
            {**BUILD_PAIR, "BASE_HOST": "10.9.20.11:32000"},
        )
        payload = SimpleNamespace(
            UUID="payload-uuid",
            AgentFileId="file-uuid",
            Filename="container_wrapper.tar",
        )
        response_mock = AsyncMock()
        process_mock = AsyncMock(return_value=FakeProcess())
        content_mock = AsyncMock(return_value=SimpleNamespace(Success=True, Content=b"archive"))
        with patch.object(
            copy_module,
            "SendMythicRPCPayloadSearch",
            AsyncMock(return_value=SimpleNamespace(Success=True, Payloads=[payload])),
        ), patch.object(
            copy_module,
            "SendMythicRPCFileGetContent",
            content_mock,
        ), patch.object(
            copy_module, "SendMythicRPCResponseCreate", response_mock
        ), patch.object(copy_module.asyncio, "create_subprocess_exec", process_mock):
            result = await command_instance(copy_module.Copy).create_go_tasking(task)

        argv = process_mock.await_args.args
        self.assertTrue(result.Success)
        self.assertIn("--dest-creds", argv)
        self.assertNotIn("--creds", argv)
        self.assertIn("--dest-tls-verify=false", argv)
        self.assertEqual("docker://10.9.20.11:32000/temporary/repo:qa", argv[-1])
        self.assertEqual("file-uuid", content_mock.await_args.args[0].AgentFileID)

    async def test_subprocess_secret_is_absent_from_error_response(self):
        result, _, response_mock = await self._run_skopeo_command(
            inspect_module,
            inspect_module.Inspect,
            {"image_name": "repo:tag", "USERNAME": "", "PASSWORD": "", "INSECURE": False, "raw": False},
            FakeProcess(returncode=1, stderr=b"login failed --creds build-user:test-password"),
        )
        self.assertFalse(result.Success)
        output = response_text(response_mock)
        self.assertNotIn("test-password", output)
        self.assertIn("<redacted>", output)


class CatalogCommandTests(unittest.IsolatedAsyncioTestCase):
    async def _run_catalog(self, insecure, registry_response):
        task = make_task(
            {"BASE_HOST": "", "USERNAME": "", "PASSWORD": "", "INSECURE": insecure},
            {**BUILD_PAIR, "BASE_HOST": "index.docker.io"},
        )
        response_mock = AsyncMock()
        with patch.object(catalog_module.requests, "get", return_value=registry_response) as get_mock, patch.object(
            catalog_module, "SendMythicRPCResponseCreate", response_mock
        ):
            result = await command_instance(catalog_module.ListCatalog).create_go_tasking(task)
        return result, get_mock, response_mock

    async def test_catalog_https_and_auth_arguments(self):
        registry_response = SimpleNamespace(
            status_code=200,
            reason="OK",
            text='{"repositories":[]}',
            json=lambda: {"repositories": []},
        )
        result, get_mock, _ = await self._run_catalog(False, registry_response)
        self.assertTrue(result.Success)
        get_mock.assert_called_once_with(
            "https://docker.io/v2/_catalog",
            auth=("build-user", "test-password"),
            verify=True,
            timeout=30,
        )

    async def test_catalog_insecure_uses_http_and_disables_verification(self):
        registry_response = SimpleNamespace(
            status_code=200,
            reason="OK",
            text='{"repositories":["testing_image"]}',
            json=lambda: {"repositories": ["testing_image"]},
        )
        result, get_mock, _ = await self._run_catalog(True, registry_response)
        self.assertTrue(result.Success)
        self.assertEqual("http://docker.io/v2/_catalog", get_mock.call_args.args[0])
        self.assertFalse(get_mock.call_args.kwargs["verify"])

    async def test_catalog_error_redacts_password(self):
        registry_response = SimpleNamespace(
            status_code=401,
            reason="Unauthorized",
            text="credential test-password rejected",
        )
        result, _, response_mock = await self._run_catalog(False, registry_response)
        self.assertFalse(result.Success)
        output = response_text(response_mock)
        self.assertNotIn("test-password", output)
        self.assertIn("<redacted>", output)


class SourceLoggingTests(unittest.TestCase):
    def test_active_commands_do_not_log_arguments_or_credentials(self):
        source_dir = PACKAGE_ROOT / "container_registry" / "agent_functions"
        source = "\n".join(path.read_text(encoding="utf-8") for path in source_dir.glob("*.py"))
        self.assertNotIn("logger.debug", source)
        self.assertNotIn("args.to_json", source)
        self.assertNotIn("BuildParameters]", source)
        self.assertNotIn("logger.info", source)


if __name__ == "__main__":
    unittest.main()
