from mythic_container.PayloadBuilder import *
from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *


class ContainerRegistry(PayloadType):
    name = "container_registry"
    file_extension = ""
    author = "@elreydetoda"
    supported_os = [SupportedOS.Linux]
    wrapper = False
    wrapped_payloads = []
    note = """
    This is a service payload that wraps skopeo for OCI container registry operations.
    It provides a Mythic interface to interact with container registries similar to how
    the bloodhound payload interacts with BloodHound CE.

    Skopeo must be installed on the Mythic server for this payload to work.
    """
    supports_dynamic_loading = False
    mythic_encrypts = True
    version = "0.0.1"

    build_parameters = [
        BuildParameter(
            name="registry_url",
            parameter_type=BuildParameterType.String,
            description="Default container registry URL (e.g., docker.io, ghcr.io, quay.io)",
            default_value="docker.io",
        ),
        BuildParameter(
            name="registry_username",
            parameter_type=BuildParameterType.String,
            description="Registry username (optional, can be set per command)",
            default_value="",
            required=False,
        ),
        BuildParameter(
            name="registry_password",
            parameter_type=BuildParameterType.String,
            description="Registry password/token (optional, can be set per command)",
            default_value="",
            required=False,
        ),
        BuildParameter(
            name="insecure",
            parameter_type=BuildParameterType.Boolean,
            description="Allow insecure (HTTP) registry connections",
            default_value=False,
        ),
    ]

    c2_profiles = []

    agent_path = Path(".") / "container_registry"
    agent_icon_path = agent_path / "container_registry.svg"
    agent_code_path = agent_path / "agent_code"

    build_steps = [
        BuildStep(
            step_name="Configuring",
            step_description="Configuring container registry connection"
        ),
    ]

    async def build(self) -> BuildResponse:
        """
        This build function creates a callback in Mythic for interacting with
        container registries via skopeo, similar to how the bloodhound payload works.
        """
        resp = BuildResponse(status=BuildStatus.Success)

        # Create the callback
        create_callback = await SendMythicRPCCallbackCreate(
            MythicRPCCallbackCreateMessage(
                PayloadUUID=self.uuid,
                C2ProfileName="",
                User="ContainerRegistry",
                Host="ContainerRegistry",
                Ip="127.0.0.1",
                IntegrityLevel=3,
                ExtraInfo=f"Registry: {self.get_parameter('registry_url')}",
            )
        )

        if not create_callback.Success:
            resp.status = BuildStatus.Error
            resp.build_stderr = f"Failed to create callback: {create_callback.Error}"
            return resp

        resp.build_message = "Successfully configured container registry service"
        resp.payload = b""

        return resp
