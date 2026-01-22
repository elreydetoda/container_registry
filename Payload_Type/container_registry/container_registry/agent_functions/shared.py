from typing import Any
from enum import Enum
from mythic_container.MythicCommandBase import PTTaskMessageAllData, MythicRPCPayloadConfigurationBuildParameter

class BuildParamNames(Enum):
    BASE_HOST = "BASE_HOST"
    USERNAME = "USERNAME"
    PASSWORD = "PASSWORD"
    INSECURE = "INSECURE"

def get_build_info(all_data: PTTaskMessageAllData, key_requested: str) -> Any | None:
    for buildParam in all_data.BuildParameters:
        if buildParam.Name == key_requested:
            return buildParam.Value

def get_arg_or_build_value(taskData: PTTaskMessageAllData, key_requested) -> Any:
    return taskData.args.get_arg(key_requested) or get_build_info(taskData, BuildParamNames[key_requested].value)

def get_registry_base_url(provide_url: str, insecure: bool) -> str:
    # Ensure registry_url doesn't end with /
    registry_url = provide_url.rstrip('/')
    if insecure:
        return f"http://{registry_url}"
    else:
        return f"https://{registry_url}"
