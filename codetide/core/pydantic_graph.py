
from codetide.core.defaults import SERIALIZATION_DIR, SERIALIZED_GRAPH
from codetide.core.common import writeFile, readFile
from codetide.core.models import CodeBase


from typing import Dict, List, Optional, Union, Set, Any
from pydantic import BaseModel, Field
from pathlib import Path
import networkx as nx
import json
import os


class Node(BaseModel):
    id: str
    data: Optional[dict] = None


class Edge(BaseModel):
    source: str
    target: str
    data: Optional[dict] = None


class PydanticGraph(BaseModel):
    nodes: Dict[str, Node] = Field(default_factory=dict)
    edges: List[Edge] = Field(default_factory=list)

    @classmethod
    def from_codebase(cls, codebase: CodeBase) -> 'PydanticGraph':
        """
        Build the dependency graph from a codebase object.
        
        Args:
            codebase: A codebase object with elements collection containing code elements
            
        Returns:
            The updated PydanticGraph instance
            
        Raises:
            AttributeError: If the codebase doesn't have the expected structure
        """
        try:
            graph = cls()
            # Add all elements as nodes
            for element_id, element in codebase.elements.root.items():
                if hasattr(element, 'element_type'):
                    # Extract element attributes with sensible defaults
                    node_data = {
                        'name': getattr(element, 'name', ''),
                        'element_type': getattr(element, 'element_type', ''),
                        'language': getattr(element, 'language', ''),
                        'file_path': str(getattr(element, 'file_path', ''))
                    }
                    
                    # Add additional properties if present
                    for attr in ['line_start', 'line_end', 'col_start', 'col_end', 'doc_string']:
                        if hasattr(element, attr):
                            node_data[attr] = getattr(element, attr)
                    
                    # Add node with attributes
                    graph.add_node(element_id, data=node_data)
            
            # Add dependencies as edges
            for element_id, element in codebase.elements.root.items():
                if hasattr(element, 'dependencies'):
                    for dep_type, target_ids in element.dependencies.items():
                        # Handle different dependency formats (list or dict)
                        if isinstance(target_ids, list):
                            targets = target_ids
                        elif isinstance(target_ids, dict):
                            targets = list(target_ids.keys())
                        else:
                            targets = [target_ids]
                        
                        for target_id in targets:
                            if target_id in codebase.elements.root:
                                graph.add_edge(
                                    element_id, 
                                    target_id, 
                                    data={'dep_type': dep_type}
                                )
            
            return graph
        
        except (AttributeError, TypeError) as e:
            raise AttributeError(f"Error building graph from codebase: {e}")

    def add_node(self, node_id: str, data: Optional[dict] = None):
        """
        Add a node to the graph.
        
        Args:
            node_id: ID of the node
            data: Optional dictionary of node attributes
        """
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(id=node_id, data=data)

    def add_edge(self, source: str, target: str, data: Optional[dict] = None):
        """
        Add an edge to the graph.
        
        Args:
            source: ID of the source node
            target: ID of the target node
            data: Optional dictionary of edge attributes
        """
        self.add_node(source)
        self.add_node(target)
        self.edges.append(Edge(source=source, target=target, data=data))

    def delete_edges_from_node(self, node_id: str):
        """
        Deletes all edges that start from a specific node.
        
        Args:
            node_id (str): The ID of the node whose outgoing edges should be removed.
        """
        # Filter edges, keeping only those that do not originate from the specified node
        self.edges = [edge for edge in self.edges if edge.source != node_id]

    def get_neighbors(self, node_id: str, degrees: int = 1) -> List[str]:
        """
        Retrieve neighbors of a node up to a specified number of degrees.
        
        Args:
            node_id (str): The ID of the starting node
            degrees (int, optional): Number of degrees of separation to include. Defaults to 1.
        
        Returns:
            List[str]: List of neighbor node IDs
        """
        # Validate input
        if degrees < 1:
            raise ValueError("Degrees must be a positive integer")
        
        # Set to keep track of visited nodes and prevent duplicates
        visited_nodes = set()        
        # Initial set of nodes to explore
        current_degree_nodes = {node_id}        
        # Iterate through specified degrees
        for _ in range(degrees):
            # Set to collect nodes for the next degree
            next_degree_nodes = set()            
            # Explore neighbors for current degree nodes
            for current_node in current_degree_nodes:
                # Find direct neighbors
                neighbors = [
                    edge.target for edge in self.edges 
                    if edge.source == current_node and edge.target not in visited_nodes
                ]                
                # Add new neighbors to next degree and mark as visited
                for neighbor in neighbors:
                    next_degree_nodes.add(neighbor)
                    visited_nodes.add(neighbor)            
            # Update current degree nodes for next iteration
            current_degree_nodes = next_degree_nodes            
            # Break if no new neighbors found
            if not current_degree_nodes:
                break        
        # Remove the original node from the result
        visited_nodes.discard(node_id)

        return list(visited_nodes)

    def get_elements_by_type(self, element_type: str) -> List[str]:
        """
        Get all elements of a specific type.
        
        Args:
            element_type: Type of elements to retrieve
            
        Returns:
            List of element IDs of the specified type
        """
        return [
            node_id for node_id, node in self.nodes.items()
            if node.data and node.data.get('element_type') == element_type
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
        
        if element_id in self.nodes:
            for edge in self.edges:
                if edge.source == element_id:
                    dep_type = edge.data.get('dep_type', 'unknown') if edge.data else 'unknown'
                    if dep_type not in dependencies:
                        dependencies[dep_type] = []
                    dependencies[dep_type].append(edge.target)
        
        return dependencies
    
    def get_dependents(self, element_id: str) -> List[str]:
        """
        Get all elements that depend on the specified element.
        
        Args:
            element_id: ID of the element
            
        Returns:
            List of element IDs that depend on the specified element
        """
        return [edge.source for edge in self.edges if edge.target == element_id]
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Find circular dependencies in the graph.
        
        Returns:
            List of cycles, where each cycle is a list of element IDs
        """
        # Convert to NetworkX DiGraph for cycle detection
        nx_graph = self.to_networkx()
        
        try:
            return list(nx.simple_cycles(nx_graph))
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
        nx_graph = self.to_networkx()
        
        try:
            return nx.shortest_path(nx_graph, start_id, end_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def find_strongly_connected_components(self) -> List[Set[str]]:
        """
        Find strongly connected components in the graph.
        
        Returns:
            List of sets, where each set contains element IDs in a strongly connected component
        """
        nx_graph = self.to_networkx()
        return list(nx.strongly_connected_components(nx_graph))
    
    def get_element_centrality(self, centrality_type: str = 'degree') -> Dict[str, float]:
        """
        Calculate centrality measures for elements in the graph.
        
        Args:
            centrality_type: Type of centrality to calculate ('degree', 'betweenness', 'eigenvector')
            
        Returns:
            Dictionary mapping element IDs to centrality values
        """
        nx_graph = self.to_networkx()
        
        if centrality_type == 'degree':
            return dict(nx.degree_centrality(nx_graph))
        elif centrality_type == 'betweenness':
            return dict(nx.betweenness_centrality(nx_graph))
        elif centrality_type == 'eigenvector':
            return dict(nx.eigenvector_centrality(nx_graph, max_iter=1000))
        else:
            raise ValueError(f"Unsupported centrality type: {centrality_type}")
    
    def get_dependency_subgraph(self, element_ids: List[str]) -> 'PydanticGraph':
        """
        Get a subgraph containing only the specified elements and their dependencies.
        
        Args:
            element_ids: List of element IDs to include in the subgraph
            
        Returns:
            New PydanticGraph object containing the subgraph
        """
        subgraph = PydanticGraph()
        
        # Add specified nodes
        for element_id in element_ids:
            if element_id in self.nodes:
                node = self.nodes[element_id]
                subgraph.add_node(element_id, data=node.data)
        
        # Add edges between specified nodes
        for edge in self.edges:
            if edge.source in element_ids and edge.target in element_ids:
                subgraph.add_edge(edge.source, edge.target, data=edge.data)
        
        return subgraph
    
    def to_networkx(self) -> nx.DiGraph:
        """
        Convert the PydanticGraph to a NetworkX DiGraph.
        
        Returns:
            NetworkX DiGraph representation of this graph
        """
        graph = nx.DiGraph()
        
        # Add nodes
        for node_id, node in self.nodes.items():
            if not node_id.startswith("import"):
                graph.add_node(node_id, **(node.data or {}))
        
        # Add edges
        for edge in self.edges:
            graph.add_edge(edge.source, edge.target, **(edge.data or {}))
        
        return graph
    
    @property
    def as_dict(self) -> dict:
        """
        Get dictionary representation of the graph.
        
        Returns:
            Dictionary with nodes and edges
        """
        return {
            "nodes": {node_id: node.model_dump() for node_id, node in self.nodes.items()},
            "edges": [edge.model_dump() for edge in self.edges],
        }
    
    def to_json(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Export the dependency graph to JSON format.
        
        Args:
            output_path: Path to save the JSON file (if None, only returns the dict)
            
        Returns:
            Dictionary representation of the graph
        """
        nodes = []
        for node_id, node in self.nodes.items():
            node_data = {
                'id': node_id,
                **(node.data or {})
            }
            nodes.append(node_data)
        
        edges = []
        for edge in self.edges:
            edge_data = {
                'source': edge.source,
                'target': edge.target,
                'type': edge.data.get('dep_type', 'unknown') if edge.data else 'unknown'
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

    @classmethod
    def deserialize(cls,
            serialization_dir: Union[Path, str]=SERIALIZATION_DIR, 
            graph_filename: str=SERIALIZED_GRAPH)->"PydanticGraph":        
        serialization_dir = Path(serialization_dir)
        if not os.path.isdir(serialization_dir):
            raise FileNotFoundError(f"{serialization_dir=} is not a valid directory")
        if not os.path.exists(serialization_dir / graph_filename):
            raise FileNotFoundError(f"{serialization_dir / graph_filename=} does not exist")
        graph = json.loads(readFile(serialization_dir / graph_filename))
        return cls(**graph)
    
    def serialize(self, 
            serialization_dir: Union[Path, str]=SERIALIZATION_DIR, 
            graph_filename: str=SERIALIZED_GRAPH):
        serialization_dir = Path(serialization_dir)
        os.makedirs(serialization_dir, exist_ok=True)
        writeFile(self.model_dump_json(indent=4), serialization_dir / graph_filename)

    def visualize(self):
        """
        Visualize the graph using Plotly and NetworkX.
        
        Requires plotly and networkx to be installed.
        
        Raises:
            ImportError: If plotly or networkx are not installed
        """
        try:
            import plotly.graph_objects as go
            import networkx as nx
        except ImportError:
            raise ImportError(
                "Plotly, NetworkX and Numpy are required for visualization. Please install using 'pip install codetide[visualization]' or 'pip install plotly networkx numpy'"
            )
        
        # Create a NetworkX graph from the PydanticGraph
        graph = self.to_networkx()
        
        # Compute node positions using spring layout
        pos = nx.spring_layout(graph, seed=42)        
        # Create edge traces
        edge_trace = []
        for edge in graph.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace.append(go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                line=dict(width=1, color='#888'),
                hoverinfo='none',
                mode='lines'))
        
        # Prepare node data
        x_list = []
        y_list = []
        text_list = []
        hover_text_list = []
        marker_color_list = []
                
        for node in graph.nodes():
            x, y = pos[node]
            x_list.append(x)
            y_list.append(y)
            
            # Use the node name for display instead of ID
            node_name = self.nodes[node].data.get("name", node) if node in self.nodes else node
            text_list.append(node_name)
            
            # Create detailed hover text that includes both name and ID
            hover_text = f"Name: {node_name}<br>ID: {node}"
            if node in self.nodes and self.nodes[node].data:
                node_type = self.nodes[node].data.get("type", "")
                file_path = self.nodes[node].data.get("file_path", "")
                if node_type:
                    hover_text += f"<br>Type: {node_type}"
                if file_path:
                    hover_text += f"<br>File: {file_path}"
            
            hover_text_list.append(hover_text)
            marker_color_list.append(len(list(graph.neighbors(node))))
        
        # Create node trace
        node_trace = go.Scatter(
            x=x_list,
            y=y_list,
            text=text_list,
            hovertext=hover_text_list,
            mode='markers+text',
            textposition='bottom center',
            hoverinfo='text',
            marker=dict(
                showscale=True,
                colorscale='YlGnBu',
                color=marker_color_list,
                size=10,
                colorbar=dict(
                    thickness=15,
                    title='Node Connections',
                    xanchor='left',
                    titleside='right'
                )
            )
        )
        
        # Create the figure
        fig = go.Figure(data=edge_trace + [node_trace],
                        layout=go.Layout(
                            title='<br>Graph Visualization',
                            titlefont=dict(size=16),
                            showlegend=False,
                            hovermode='closest',
                            margin=dict(b=20, l=5, r=5, t=40),
                            annotations=[dict(
                                text="Network graph visualization",
                                showarrow=False,
                                xref="paper", yref="paper",
                                x=0.005, y=-0.002)],
                            xaxis=dict(showgrid=False, zeroline=False),
                            yaxis=dict(showgrid=False, zeroline=False))
                        )
        
        # Show the figure
        fig.show()


if __name__ == "__main__":
    # Example usage
    def main():
        graph = PydanticGraph()
        # Add nodes with element type information
        graph.add_node("A", data={"element_type": "module", "name": "Module A", "language": "python"})
        graph.add_node("B", data={"element_type": "function", "name": "Function B", "language": "python"})
        graph.add_node("C", data={"element_type": "class", "name": "Class C", "language": "python"})
        graph.add_node("D", data={"element_type": "file", "name": "File D", "language": "python"})

        # Add edges with dependency information
        graph.add_edge("A", "B", data={"dep_type": "calls"})
        graph.add_edge("B", "C", data={"dep_type": "contains"})
        graph.add_edge("A", "C", data={"dep_type": "uses"})
        graph.add_edge("C", "D", data={"dep_type": "imports"})
        
        # Add a cycle to demonstrate circular dependency detection
        graph.add_edge("D", "A", data={"dep_type": "requires"})
        
        # Get neighbors with different degrees of separation
        print("Neighbors of A (1 degree):", graph.get_neighbors("A", degrees=1))
        print("Neighbors of A (2 degrees):", graph.get_neighbors("A", degrees=2))
        
        # Test dependency analysis functions
        print("\nElements by type 'function':", graph.get_elements_by_type("function"))
        print("Direct dependencies of A:", graph.get_direct_dependencies("A"))
        print("Dependents of C:", graph.get_dependents("C"))
        print("Circular dependencies:", graph.find_circular_dependencies())
        print("Dependency chain from D to C:", graph.get_dependency_chain("D", "C"))
        print("Strongly connected components:", graph.find_strongly_connected_components())
        print("Element centrality (degree):", graph.get_element_centrality())
        
        # Export to JSON
        json_data = graph.to_json()
        print("\nJSON representation:", json.dumps(json_data, indent=2))
        
        # Visualize the graph
        graph.visualize()

    main()