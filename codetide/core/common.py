import re
from codetide.core.defaults import DEFAULT_ENCODING
from typing import Union
from pathlib import Path

def readFile(path :Union[str, Path], mode :str="r")->str:
    with open(path, mode, encoding=DEFAULT_ENCODING if mode != "rb" else None) as _file:
        contents = _file.read()
    return contents

def writeFile(contents :str, path :Union[str, Path], mode :str="w"):
    with open(path, mode, encoding=DEFAULT_ENCODING) as  _file:
        _file.write(contents)

def wrap_content(content: str, filepath: str) -> str:
    safe_path = re.sub(r"[^\w\-\.]", "_", filepath)
    return f"""<FILE_START::{safe_path}>
{content}
</FILE_END::{safe_path}>"""
