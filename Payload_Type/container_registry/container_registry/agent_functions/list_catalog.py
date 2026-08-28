import json

import requests
from mythic_container.MythicCommandBase import *
from mythic_container.MythicRPC import *

from container_registry.agent_functions.shared import (
    credential_secrets,
    get_arg_or_build_value,
    get_registry_base_url,
    redact_sensitive_text,
    resolve_credentials,
    with_authentication_provenance,
)


class ListCatalogArguments(TaskArguments):
    def __init__(self, command_line, **kwargs):
        super().__init__(command_line, **kwargs)
        self.args = [
            CommandParameter(
                name="BASE_HOST",
                type=ParameterType.String,
                description="Registry base host -- leave empty to use the callback build parameter",
                default_value="",
                parameter_group_info=[ParameterGroupInfo(required=False)],
            ),
            CommandParameter(
                name="INSECURE",
                type=ParameterType.Boolean,
                description="Use HTTP and skip TLS verification",
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
    help_cmd = "list_catalog (standard /v2/_catalog registries only)"
    description = (
        "List repositories from the standard Registry HTTP API V2 /v2/_catalog endpoint; "
        "vendor-specific APIs are out of scope and hosted registries may reject it"
    )
    version = 1
    supported_ui_features = ["container_registry:list_catalog"]
    author = "@elreydetoda"
    argument_class = ListCatalogArguments
    attackmapping = []

    async def create_go_tasking(
        self, taskData: MythicCommandBase.PTTaskMessageAllData
    ) -> MythicCommandBase.PTTaskCreateTaskingMessageResponse:
        response = MythicCommandBase.PTTaskCreateTaskingMessageResponse(
            TaskID=taskData.Task.ID,
            Success=False,
            Completed=True,
        )
        secrets = credential_secrets(taskData)
        resolved_credentials = None

        try:
            registry_host = get_arg_or_build_value(taskData, "BASE_HOST")
            insecure = get_arg_or_build_value(taskData, "INSECURE")
            resolved_credentials = resolve_credentials(taskData)
            registry_url = get_registry_base_url(registry_host, insecure)
            catalog_url = f"{registry_url}/v2/_catalog"

            registry_response = requests.get(
                catalog_url,
                auth=resolved_credentials.pair,
                verify=not insecure,
                timeout=30,
            )

            if registry_response.status_code != 200:
                error_detail = f"HTTP {registry_response.status_code}: {registry_response.reason}"
                if registry_response.text:
                    error_detail += f"\n\n{registry_response.text}"
                safe_detail = redact_sensitive_text(error_detail, secrets)
                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=with_authentication_provenance(
                            f"Error accessing registry catalog at {registry_url}:\n{safe_detail}",
                            resolved_credentials,
                        ).encode(),
                    )
                )
                return response

            try:
                catalog_data = registry_response.json()
            except (json.JSONDecodeError, ValueError):
                safe_text = redact_sensitive_text(registry_response.text, secrets)
                await SendMythicRPCResponseCreate(
                    MythicRPCResponseCreateMessage(
                        TaskID=taskData.Task.ID,
                        Response=with_authentication_provenance(
                            f"Error parsing response from {registry_url}:\n\n{safe_text}",
                            resolved_credentials,
                        ).encode(),
                    )
                )
                return response

            repositories = catalog_data.get("repositories", [])
            if repositories:
                formatted_output = f"Registry: {catalog_url}\n"
                formatted_output += f"Repositories ({len(repositories)}):\n\n"
                formatted_output += "".join(f"  - {repository}\n" for repository in repositories)
            else:
                formatted_output = (
                    f"Registry: {registry_url}\n\nNo repositories found or empty catalog."
                )

            await SendMythicRPCResponseCreate(
                MythicRPCResponseCreateMessage(
                    TaskID=taskData.Task.ID,
                    Response=with_authentication_provenance(
                        redact_sensitive_text(formatted_output, secrets),
                        resolved_credentials,
                    ).encode(),
                )
            )
            response.Success = True

        except Exception as error:
            message = f"Exception occurred: {redact_sensitive_text(error, secrets)}"
            if resolved_credentials is not None:
                message = with_authentication_provenance(message, resolved_credentials)
            await SendMythicRPCResponseCreate(
                MythicRPCResponseCreateMessage(
                    TaskID=taskData.Task.ID,
                    Response=message.encode(),
                )
            )

        return response
