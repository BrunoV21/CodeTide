from typing import List, Union
import re

def parse_xml_content(text: str, tag: str = "diff", multiple: bool = False) -> Union[str, List[str], None]:
    """
    Extract content between <tag>...</tag> markers.
    
    Args:
        text: Full input text.
        tag: The tag name to extract content from (default: 'diff').
        multiple: If True, return all matching blocks. If False, return only the first one.
    
    Returns:
        The extracted content as a string (if one block), list of strings (if multiple),
        or None if no blocks found.
    """
    pattern = fr"<{tag}>\s*(.*?)\s*</{tag}>"
    matches = re.findall(pattern, text, re.DOTALL)

    if not matches:
        return None

    return matches if multiple else matches[0]
