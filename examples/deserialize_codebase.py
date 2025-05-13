from codetide.core.models import CodeBase
from codetide.tide import CodeTide

codeBase = CodeBase.deserialize()
tide = CodeTide(codebase=codeBase)

print(tide.get_file_tree_structure())

print(tide.get_module_function_tree())
