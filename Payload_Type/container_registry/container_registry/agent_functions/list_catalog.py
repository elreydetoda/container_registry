from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *
from container_registry.agent_functions.shared import get_arg_or_build_value, get_registry_base_url
import json
import requests


class ListCatalogArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="BASE_HOST",
                type=ParameterType.String,
                description="Registry BASE_HOST (e.g., registry-1.docker.io, ghcr.io, localhost:5000) -- leave empty to use from provided build parameters",
                default_value="",
                parameter_group_info=[ParameterGroupInfo(required=False)],
            ),
            CommandParameter(
                name="USERNAME",
                type=ParameterType.String,
                description="Registry username (optional) -- leave empty to use from provided build parameters",
                default_value="",
                parameter_group_info=[ParameterGroupInfo(required=False)],
            ),
            CommandParameter(
                name="PASSWORD",
                type=ParameterType.String,
                description="Registry password/token (optional) -- leave empty to use from provided build parameters",
                default_value="",
                parameter_group_info=[ParameterGroupInfo(required=False)],
            ),
            CommandParameter(
                name="INSECURE",
                type=ParameterType.Boolean,
                description="Allow insecure connections (skip TLS verification)",
                default_value=False,
                parameter_group_info=[ParameterGroupInfo(required=False)],
            ),
        ]

    async def parse_arguments(self):
        if len(self.command_line) == 0:
            raise ValueError("Must supply arguments")
        if self.command_line[0] == "{":
            self.load_args_from_json_string(self.command_line)
        else:
            raise ValueError("Require JSON arguments")


class ListCatalog(CommandBase):
    cmd = "list_catalog"
    needs_admin = False
    help_cmd = "list_catalog"
    description = "List all repositories in a registry using the /v2/_catalog API endpoint"
    version = 1
    supported_ui_features = ["container_registry:list_catalog"]
    author = "@elreydetoda"
    argument_class = ListCatalogArguments
    attackmapping = []

    async def create_go_tasking(self, taskData: MythicCommandBase.PTTaskMessageAllData) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=False,
            Completed=True,
        )

        try:
            registry_url = get_arg_or_build_value(taskData, "BASE_HOST")
            username = get_arg_or_build_value(taskData, "USERNAME")
            password = get_arg_or_build_value(taskData, "PASSWORD")
            insecure = get_arg_or_build_value(taskData, "INSECURE")

            registry_url = get_registry_base_url(registry_url, insecure)

            # Build the catalog endpoint BASE_HOST
            catalog_url = f"{registry_url}/v2/_catalog"

            # Prepare authentication
            auth = None
            if username and password:
                auth = (username, password)

            # Prepare SSL verification setting
            verify_ssl = not insecure

            # Make the GET request
            resp = requests.get(catalog_url, auth=auth, verify=verify_ssl, timeout=30)

            # Check if request was successful
            if resp.status_code == 200:
                try:
                    # Parse JSON response
                    catalog_data = resp.json()
                    repositories = catalog_data.get("repositories", [])

                    if repositories:
                        formatted_output = f"Registry: {registry_url}\n"
                        formatted_output += f"Repositories ({len(repositories)}):\n\n"
                        for repo in repositories:
                            formatted_output += f"  - {repo}\n"
                    else:
                        formatted_output = f"Registry: {registry_url}\n\nNo repositories found or empty catalog."

                    await SendMythicRPCResponseCreate(
                        MythicRPCResponseCreateMessage(
                            TaskID=taskData.Task.ID,
                            Response=formatted_output.encode(),
                        )
                    )
                    response.Success = True
                except json.JSONDecodeError:
                    # If response is not JSON, might be an error message
                    await SendMythicRPCResponseCreate(
                        MythicRPCResponseCreateMessage(
                            TaskID=taskData.Task.ID,
                            Response=f"Error parsing response from {registry_url}:\n\n{resp.text}".encode(),
                        )
                    )
            else:
                error_msg = f"HTTP {resp.status_code}: {resp.reason}"
                if resp.text:
                    error_msg += f"\n\n{resp.text}"

                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=f"Error accessing registry catalog at {registry_url}:\n{error_msg}".encode(),
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
