from codetide.core.utils import find_code_files, get_language_from_extension, read_file_content
from codetide.core.defaults import DEFAULT_IGNORE_PATTERNS
from codetide.parsers.python_parser import PythonParser
from codetide.core.models import CodeBase
from codetide.core.pydantic_graph import PydanticGraph

from typing import List, Union, Optional    
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from tqdm import tqdm
import logging

# Setup logging
logger = logging.getLogger(__name__)

class CodeTide:
    """
    Class for parsing an entire project and building a CodeBase model with advanced querying capabilities.
    """
    def __init__(self, root_path: Optional[Union[str, Path]]=None,
                 codebase :Optional[CodeBase]=None, 
                 languages: List[str] = None,
                 custom_ignore_patterns: List[str] = None):
        """
        Initialize a project parser.
        
        Args:
            root_path: Root directory of the project
            languages: List of languages to parse (None for all supported languages)
            custom_ignore_patterns: Additional patterns to ignore beyond gitignore and defaults
        """
        if codebase is not None:
            self.root_path = codebase.root_path
            self.codebase = codebase
            self.graph = PydanticGraph.from_codebase(codebase)
        else:
            self.root_path = Path(root_path) if isinstance(root_path, str) else root_path
            # Initialize codebase and graph as None until project is parsed
            self.codebase = None
            self.graph = None
        
        self.languages = languages
        
        # Initialize parsers for different languages
        self.parsers = {
            "python": PythonParser()
        }
        
        # Combine ignore patterns from defaults, gitignore, and custom patterns
        self.ignore_patterns = list(DEFAULT_IGNORE_PATTERNS)
        
        # Add patterns from .gitignore if it exists
        gitignore_patterns = self._load_gitignore_patterns()
        if gitignore_patterns:
            self.ignore_patterns.extend(gitignore_patterns)
            
        # Add custom ignore patterns
        if custom_ignore_patterns:
            self.ignore_patterns.extend(custom_ignore_patterns)
        
        # Cache for entry points and their dependencies
        self._cache = {}
        self._cache_timestamps = {}  # Store timestamps to check for staleness
        
    def _load_gitignore_patterns(self) -> List[str]:
        """
        Load patterns from .gitignore file if it exists.
        
        Returns:
            List of gitignore patterns
        """
        gitignore_path = self.root_path / ".gitignore"
        patterns = []
        
        if gitignore_path.exists() and gitignore_path.is_file():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            # Convert gitignore pattern to fnmatch pattern
                            if line.startswith('/'):
                                # Pattern anchored to root
                                line = line[1:]  # Remove leading slash
                                pattern = f"{self.root_path.name}/{line}"
                            else:
                                # Pattern can match anywhere
                                pattern = f"*{line}" if not line.startswith('*') else line
                                
                            patterns.append(pattern)
                            # Also add pattern with trailing /* to catch directories
                            if not pattern.endswith('*'):
                                patterns.append(f"{pattern}/*")
            except Exception as e:
                logger.warning(f"Error reading .gitignore file: {e}")
                
        return patterns
    
    def parse_project(self) -> CodeBase:
        """
        Parse the entire project and build a CodeBase model.
        
        Returns:
            CodeBase object containing all parsed elements
        """
        # Initialize an empty CodeBase
        codebase = CodeBase(root_path=self.root_path)
        
        # Find all code files in the project
        code_files = find_code_files(self.root_path, self.languages, self.ignore_patterns)
        
        # Parse each file with the appropriate parser
        for file_path in tqdm(code_files):
            language = get_language_from_extension(file_path)
            if language and language in self.parsers:
                try:
                    # Read file content
                    content = read_file_content(file_path)
                    if content is None:
                        logger.warning(f"Could not read file: {file_path}")
                        continue
                    
                    # Parse the file
                    parser = self.parsers[language]
                    code_file, elements = parser.parse_file(file_path, content, self.root_path)
                    
                    # Add the file to the codebase
                    codebase.elements.add_element(code_file)
                    codebase.files.append(code_file.id)
                    codebase.modules.extend(code_file.classes) 
                    codebase.modules.extend(code_file.functions)
                    codebase.modules.extend(code_file.variables)
                    
                    # Add all elements from the file to the codebase
                    for element_type, element_list in elements.items():
                        for element in element_list:
                            codebase.elements.add_element(element)
                except Exception as e:
                    logger.error(f"Error parsing file {file_path}: {e}")
        
        codebase._sort_modules()
        # Resolve dependencies between elements
        self._resolve_dependencies(codebase)
        
        # Store the codebase
        self.codebase = codebase
        
        # Create the graph based on the codebase
        self.graph = PydanticGraph.from_codebase(codebase)
        
        # Clear cache when a new project is parsed
        self._cache = {}
        self._cache_timestamps = {}
        
        return codebase
    
    def _resolve_dependencies(self, codebase: CodeBase) -> None:
        """
        Resolve dependencies between elements in the codebase.
        
        Args:
            codebase: CodeBase object containing all parsed elements
        """
        # Resolve dependencies for each language
        for language, parser in self.parsers.items():
            try:
                parser.resolve_dependencies(codebase)
            except Exception as e:
                logger.error(f"Error resolving dependencies for language {language}: {e}")

    @lru_cache(maxsize=1024)
    def get_files_tree(self):
        """
        Build a string representation of a file tree structure from a list of file paths.
        
        Args:
            file_list (list): A list of file paths, each prefixed with "file:"
        
        Returns:
            str: A string representation of the file tree structure
        """
        # Strip the "file:" prefix and create a dictionary to represent the tree
        tree = {}
        
        for file_path in self.codebase.files:
            if file_path.startswith("file:"):
                path = file_path[5:]  # Remove the "file:" prefix
                
                # Split the path into components
                parts = path.replace('\\', '/').split('/')
                
                # Navigate the tree and create directories as needed
                current = tree
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:  # This is a file
                        if 'files' not in current:
                            current['files'] = []
                        current['files'].append(part)
                    else:  # This is a directory
                        if 'dirs' not in current:
                            current['dirs'] = {}
                        if part not in current['dirs']:
                            current['dirs'][part] = {}
                        current = current['dirs'][part]
    
        # Generate the string representation of the tree
        tree_lines = self._generate_tree_string(tree)

        if self.root_path:
            result = f"{Path(self.root_path).name}/\n"
            # Indent all lines by 4 spaces
            result += "\n".join(f" {line}" for line in tree_lines)
            return result
        else:
            return "\n".join(tree_lines)
    
    @classmethod
    def _generate_tree_string(cls, node, prefix :str="", is_last :bool=True):
        output = []
        
        # Add files
        if 'files' in node:
            files = sorted(node['files'])
            for i, file in enumerate(files):
                is_last_file = (i == len(files) - 1) and ('dirs' not in node)
                if is_last_file:
                    output.append(f"{prefix}└── {file}")
                else:
                    output.append(f"{prefix}├── {file}")
        
        # Add directories
        if 'dirs' in node:
            dirs = sorted(node['dirs'].keys())
            for i, dir_name in enumerate(dirs):
                is_last_dir = (i == len(dirs) - 1)
                if is_last_dir:
                    output.append(f"{prefix}└── {dir_name}/")
                    new_prefix = f"{prefix}    "
                else:
                    output.append(f"{prefix}├── {dir_name}/")
                    new_prefix = f"{prefix}│   "
                
                # Recursively add the contents of this directory
                output.extend(cls._generate_tree_string(node['dirs'][dir_name], new_prefix, is_last_dir))
        
        return output

    @classmethod
    def _render(cls, node, show_type, modules_only, prefix=""):
        lines = []
        keys = sorted(node.keys())
        for i, key in enumerate(keys):
            is_last = (i == len(keys) - 1)
            connector = "└──" if is_last else "├──"
            next_prefix = prefix + ("    " if is_last else "│   ")

            if isinstance(node[key], list):
                lines.append(f"{prefix}{connector} {key}")
                
                # Process the entries in the list for this file
                # Group methods with their parent classes
                entries = node[key]
                j = 0
                while j < len(entries):
                    type_, name = entries[j]
                    
                    # Skip method entries entirely when modules_only is True
                    if modules_only and type_ == "method":
                        j += 1
                        continue
                    
                    if type_ == "class":
                        # Add the class entry
                        is_last_member = (j == len(entries) - 1)
                        member_connector = "└──" if is_last_member else "├──"
                        type_str = " [C]" if show_type else ""
                        lines.append(f"{next_prefix}{member_connector}{type_str} {name}".strip())
                        
                        # Only process methods if modules_only is False
                        if not modules_only:
                            # Look ahead for methods belonging to this class
                            k = j + 1
                            method_prefix = next_prefix + ("    " if is_last_member else "│   ")                        
                            
                            while k < len(entries) and entries[k][0] == "method":
                                method_type, method_name = entries[k]
                                is_last_method = (k + 1 >= len(entries) or entries[k+1][0] != "method")
                                method_connector = "└──" if is_last_method else "├──"
                                method_type_str = " [M]" if show_type else ""
                                new_method = f"{method_prefix}{method_connector}{method_type_str} {method_name}".strip()
                                if new_method not in lines:
                                    lines.append(new_method)
                                k += 1
                            
                            # Update j to skip processed methods
                            j = k
                        else:
                            # When modules_only is True, just move to next entry
                            j += 1
                    else:
                        # Handle other entry types (function, variable, etc.)
                        is_last_member = (j == len(entries) - 1)
                        member_connector = "└──" if is_last_member else "├──"
                        type_abbr = type_[0].upper() if type_ != "method" else "M"
                        type_str = f" [{type_abbr}]" if show_type else ""
                        lines.append(f"{next_prefix}{member_connector}{type_str} {name}".strip())
                        j += 1
            else:
                lines.append(f"{prefix}{connector} {key}/")
                lines.extend(cls._render(node[key], show_type, modules_only, next_prefix))
        return lines

    def get_modules_tree(self, show_type: Optional[bool]=False, modules_only: Optional[bool]=False):
        tree = defaultdict(list)

        # Build nested tree structure: dirs > file > [(type, name)]
        for entry in self.codebase.modules:
            type_, file_path, name, line = entry.split(":")
            
            # If modules_only is True, skip method entries entirely
            if modules_only and type_ == "method":
                continue
                
            parts = Path(file_path).parts
            current = tree

            for part in parts[:-1]:  # Traverse directory components
                current = current.setdefault(part, {})
            file_node = current.setdefault(parts[-1], [])
            file_node.append((type_, name))

        output_lines = self._render(tree, show_type, modules_only)
        if self.root_path:
            return f"{Path(self.root_path).name}/\n" + "\n".join(" " + line for line in output_lines)
        else:
            return "\n".join(output_lines)

### TODO add support to retrieve context via parsing from selected entry point and comile into list of markdown files
### TODO add support to generate mermaid representation of the graph in plaintxt + html
### TODO add support to update codebase each time a new file / files are created