# Add the root directory to sys.path if needed
# This might be needed if the codetide package isn't installed
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codetide.core.models import CodeBase
from codetide.tide import CodeTide

codeBase = CodeBase.deserialize()
tide = CodeTide(codebase=codeBase)

print(tide.get_files_tree())
print("\n\n")
print(tide.get_modules_tree())
