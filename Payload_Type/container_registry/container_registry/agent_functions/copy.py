from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
from container_registry.agent_functions.shared import get_arg_or_build_value
import asyncio


class CopyArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="source",
                type=ParameterType.String,
                description="Source image (e.g., docker://docker.io/library/alpine:latest)",
                parameter_group_info=[ParameterGroupInfo(required=True)],
            ),
            CommandParameter(
                name="destination",
                type=ParameterType.String,
                description="Destination image (e.g., docker://myregistry.com/alpine:latest)",
                parameter_group_info=[ParameterGroupInfo(required=True)],
            ),
            CommandParameter(
                name="SRC_USERNAME",
                type=ParameterType.String,
                description="Source registry username (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="SRC_PASSWORD",
                type=ParameterType.String,
                description="Source registry password/token (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="DEST_USERNAME",
                type=ParameterType.String,
                description="Destination registry username (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="DEST_PASSWORD",
                type=ParameterType.String,
                description="Destination registry password/token (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="SRC_INSECURE",
                type=ParameterType.Boolean,
                description="Allow insecure source connections",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value=False,
            ),
            CommandParameter(
                name="DEST_INSECURE",
                type=ParameterType.Boolean,
                description="Allow insecure destination connections",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value=False,
            ),
            CommandParameter(
                name="all",
                type=ParameterType.Boolean,
                description="Copy all images if source is a list",
                parameter_group_info=[ParameterGroupInfo(required=False)],
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


class Copy(CommandBase):
    cmd = "copy"
    needs_admin = False
    help_cmd = "copy"
    description = "Copy a container image between registries using skopeo copy"
    version = 1
    supported_ui_features = ["container_registry:copy"]
    author = "@elreydetoda"
    argument_class = CopyArguments
    attackmapping = []

    async def create_go_tasking(self, taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=False,
            Completed=True,
        )

        try:
            # Build skopeo command
            cmd = ["skopeo", "copy"]

            # Add source authentication if provided
            src_username = taskData.args.get_arg("SRC_USERNAME") or get_arg_or_build_value(taskData, "USERNAME")
            src_password = taskData.args.get_arg("SRC_PASSWORD") or get_arg_or_build_value(taskData, "PASSWORD")
            if src_username and src_password:
                cmd.extend(["--src-creds", f"{src_username}:{src_password}"])

            # Add destination authentication if provided
            dest_username = taskData.args.get_arg("DEST_USERNAME") or get_arg_or_build_value(taskData, "USERNAME")
            dest_password = taskData.args.get_arg("DEST_PASSWORD") or get_arg_or_build_value(taskData, "PASSWORD")
            if dest_username and dest_password:
                cmd.extend(["--dest-creds", f"{dest_username}:{dest_password}"])

            # Add insecure flags if needed
            src_insecure = taskData.args.get_arg("SRC_INSECURE") or get_arg_or_build_value(taskData, "INSECURE")
            if src_insecure:
                cmd.append("--src-tls-verify=false")

            dest_insecure = taskData.args.get_arg("DEST_INSECURE") or get_arg_or_build_value(taskData, "INSECURE")
            if dest_insecure:
                cmd.append("--dest-tls-verify=false")

            # Add all flag if requested
            if taskData.args.get_arg("all"):
                cmd.append("--all")

            # Add source and destination
            source = taskData.args.get_arg("source")
            destination = taskData.args.get_arg("destination")
            cmd.extend([source, destination])

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
                result = f"Successfully copied {source} to {destination}"
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
                        Response=f"Error copying {source} to {destination}:\n{error_msg}".encode(),
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
