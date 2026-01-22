from pathlib import Path
from importlib import import_module

# Get the agent_functions directory
searchPath = Path(__file__).parent / "agent_functions"

# Find all .py files in agent_functions except __init__.py
modules = [f for f in searchPath.glob("*.py") if f.name != "__init__.py"]

# Import all modules and populate globals
for module_file in modules:
    module = import_module(f"{__name__}.agent_functions.{module_file.stem}")
    for attribute_name in dir(module):
        if not attribute_name.startswith("_"):
            globals()[attribute_name] = getattr(module, attribute_name)
