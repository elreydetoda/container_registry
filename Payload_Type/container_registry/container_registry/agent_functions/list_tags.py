from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
from container_registry.agent_functions.shared import get_arg_or_build_value
import asyncio
import json


class ListTagsArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="repository",
                type=ParameterType.String,
                description="Repository to list tags for (e.g., docker://docker.io/library/alpine)",
                parameter_group_info=[ParameterGroupInfo(required=True)],
            ),
            CommandParameter(
                name="USERNAME",
                type=ParameterType.String,
                description="Registry username (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="PASSWORD",
                type=ParameterType.String,
                description="Registry password/token (optional) -- leave empty to use from provided build parameters",
                parameter_group_info=[ParameterGroupInfo(required=False)],
                default_value="",
            ),
            CommandParameter(
                name="INSECURE",
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


class ListTags(CommandBase):
    cmd = "list_tags"
    needs_admin = False
    help_cmd = "list_tags"
    description = "List all tags for a repository using skopeo list-tags"
    version = 1
    supported_ui_features = ["container_registry:list_tags"]
    author = "@elreydetoda"
    argument_class = ListTagsArguments
    attackmapping = []

    async def create_go_tasking(self, taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=False,
            Completed=True,
        )

        try:
            # Build skopeo command
            cmd = ["skopeo", "list-tags"]

            # Add authentication if provided
            username = get_arg_or_build_value(taskData, "USERNAME")
            password = get_arg_or_build_value(taskData, "PASSWORD")
            if username and password:
                cmd.extend(["--creds", f"{username}:{password}"])

            # Add insecure flag if needed
            insecure = get_arg_or_build_value(taskData, "INSECURE")
            if insecure:
                cmd.append("--tls-verify=false")

            # Add the repository
            repository = taskData.args.get_arg("repository")
            cmd.append(repository)

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
                    tags = json_output.get("Tags", [])
                    formatted_output = f"Repository: {json_output.get('Repository', repository)}\n"
                    formatted_output += f"Tags ({len(tags)}):\n"
                    for tag in tags:
                        formatted_output += f"  - {tag}\n"

                    await SendMythicRPCResponseCreate(
                        MythicRPCResponseCreateMessage(
                            TaskID=taskData.Task.ID,
                            Response=formatted_output.encode(),
                        )
                    )
                    response.Success = True
                except json.JSONDecodeError:
                    # If not JSON, return as-is
                    await SendMythicRPCResponseCreate(
                        MythicRPCResponseCreateMessage(
                            TaskID=taskData.Task.ID,
                            Response=f"Tags for {repository}:\n\n{output}".encode(),
                        )
                    )
                    response.Success = True
            else:
                error_msg = stderr.decode()
                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=f"Error listing tags for {repository}:\n{error_msg}".encode(),
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
