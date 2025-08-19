from .defaults import DEFAULT_ENCODING
from typing import Union
from pathlib import Path

def readFile(path :Union[str, Path], mode :str="r", skip_errors :bool=False)->str:
    try:
        with open(path, mode, encoding=DEFAULT_ENCODING if mode != "rb" else None) as _file:
            contents = _file.read()
    except Exception as e:
        if skip_errors:
            return ""
        raise e
    
    return contents

def writeFile(contents: Union[str, bytes], path: Union[str, Path], mode: str = "w"):
    if isinstance(contents, bytes):
        with open(path, "wb") as f:
            f.write(contents)
    else:
        with open(path, mode, encoding=DEFAULT_ENCODING) as f:
            f.write(contents)

def wrap_package_dependencies(content: str) -> str:
    return f"""<PACKAGE_DEPENDENCIES_START>
{content}
</PACKAGE_DEPENDENCIES_END>"""

def wrap_content(content: str, filepath: str) -> str:
    if filepath == "PACKAGES":
        return wrap_package_dependencies(content)
    
    return f"""<FILE_START::{filepath}>
{content}
</FILE_END::{filepath}>"""

CONTEXT_INTRUCTION = """
[CONTEXT FILES START BELOW]
These files provide dependencies, configuration, and supporting logic.
You may modify them **only if absolutely necessary** to implement the desired logic or ensure compatibility with the changes in the target file.
Otherwise, leave them unchanged.
"""

TARGET_INSTRUCTION = """
[TARGET FILE STARTS BELOW]
The following file is the main focus. 
Apply your changes primarily to this file.
Use the context above to ensure correctness and compatibility.
"""