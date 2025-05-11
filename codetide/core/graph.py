from typing import Dict, List, Set, Tuple, Optional, Union, Any
import networkx as nx
from pathlib import Path
import json

from codetide.core.models import CodeBase, CodeElement, DependencyType


class DependencyGraph:
    """
    Class for managing and analyzing the dependency graph of a codebase.
    """
    def __init__(self, codebase: CodeBase):
        """
        Initialize a dependency graph from a CodeBase object.
        
        Args:
            codebase: The CodeBase object containing all parsed elements
        """
        self.codebase = codebase
        self.graph = nx.DiGraph()
        self._build_graph()
    
    def _build_graph(self) -> None:
        """Build the dependency graph from the codebase."""
        # Add all elements as nodes
        for element_id, element in self.codebase.elements.root.items():
            if hasattr(element, 'element_type'):
                # Add node with attributes
                self.graph.add_node(
                    element_id,
                    name=getattr(element, 'name', ''),
                    element_type=getattr(element, 'element_type', ''),
                    language=getattr(element, 'language', ''),
                    file_path=str(getattr(element, 'file_path', ''))
                )
        
        # Add dependencies as edges
        for element_id, element in self.codebase.elements.root.items():
            if hasattr(element, 'dependencies'):
                for dep_type, target_ids in element.dependencies.items():
                    for target_id in target_ids:
                        if target_id in self.codebase.elements.root:
                            self.graph.add_edge(
                                element_id, 
                                target_id, 
                                dep_type=dep_type
                            )
    
    def get_elements_by_type(self, element_type: str) -> List[str]:
        """
        Get all elements of a specific type.
        
        Args:
            element_type: Type of elements to retrieve
            
        Returns:
            List of element IDs of the specified type
        """
        return [
            node_id for node_id, attrs in self.graph.nodes(data=True)
            if attrs.get('element_type') == element_type
        ]
    
    def get_direct_dependencies(self, element_id: str) -> Dict[str, List[str]]:
        """
        Get all direct dependencies of an element.
        
        Args:
            element_id: ID of the element
            
        Returns:
            Dictionary mapping dependency types to lists of element IDs
        """
        dependencies = {}
        
        if element_id in self.graph:
            for _, target_id, edge_data in self.graph.out_edges(element_id, data=True):
                dep_type = edge_data.get('dep_type', 'unknown')
                if dep_type not in dependencies:
                    dependencies[dep_type] = []
                dependencies[dep_type].append(target_id)
        
        return dependencies
    
    def get_dependents(self, element_id: str) -> List[str]:
        """
        Get all elements that depend on the specified element.
        
        Args:
            element_id: ID of the element
            
        Returns:
            List of element IDs that depend on the specified element
        """
        return list(self.graph.predecessors(element_id)) if element_id in self.graph else []
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Find circular dependencies in the graph.
        
        Returns:
            List of cycles, where each cycle is a list of element IDs
        """
        try:
            return list(nx.simple_cycles(self.graph))
        except nx.NetworkXNoCycle:
            return []
    
    def get_dependency_chain(self, start_id: str, end_id: str) -> Optional[List[str]]:
        """
        Find a dependency chain between two elements.
        
        Args:
            start_id: ID of the starting element
            end_id: ID of the ending element
            
        Returns:
            List of element IDs forming the dependency chain, or None if no path exists
        """
        try:
            return nx.shortest_path(self.graph, start_id, end_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def find_strongly_connected_components(self) -> List[Set[str]]:
        """
        Find strongly connected components in the graph.
        
        Returns:
            List of sets, where each set contains element IDs in a strongly connected component
        """
        return list(nx.strongly_connected_components(self.graph))
    
    def get_element_centrality(self, centrality_type: str = 'degree') -> Dict[str, float]:
        """
        Calculate centrality measures for elements in the graph.
        
        Args:
            centrality_type: Type of centrality to calculate ('degree', 'betweenness', 'eigenvector')
            
        Returns:
            Dictionary mapping element IDs to centrality values
        """
        if centrality_type == 'degree':
            return dict(nx.degree_centrality(self.graph))
        elif centrality_type == 'betweenness':
            return dict(nx.betweenness_centrality(self.graph))
        elif centrality_type == 'eigenvector':
            return dict(nx.eigenvector_centrality(self.graph, max_iter=1000))
        else:
            raise ValueError(f"Unsupported centrality type: {centrality_type}")
    
    def get_dependency_subgraph(self, element_ids: List[str]) -> 'DependencyGraph':
        """
        Get a subgraph containing only the specified elements and their dependencies.
        
        Args:
            element_ids: List of element IDs to include in the subgraph
            
        Returns:
            New DependencyGraph object containing the subgraph
        """
        # Create a new codebase with only the specified elements
        subgraph_codebase = CodeBase(root_path=self.codebase.root_path)
        
        # Add all specified elements and their dependencies
        for element_id in element_ids:
            if element_id in self.codebase.elements.root:
                element = self.codebase.elements.root[element_id]
                subgraph_codebase.elements.add_element(element)
        
        # Build the subgraph
        subgraph = DependencyGraph(subgraph_codebase)
        return subgraph
    
    def to_json(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Export the dependency graph to JSON format.
        
        Args:
            output_path: Path to save the JSON file (if None, only returns the dict)
            
        Returns:
            Dictionary representation of the graph
        """
        nodes = []
        for node_id, attrs in self.graph.nodes(data=True):
            node_data = {
                'id': node_id,
                **attrs
            }
            nodes.append(node_data)
        
        edges = []
        for source_id, target_id, attrs in self.graph.edges(data=True):
            edge_data = {
                'source': source_id,
                'target': target_id,
                'type': attrs.get('dep_type', 'unknown')
            }
            edges.append(edge_data)
        
        graph_data = {
            'nodes': nodes,
            'edges': edges
        }
        
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(graph_data, f, indent=2)
        
        return graph_data
    
