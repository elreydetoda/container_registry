from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
import asyncio


class DeleteArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="image",
                type=ParameterType.String,
                description="Image to delete (e.g., docker://docker.io/myrepo/myimage:tag)",
                parameter_group_info=[ParameterGroupInfo(required=True)],
            ),
            CommandParameter(
                name="username",
                type=ParameterType.String,
                description="Registry username (optional)",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="password",
                type=ParameterType.String,
                description="Registry password/token (optional)",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="insecure",
                type=ParameterType.Boolean,
                description="Allow insecure connections",
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


class Delete(CommandBase):
    cmd = "delete"
    needs_admin = False
    help_cmd = "delete"
    description = "Delete a container image from a registry using skopeo delete"
    version = 1
    supported_ui_features = ["container_registry:delete"]
    author = "@elreydetoda"
    argument_class = DeleteArguments
    attackmapping = []

    async def create_go_tasking(self, taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=True,
        )

        try:
            # Build skopeo command
            cmd = ["skopeo", "delete"]

            # Add authentication if provided
            username = taskData.args.get_arg("username")
            password = taskData.args.get_arg("password")
            if username and password:
                cmd.extend(["--creds", f"{username}:{password}"])

            # Add insecure flag if needed
            if taskData.args.get_arg("insecure"):
                cmd.append("--tls-verify=false")

            # Add the image
            image = taskData.args.get_arg("image")
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
                output = stdout.decode()
                error_output = stderr.decode()
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
            else:
                error_msg = stderr.decode()
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
                    Response=f"Exception occurred: {str(e)}".encode(),
                )
            )

        return response
