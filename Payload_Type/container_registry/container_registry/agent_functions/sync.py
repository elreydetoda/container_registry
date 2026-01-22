from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
import asyncio


class SyncArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="source",
                type=ParameterType.String,
                description="Source transport (e.g., docker://registry.example.com/myimage)",
                parameter_group_info=[ParameterGroupInfo(required=True)],
            ),
            CommandParameter(
                name="destination",
                type=ParameterType.String,
                description="Destination transport (e.g., dir:/path/to/dir)",
                parameter_group_info=[ParameterGroupInfo(required=True)],
            ),
            CommandParameter(
                name="src_username",
                type=ParameterType.String,
                description="Source registry username (optional)",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="src_password",
                type=ParameterType.String,
                description="Source registry password/token (optional)",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="dest_username",
                type=ParameterType.String,
                description="Destination registry username (optional)",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="dest_password",
                type=ParameterType.String,
                description="Destination registry password/token (optional)",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="src_insecure",
                type=ParameterType.Boolean,
                description="Allow insecure source connections",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value=False,
            ),
            CommandParameter(
                name="dest_insecure",
                type=ParameterType.Boolean,
                description="Allow insecure destination connections",
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
            Success=True,
        )

        try:
            # Build skopeo command
            cmd = ["skopeo", "sync"]

            # Add source authentication if provided
            src_username = taskData.args.get_arg("src_username")
            src_password = taskData.args.get_arg("src_password")
            if src_username and src_password:
                cmd.extend(["--src-creds", f"{src_username}:{src_password}"])

            # Add destination authentication if provided
            dest_username = taskData.args.get_arg("dest_username")
            dest_password = taskData.args.get_arg("dest_password")
            if dest_username and dest_password:
                cmd.extend(["--dest-creds", f"{dest_username}:{dest_password}"])

            # Add insecure flags if needed
            if taskData.args.get_arg("src_insecure"):
                cmd.append("--src-tls-verify=false")
            if taskData.args.get_arg("dest_insecure"):
                cmd.append("--dest-tls-verify=false")

            # Add source and destination
            source = taskData.args.get_arg("source")
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
