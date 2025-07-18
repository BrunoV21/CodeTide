from typing import List, Union
import re

def parse_patch_blocks(text: str, multiple: bool = True) -> Union[str, List[str], None]:
    """
    Extract content between *** Begin Patch and *** End Patch markers (inclusive),
    ensuring that both markers are at zero indentation (start of line, no leading spaces).

    Args:
        text: Full input text containing one or more patch blocks.
        multiple: If True, return a list of all patch blocks. If False, return the first match.

    Returns:
        A string (single patch), list of strings (multiple patches), or None if not found.
    """
    
    pattern = r"(?m)^(\*\*\* Begin Patch[\s\S]*?^\*\*\* End Patch)$"
    matches = re.findall(pattern, text)

    if not matches:
        return None

    return matches if multiple else matches[0]