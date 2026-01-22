from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
import json
import asyncio


class InspectArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="image",
                type=ParameterType.String,
                description="Image to inspect (e.g., docker://docker.io/library/alpine:latest)",
                parameter_group_info=[ParameterGroupInfo(required=True)],
            ),
            CommandParameter(
                name="username",
                type=ParameterType.String,
                description="Registry username (optional, overrides build parameter)",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="password",
                type=ParameterType.String,
                description="Registry password/token (optional, overrides build parameter)",
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
            CommandParameter(
                name="raw",
                type=ParameterType.Boolean,
                description="Return raw manifest instead of formatted output",
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


class Inspect(CommandBase):
    cmd = "inspect"
    needs_admin = False
    help_cmd = "inspect"
    description = "Inspect a container image in a registry using skopeo inspect"
    version = 1
    supported_ui_features = ["container_registry:inspect"]
    author = "@elreydetoda"
    argument_class = InspectArguments
    attackmapping = []

    async def create_go_tasking(self, taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=True,
        )

        try:
            # Build skopeo command
            cmd = ["skopeo", "inspect"]

            # Add authentication if provided
            username = taskData.args.get_arg("username")
            password = taskData.args.get_arg("password")
            if username and password:
                cmd.extend(["--creds", f"{username}:{password}"])

            # Add insecure flag if needed
            if taskData.args.get_arg("insecure"):
                cmd.append("--tls-verify=false")

            # Add raw flag if requested
            if taskData.args.get_arg("raw"):
                cmd.append("--raw")

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
                except json.JSONDecodeError:
                    # If not JSON, return as-is
                    await SendMythicRPCResponseCreate(
                        MythicRPCResponseCreateMessage(
                            TaskID=taskData.Task.ID,
                            Response=f"Successfully inspected {image}:\n\n{output}".encode(),
                        )
                    )
            else:
                error_msg = stderr.decode()
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
                    Response=f"Exception occurred: {str(e)}".encode(),
                )
            )

        return response
