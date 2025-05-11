"""
Example script for analyzing a Python project using the CodeTide library.
"""
import sys
import os
from pathlib import Path
import argparse
import json
import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, List, Optional

# Add the root directory to sys.path if needed
# This might be needed if the codetide package isn't installed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codetide.core.pydantic_graph import PydanticGraph
from codetide.tide import CodeTide
from codetide.core.graph import DependencyGraph

def visualize_graph(graph: DependencyGraph, element_type: Optional[str] = None):
    """
    Visualize the dependency graph.
    
    Args:
        graph: DependencyGraph object
        element_type: Optional filter by element type
    """
    # Create a NetworkX graph for visualization
    G = nx.DiGraph()
    
    # Add nodes with different colors based on element type
    color_map = {
        "class": "lightblue",
        "function": "lightgreen",
        "import": "orange",
        "variable": "pink"
    }
    
    # Filter nodes if element_type is specified
    if element_type:
        nodes = graph.get_elements_by_type(element_type)
    else:
        nodes = list(graph.graph.nodes())
    
    # Add nodes
    for node_id in nodes:
        attrs = graph.graph.nodes[node_id]
        node_type = attrs.get('element_type', 'unknown')
        node_color = color_map.get(node_type, 'gray')
        G.add_node(node_id, color=node_color, label=attrs.get('name', node_id))
    
    # Add edges between the filtered nodes
    for source, target in graph.graph.edges():
        if source in nodes and target in nodes:
            G.add_edge(source, target)
    
    # Get positions for nodes
    pos = nx.spring_layout(G, seed=42)
    
    # Get node colors
    node_colors = [G.nodes[node].get('color', 'gray') for node in G.nodes()]
    
    # Draw the graph
    plt.figure(figsize=(12, 8))
    nx.draw(G, pos, with_labels=False, node_color=node_colors, node_size=300, alpha=0.8)
    
    # Add labels with smaller font size
    nx.draw_networkx_labels(G, pos, labels={n: G.nodes[n].get('label', n) for n in G.nodes()}, font_size=8)
    
    plt.title("Project Dependency Graph")
    plt.axis('off')
    plt.tight_layout()
    plt.show()

def main():
    """Main function to analyze a Python project."""
    project_path = Path("C:/Users/GL504GS/Desktop/repos/AiCore/aicore/")
    
    if not project_path.exists() or not project_path.is_dir():
        print(f"Error: {project_path} is not a valid directory")
        return 1
    
    print(f"Analyzing project: {project_path}")
    
    # Parse the project
    project_parser = CodeTide(project_path, languages=["python"])
    codebase = project_parser.parse_project()
    
    # Build the dependency graph
    # graph = DependencyGraph(codebase)
    
    graph = PydanticGraph.from_codebase(codebase)
    
    # Print basic stats
    print("\nProject Statistics:")
    print(f"  Number of files: {len(codebase.files)}")
    print(f"  Number of elements: {len(codebase.elements.root)}")
    
    element_types = {}
    for element_id, element in codebase.elements.root.items():
        if hasattr(element, 'element_type'):
            element_type = element.element_type
            element_types[element_type] = element_types.get(element_type, 0) + 1
    
    print("\nElement Types:")
    for element_type, count in element_types.items():
        print(f"  {element_type}: {count}")
    
    # Find circular dependencies
    circular_deps = graph.find_circular_dependencies()
    if circular_deps:
        print("\nCircular Dependencies:")
        for i, cycle in enumerate(circular_deps):
            print(f"  Cycle {i+1}: {' -> '.join(cycle + [cycle[0]])}")
    else:
        print("\nNo circular dependencies found!")

    output_path = "./output.json"
    print(f"\nExporting dependency graph to {output_path}")
    graph.to_json(output_path)
    
    graph.visualize()
    # visualize_graph(graph)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())