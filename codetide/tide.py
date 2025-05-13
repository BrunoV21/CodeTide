from codetide.core.utils import find_code_files, get_language_from_extension, read_file_content
from codetide.core.defaults import DEFAULT_IGNORE_PATTERNS, SERIALIZATION_DIR
from codetide.parsers.python_parser import PythonParser
from codetide.core.models import CodeBase
from codetide.core.pydantic_graph import PydanticGraph, Node, Edge

from typing import List, Union, Dict, Optional, Set, Any, Tuple
from pathlib import Path
from tqdm import tqdm
import logging
import os
import json
from collections import defaultdict
import time
import xml.etree.ElementTree as ET
from xml.dom import minidom

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
                    code_file = parser.parse_file(file_path, content, self.root_path)
                    
                    # Add the file to the codebase
                    codebase.elements.add_element(code_file)
                    codebase.files.append(code_file.id)
                    
                    # Add all elements from the file to the codebase
                    elements = parser.extract_all_elements(file_path, content, self.root_path)
                    for element_type, element_list in elements.items():
                        for element in element_list:
                            codebase.elements.add_element(element)
                except Exception as e:
                    logger.error(f"Error parsing file {file_path}: {e}")
        
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

    def get_file_tree_structure(self) -> Dict:
        """
        Generate a hierarchical tree structure based on file locations and directory structure.
        
        Returns:
            Dictionary representing the file tree where keys are directory names and 
            values are either nested dictionaries or file names
        """
        if not self.codebase:
            raise ValueError("Project not parsed yet. Call parse_project() first.")
        
        file_tree = {}
        
        # Get all files from the codebase
        for file_id in self.codebase.files:
            file_element = self.codebase.elements.get_element(file_id)
            if file_element:
                # Get the relative path from the root path
                try:
                    rel_path = file_element.file_path.relative_to(self.codebase.root_path)
                    # Split into path parts
                    path_parts = list(rel_path.parts)
                    
                    # Navigate to the correct position in the tree
                    current = file_tree
                    for i, part in enumerate(path_parts):
                        if i == len(path_parts) - 1:  # This is a file
                            current[part] = file_id
                        else:  # This is a directory
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                except ValueError:
                    # If the file is not relative to the root path, add it at the root level
                    file_tree[file_element.file_path.name] = file_id
        
        return file_tree
    
    def get_module_function_tree(self) -> Dict:
        """
        Generate a hierarchical tree structure based on modules, classes, and functions in each file.
        Ignores imports and variables as specified.
        
        Returns:
            Dictionary representing the module tree where keys are file names and
            values are nested dictionaries of modules, classes, and functions
        """
        if not self.codebase or not self.graph:
            raise ValueError("Project not parsed yet. Call parse_project() first.")
        
        module_tree = {}
        
        # Create a mapping from file paths to file IDs
        file_path_to_id = {}
        for file_id in self.codebase.files:
            file_element = self.codebase.elements.get_element(file_id)
            if file_element:
                file_path_to_id[str(file_element.file_path)] = file_id
        
        # Process each file
        for file_id in self.codebase.files:
            file_element = self.codebase.elements.get_element(file_id)
            if file_element:
                # Get the file path as a string for the tree
                file_name = file_element.file_path.name
                
                # Initialize the file's entry in the tree
                if file_name not in module_tree:
                    module_tree[file_name] = {
                        "id": file_id,
                        "functions": [],
                        "classes": {}
                    }
                
                # Keep track of functions that belong to classes
                class_functions = set()
                
                # First, identify all functions that belong to classes
                for class_id in file_element.classes:
                    class_element = self.codebase.elements.get_element(class_id)
                    if class_element:
                        for method_id in class_element.methods:
                            class_functions.add(method_id)
                
                # Add functions directly defined in the file (not in a class)
                for func_id in file_element.functions:
                    # Only include functions not part of any class
                    if func_id not in class_functions:
                        func_element = self.codebase.elements.get_element(func_id)
                        if func_element:
                            module_tree[file_name]["functions"].append({
                                "id": func_id,
                                "name": func_element.name,
                                "line_range": (func_element.start_line, func_element.end_line)
                            })
                
                # Add classes and their methods
                for class_id in file_element.classes:
                    class_element = self.codebase.elements.get_element(class_id)
                    if class_element:
                        class_methods = []
                        
                        # Add methods of the class
                        for method_id in class_element.methods:
                            method_element = self.codebase.elements.get_element(method_id)
                            if method_element:
                                class_methods.append({
                                    "id": method_id,
                                    "name": method_element.name,
                                    "line_range": (method_element.start_line, method_element.end_line)
                                })
                        
                        # Add the class to the tree
                        module_tree[file_name]["classes"][class_element.name] = {
                            "id": class_id,
                            "methods": class_methods,
                            "line_range": (class_element.start_line, class_element.end_line)
                        }
        
        return module_tree
        
    def _find_node_by_name(self, name: str) -> Optional[str]:
        """
        Find a node ID by its name.
        
        Args:
            name: Name of the node to find
            
        Returns:
            Node ID if found, None otherwise
        """
        if not self.graph:
            raise ValueError("Project not parsed yet. Call parse_project() first.")
        
        for node_id, node in self.graph.nodes.items():
            if node.data and node.data.get('name') == name:
                return node_id
        
        return None
    
    def _find_node_by_location(self, file_path: Union[str, Path], line_range: Optional[Tuple[int, int]] = None) -> Optional[str]:
        """
        Find a node ID by its file path and optional line range.
        
        Args:
            file_path: Path to the file
            line_range: Optional tuple of (start_line, end_line)
            
        Returns:
            Node ID if found, None otherwise
        """
        if not self.graph:
            raise ValueError("Project not parsed yet. Call parse_project() first.")
        
        # Convert file_path to string for comparison
        if isinstance(file_path, Path):
            file_path = str(file_path)
        
        matching_nodes = []
        
        for node_id, node in self.graph.nodes.items():
            if node.data and node.data.get('file_path') == file_path:
                if line_range is None:
                    # If no line range specified, return the file node
                    if node.data.get('element_type') == 'file':
                        return node_id
                    matching_nodes.append(node_id)
                else:
                    # Check if the node is within the specified line range
                    node_start = node.data.get('start_line')
                    node_end = node.data.get('end_line')
                    
                    if node_start is not None and node_end is not None:
                        if line_range[0] <= node_start and node_end <= line_range[1]:
                            matching_nodes.append(node_id)
        
        # If multiple matches, return the most specific one (smallest scope)
        if matching_nodes:
            smallest_scope = None
            smallest_size = float('inf')
            
            for node_id in matching_nodes:
                node = self.graph.nodes[node_id]
                if node.data:
                    node_start = node.data.get('start_line', 0)
                    node_end = node.data.get('end_line', 0)
                    size = node_end - node_start
                    
                    if size < smallest_size:
                        smallest_size = size
                        smallest_scope = node_id
            
            return smallest_scope
        
        return None
    
    def _generate_xml_for_node(self, node_id: str, visited: Set[str]) -> ET.Element:
        """
        Generate XML representation for a node and its data.
        
        Args:
            node_id: ID of the node
            visited: Set of visited node IDs to avoid cycles
            
        Returns:
            ElementTree Element representing the node
        """
        if node_id in visited:
            # If already visited, just create a reference
            ref_elem = ET.Element("reference")
            ref_elem.set("id", node_id)
            return ref_elem
        
        visited.add(node_id)
        
        node = self.graph.nodes.get(node_id)
        if not node or not node.data:
            # If node doesn't exist or has no data, return empty element
            return ET.Element("unknown", id=node_id)
        
        # Create element based on node type
        element_type = node.data.get('element_type', 'unknown')
        elem = ET.Element(element_type)
        elem.set("id", node_id)
        
        # Add node data as attributes
        for key, value in node.data.items():
            if key != 'element_type' and value is not None:
                elem.set(key, str(value))
        
        return elem
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if a cached result is still valid by checking timestamps.
        
        Args:
            cache_key: Cache key to check
            
        Returns:
            True if cache is valid, False otherwise
        """
        # If no timestamp, cache is invalid
        if cache_key not in self._cache_timestamps:
            return False
        
        # For now, let's assume cache is always valid
        # In a real implementation, you would check if files have been modified
        # by comparing file modification times against the cache timestamp
        return True
    
    def get(self, entry_points: Union[str, List[str], Dict], degree: int = 1) -> Union[str, List[str]]:
        """
        Get XML representation of one or more entry points and their dependencies.
        
        Args:
            entry_points: Entry point(s) to get. Can be:
                          - A string (node name or ID)
                          - A dict with 'file_path' and optional 'line_range' keys
                          - A list of the above
            degree: Number of degrees of dependencies to include (-1 for all)
            
        Returns:
            XML string representation of the entry points and their dependencies
        """
        if not self.codebase or not self.graph:
            raise ValueError("Project not parsed yet. Call parse_project() first.")
        
        # Normalize entry_points to a list
        if isinstance(entry_points, (str, dict)):
            entry_points = [entry_points]
        
        results = []
        
        for entry_point in entry_points:
            # Generate a cache key based on entry_point and degree
            cache_key = f"{str(entry_point)}:{degree}"
            
            # Check if result is in cache and valid
            if cache_key in self._cache and self._is_cache_valid(cache_key):
                results.append(self._cache[cache_key])
                continue
            
            # Find the node ID based on the entry point
            node_id = None
            
            if isinstance(entry_point, str):
                # Try as node ID first
                if entry_point in self.graph.nodes:
                    node_id = entry_point
                else:
                    # Try as node name
                    node_id = self._find_node_by_name(entry_point)
            elif isinstance(entry_point, dict):
                # Entry point is a location (file_path and optional line_range)
                file_path = entry_point.get('file_path')
                line_range = entry_point.get('line_range')
                
                if file_path:
                    node_id = self._find_node_by_location(file_path, line_range)
            
            if not node_id:
                # Entry point not found
                results.append(f"<error>Entry point not found: {entry_point}</error>")
                continue
            
            # Get the node and its dependencies
            visited = set()
            root_elem = None
            
            # Create the root element based on the entry point
            root_elem = self._generate_xml_for_node(node_id, visited)
            
            # Get neighboring nodes based on degree
            if degree != 0:
                neighbor_ids = set()
                
                if degree > 0:
                    # Get neighbors up to specified degree
                    neighbor_ids = set(self.graph.get_neighbors(node_id, degree))
                elif degree == -1:
                    # Get all reachable nodes
                    to_visit = [node_id]
                    all_visited = {node_id}
                    
                    while to_visit:
                        current = to_visit.pop(0)
                        neighbors = self.graph.get_neighbors(current, 1)
                        
                        for neighbor in neighbors:
                            if neighbor not in all_visited:
                                to_visit.append(neighbor)
                                all_visited.add(neighbor)
                    
                    neighbor_ids = all_visited - {node_id}
                
                # Add children elements for dependencies
                for dep_id in neighbor_ids:
                    if dep_id not in visited:
                        dep_elem = self._generate_xml_for_node(dep_id, visited)
                        root_elem.append(dep_elem)
            
            # Convert to string
            xml_str = self._prettify_xml(root_elem)
            
            # Cache the result with current timestamp
            self._cache[cache_key] = xml_str
            self._cache_timestamps[cache_key] = time.time()
            
            results.append(xml_str)
        
        # Return single string or list based on input
        if len(results) == 1:
            return results[0]
        else:
            return results
    
    def _prettify_xml(self, elem: ET.Element) -> str:
        """
        Convert an ElementTree element to a pretty-printed XML string.
        
        Args:
            elem: ElementTree Element to convert
            
        Returns:
            Pretty-printed XML string
        """
        rough_string = ET.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ").strip()
    
    def clear_cache(self) -> None:
        """Clear the cache for entry points."""
        self._cache = {}
        self._cache_timestamps = {}
    
    def invalidate_cache_for_file(self, file_path: Union[str, Path]) -> None:
        """
        Invalidate cache entries related to a specific file.
        
        Args:
            file_path: Path to the file that has changed
        """
        # In a real implementation, you would identify and invalidate
        # only the cache entries related to the changed file
        # For simplicity, we'll clear the entire cache for now
        self.clear_cache()
    
    def serialize_and_save(self, 
                          serialization_dir: Union[Path, str] = SERIALIZATION_DIR) -> None:
        """
        Serialize and save the codebase and graph to files.
        
        Args:
            serialization_dir: Directory to save serialized data
        """
        if not self.codebase or not self.graph:
            raise ValueError("Project not parsed yet. Call parse_project() first.")
        
        # Serialize codebase
        self.codebase.serialize(serialization_dir)
        
        # Serialize graph
        self.graph.serialize(serialization_dir)
    
    @classmethod
    def load_from_serialized(cls, 
                            root_path: Union[str, Path],
                            serialization_dir: Union[Path, str] = SERIALIZATION_DIR) -> 'CodeTide':
        """
        Load codebase and graph from serialized files.
        
        Args:
            root_path: Root path of the project
            serialization_dir: Directory containing serialized data
            
        Returns:
            CodeTide instance with loaded codebase and graph
        """
        # Create a new instance
        code_tide = cls(root_path)
        
        # Load codebase
        code_tide.codebase = CodeBase.deserialize(serialization_dir)
        
        # Load graph
        code_tide.graph = PydanticGraph.deserialize(serialization_dir)
        
        return code_tide

### TODO add support to retrieve context via parsing from selected entry point and comile into list of markdown files
### TODO add support to generate mermaid representation of the graph in plaintxt + html
### TODO add support for file structure tree and file + modules / function / variables from codebase
### TODO add support to serialize and deserialize CodeBase for speed up -> DONE
### TODO add support to update codebase each time a new file / files are created