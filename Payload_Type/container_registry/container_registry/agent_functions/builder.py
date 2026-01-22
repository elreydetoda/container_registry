from mythic_container.PayloadBuilder import *
from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *


class ContainerRegistry(PayloadType):
    name = "container_registry"
    file_extension = ""
    author = "@elreydetoda"
    supported_os = [SupportedOS("container_registry")]
    wrapper = False
    wrapped_payloads = []
    note = """
    This is a 3rd party service payload that wraps skopeo
    (https://github.com/containers/skopeo) for OCI container registry operations.
    """
    supports_dynamic_loading = False
    mythic_encrypts = True
    agent_type = AgentType.Service
    version = "0.0.1"

    build_parameters = [
        BuildParameter(
            name="BASE_HOST",
            parameter_type=BuildParameterType.String,
            description="Default container registry URL (e.g., docker.io, ghcr.io, quay.io)",
            default_value="localhost:5000",
        ),
        BuildParameter(
            name="USERNAME",
            parameter_type=BuildParameterType.String,
            description="Registry username (optional, can be set per command)",
            default_value="",
            required=False,
        ),
        BuildParameter(
            name="PASSWORD",
            parameter_type=BuildParameterType.String,
            description="Registry password/token (optional, can be set per command)",
            default_value="",
            required=False,
        ),
        BuildParameter(
            name="INSECURE",
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
                ExtraInfo=f"Registry: {self.get_parameter('BASE_HOST')}",
            )
        )

        if not create_callback.Success:
            resp.status = BuildStatus.Error
            resp.build_stderr = f"Failed to create callback: {create_callback.Error}"
            return resp

        resp.build_message = "Successfully configured container registry service"
        resp.payload = b""

        return resp
