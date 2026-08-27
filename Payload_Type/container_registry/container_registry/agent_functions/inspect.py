from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
from container_registry.agent_functions.shared import (
    credential_secrets,
    get_arg_or_build_value,
    get_registry_proto_url,
    redact_sensitive_text,
    resolve_credentials,
)
import json
import asyncio


class InspectArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="image_name",
                type=ParameterType.String,
                description="Image name with tag to inspect (e.g., alpine:latest from docker://localhost:5000/alpine:latest & library/alpine:latest from docker://docker.io/library/alpine:latest)",
                parameter_group_info=[ParameterGroupInfo(required=True, ui_position=0)],
            ),
            CommandParameter(
                name="USERNAME",
                type=ParameterType.String,
                description="Registry username (optional; supply with PASSWORD, or leave both empty to use the build pair)",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=1)],
                default_value="",
            ),
            CommandParameter(
                name="PASSWORD",
                type=ParameterType.String,
                description="Registry password/token (optional; supply with USERNAME, or leave both empty to use the build pair)",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=2)],
                default_value="",
            ),
            CommandParameter(
                name="INSECURE",
                type=ParameterType.Boolean,
                description="Allow insecure connections",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=3)],
                default_value=False,
            ),
            CommandParameter(
                name="raw",
                type=ParameterType.Boolean,
                description="Return raw manifest instead of formatted output",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=4)],
                default_value=False,
            ),
        ]

    async def parse_arguments(self):
        if len(self.command_line) == 0:
            raise ValueError("Must supply arguments")
        if self.command_line[0] == "{":
            self.load_args_from_json_string(self.command_line)
        else:
            raise ValueError("Require JSON arguments")


class Inspect(CommandBase):
    cmd = "inspect"
    needs_admin = False
    help_cmd = "inspect (Docker Hub example: <username>/testing:<tag>)"
    description = "Inspect an image in the configured registry using authenticated skopeo inspect"
    version = 1
    supported_ui_features = ["container_registry:inspect"]
    author = "@elreydetoda"
    argument_class = InspectArguments
    attackmapping = []

    async def create_go_tasking(self, taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=False,
            Completed=True,
        )

        secrets = credential_secrets(taskData)
        try:
            # Build skopeo command
            cmd = ["skopeo", "inspect"]

            # Add authentication if provided
            credentials = resolve_credentials(taskData)
            if credentials:
                cmd.extend(["--creds", f"{credentials[0]}:{credentials[1]}"])

            # Add insecure flag if needed
            insecure = get_arg_or_build_value(taskData, "INSECURE")
            if insecure:
                cmd.append("--tls-verify=false")

            # Add raw flag if requested
            if taskData.args.get_arg("raw"):
                cmd.append("--raw")

            # Add the image
            image = f"{get_registry_proto_url(taskData=taskData)}/{taskData.args.get_arg('image_name')}"
            cmd.append(image)

            # Execute skopeo command
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            # Process output
            if proc.returncode == 0:
                output = redact_sensitive_text(stdout.decode(errors="replace"), secrets)
                try:
                    # Try to parse as JSON for pretty printing
                    json_output = json.loads(output)
                    formatted_output = json.dumps(json_output, indent=2)
                    await SendMythicRPCResponseCreate(
                        MythicRPCResponseCreateMessage(
                            TaskID=taskData.Task.ID,
                            Response=f"Successfully inspected {image}:\n\n{formatted_output}".encode(),
                        )
                    )
                    response.Success = True
                except json.JSONDecodeError:
                    # If not JSON, return as-is
                    await SendMythicRPCResponseCreate(
                        MythicRPCResponseCreateMessage(
                            TaskID=taskData.Task.ID,
                            Response=f"Successfully inspected {image}:\n\n{output}".encode(),
                        )
                    )
                    response.Success = True
            else:
                error_msg = redact_sensitive_text(stderr.decode(errors="replace"), secrets)
                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=f"Error inspecting {image}:\n{error_msg}".encode(),
                    )
                )

        except Exception as e:
            await SendMythicRPCResponseCreate(
                MythicRPCResponseCreateMessage(
                    TaskID=taskData.Task.ID,
                    Response=f"Exception occurred: {redact_sensitive_text(e, secrets)}".encode(),
                )
            )

        return response
