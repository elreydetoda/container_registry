from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
from container_registry.agent_functions.shared import (
    credential_secrets,
    get_arg_or_build_value,
    get_registry_proto_url,
    redact_sensitive_text,
    resolve_credentials,
)
import asyncio


class DeleteArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="image_name",
                type=ParameterType.String,
                description="Image name with tag to delete (e.g., myrepo/myimage:tag from docker://localhost:5000/myrepo/myimage:tag)",
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
        ]

    async def parse_arguments(self):
        if len(self.command_line) == 0:
            raise ValueError("Must supply arguments")
        if self.command_line[0] == "{":
            self.load_args_from_json_string(self.command_line)
        else:
            raise ValueError("Require JSON arguments")


class Delete(CommandBase):
    cmd = "delete"
    needs_admin = False
    help_cmd = "delete <repository/image:tag>"
    description = "Delete an image from the configured registry using authenticated skopeo delete"
    version = 1
    supported_ui_features = ["container_registry:delete"]
    author = "@elreydetoda"
    argument_class = DeleteArguments
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
            cmd = ["skopeo", "delete"]

            # Add authentication if provided
            credentials = resolve_credentials(taskData)
            if credentials:
                cmd.extend(["--creds", f"{credentials[0]}:{credentials[1]}"])

            # Add insecure flag if needed
            insecure = get_arg_or_build_value(taskData, "INSECURE")
            if insecure:
                cmd.append("--tls-verify=false")

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
                error_output = redact_sensitive_text(stderr.decode(errors="replace"), secrets)
                result = f"Successfully deleted {image}"
                if output:
                    result += f"\n\nOutput:\n{output}"
                if error_output:
                    result += f"\n\nInfo:\n{error_output}"

                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=result.encode(),
                    )
                )
                response.Success = True
            else:
                error_msg = redact_sensitive_text(stderr.decode(errors="replace"), secrets)
                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=f"Error deleting {image}:\n{error_msg}".encode(),
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
