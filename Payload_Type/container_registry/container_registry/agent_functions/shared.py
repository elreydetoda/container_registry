from urllib.parse import urlparse
from typing import Any
from mythic_container.MythicCommandBase import PTTaskMessageAllData

def get_build_info(all_data: PTTaskMessageAllData, key_requested: str) -> Any | None:
    for buildParam in all_data.BuildParameters:
        if buildParam.Name == key_requested:
            return buildParam.Value
        # for things like SRC_USERNAME
        elif key_requested.endswith(buildParam.Name):
            return buildParam.Value

def get_arg_or_build_value(taskData: PTTaskMessageAllData, key_requested) -> Any:
    initial_value = None
    if taskData.args.has_arg(key_requested):
        initial_value = taskData.args.get_arg(key_requested)
    # if it's a bool value, just return it
    if isinstance(initial_value, bool):
        return initial_value
    # otherwise check if equivalent to False (e.g. "", None, etc.)
    elif not initial_value:
        selected_value = get_build_info(taskData, key_requested)
    # if not False equivalent, then just return initial value
    else:
        selected_value = initial_value
    return selected_value

def get_registry_base_url(provide_url: str = None, insecure: bool = False, taskData: PTTaskMessageAllData | None = None,) -> str:
    # Ensure registry_url doesn't end with /
    if provide_url is None:
        provide_url = get_arg_or_build_value(taskData, "BASE_HOST")
    
    registry_url = provide_url.rstrip('/')

    if insecure:
        return f"http://{registry_url}"
    else:
        return f"https://{registry_url}"

def get_registry_proto_url(provide_url: str = None, taskData: PTTaskMessageAllData | None = None,) -> str:
    # Ensure registry_url doesn't end with /
    if provide_url is None:
        provide_url = get_arg_or_build_value(taskData, "BASE_HOST")
        if not provide_url.startswith("docker://"):
            provide_url = f"docker://{provide_url}"
    
    registry_url = provide_url.rstrip('/')

    return registry_url
