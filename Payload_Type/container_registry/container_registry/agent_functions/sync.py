from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
from container_registry.agent_functions.shared import get_arg_or_build_value, get_registry_proto_url
import asyncio


class SyncArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="source_image_name",
                type=ParameterType.String,
                description="Source image name with tag (e.g., myimage:latest from the configured registry)",
                parameter_group_info=[ParameterGroupInfo(required=True, ui_position=0)],
            ),
            CommandParameter(
                name="destination",
                type=ParameterType.String,
                description="Destination transport (e.g., dir:/path/to/dir)",
                parameter_group_info=[ParameterGroupInfo(required=True, ui_position=1)],
            ),
            CommandParameter(
                name="SRC_USERNAME",
                type=ParameterType.String,
                description="Source registry username (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=2)],
                default_value="",
            ),
            CommandParameter(
                name="SRC_PASSWORD",
                type=ParameterType.String,
                description="Source registry password/token (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=3)],
                default_value="",
            ),
            CommandParameter(
                name="DEST_USERNAME",
                type=ParameterType.String,
                description="Destination registry username (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=4)],
                default_value="",
            ),
            CommandParameter(
                name="DEST_PASSWORD",
                type=ParameterType.String,
                description="Destination registry password/token (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=5)],
                default_value="",
            ),
            CommandParameter(
                name="SRC_INSECURE",
                type=ParameterType.Boolean,
                description="Allow insecure source connections",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=6)],
                default_value=False,
            ),
            CommandParameter(
                name="DEST_INSECURE",
                type=ParameterType.Boolean,
                description="Allow insecure destination connections",
                parameter_group_info=[ParameterGroupInfo(required=False, ui_position=7)],
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


class Sync(CommandBase):
    cmd = "sync"
    needs_admin = False
    help_cmd = "sync"
    description = "Synchronize images between registries or to local storage using skopeo sync"
    version = 1
    supported_ui_features = ["container_registry:sync"]
    author = "@elreydetoda"
    argument_class = SyncArguments
    attackmapping = []

    async def create_go_tasking(self, taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=False,
            Completed=True,
        )

        try:
            # Build skopeo command
            cmd = ["skopeo", "sync"]

            # Add source authentication if provided
            src_username = get_arg_or_build_value(taskData, "SRC_USERNAME")
            src_password = get_arg_or_build_value(taskData, "SRC_PASSWORD")
            if src_username and src_password:
                cmd.extend(["--src-creds", f"{src_username}:{src_password}"])

            # Add destination authentication if provided
            dest_username = get_arg_or_build_value(taskData, "DEST_USERNAME")
            dest_password = get_arg_or_build_value(taskData, "DEST_PASSWORD")
            if dest_username and dest_password:
                cmd.extend(["--dest-creds", f"{dest_username}:{dest_password}"])

            # Add insecure flags if needed
            src_insecure = get_arg_or_build_value(taskData, "SRC_INSECURE")
            if src_insecure:
                cmd.append("--src-tls-verify=false")

            dest_insecure = get_arg_or_build_value(taskData, "DEST_INSECURE")
            if dest_insecure:
                cmd.append("--dest-tls-verify=false")

            # Add source and destination
            source = f"{get_registry_proto_url(taskData=taskData)}/{taskData.args.get_arg('source_image_name')}"
            destination = taskData.args.get_arg("destination")
            cmd.extend(["--src", "docker", "--dest", "dir", source, destination])

            # Execute skopeo command
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            # Process output
            if proc.returncode == 0:
                output = stdout.decode()
                error_output = stderr.decode()
                result = f"Successfully synced {source} to {destination}"
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
                error_msg = stderr.decode()
                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=f"Error syncing {source} to {destination}:\n{error_msg}".encode(),
                    )
                )

        except Exception as e:
            await SendMythicRPCResponseCreate(
                MythicRPCResponseCreateMessage(
                    TaskID=taskData.Task.ID,
                    Response=f"Exception occurred: {str(e)}".encode(),
                )
            )

        return response
