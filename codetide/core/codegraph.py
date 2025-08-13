from .models import CodeBase

# --- CodeBaseGraph: Project Structure Graph Representation ---
class CodeBaseGraph:
    """
    Represents a graph of the codebase, with nodes for classes, functions, and files,
    and edges for inheritance, usage, and import relationships.

    Example usage:
        codebase = ...  # Assume you have a CodeBase object
        graph = CodeBaseGraph(codebase)
        mermaid_diagram = graph.to_mermaid()
        print(mermaid_diagram)
    """
    def __init__(self, codebase :CodeBase):
        self.codebase = codebase
        self.nodes = {}  # key: unique_id, value: element (class/function/file)
        self.edges = {
            "inheritance": set(),  # (child_unique_id, parent_unique_id)
            "usage": set(),        # (from_unique_id, to_unique_id)
            "import": set(),       # (from_file_unique_id, to_file_unique_id)
        }
        self._build_graph()

    def _build_graph(self):
        # Build nodes for all classes, functions, and files
        for code_file in self.codebase.root:
            file_uid = code_file.file_path
            self.nodes[file_uid] = code_file
            # Classes
            for class_def in code_file.classes:
                self.nodes[class_def.unique_id] = class_def
                # Inheritance edges
                for base_ref in getattr(class_def, "bases_references", []):
                    if base_ref.unique_id:
                        self.edges["inheritance"].add((class_def.unique_id, base_ref.unique_id))
                # Usage edges (attributes and methods)
                for ref in getattr(class_def, "references", []):
                    if ref.unique_id:
                        self.edges["usage"].add((class_def.unique_id, ref.unique_id))
            # Functions
            for func_def in code_file.functions:
                self.nodes[func_def.unique_id] = func_def
                for ref in getattr(func_def, "references", []):
                    if ref.unique_id:
                        self.edges["usage"].add((func_def.unique_id, ref.unique_id))
            # Imports (file-level)
            for import_stmt in code_file.imports:
                if import_stmt.source:
                    self.edges["import"].add((file_uid, import_stmt.source))

    def to_mermaid(self):
        """
        Render the graph as a Mermaid class diagram.
        Includes class definitions, inheritance, and usage relationships.
        """
        lines = ["classDiagram"]
        # Add class nodes
        for node_id, node in self.nodes.items():
            if hasattr(node, "name") and hasattr(node, "attributes") and hasattr(node, "methods"):
                class_name = node.name
                attr_lines = []
                for attr in getattr(node, "attributes", []):
                    attr_lines.append(f"  +{attr.name}")
                for method in getattr(node, "methods", []):
                    attr_lines.append(f"  +{method.name}()")
                if attr_lines:
                    lines.append(f"class {class_name} {{")
                    lines.extend(attr_lines)
                    lines.append("}")
                else:
                    lines.append(f"class {class_name}")
        # Add inheritance edges
        for from_id, to_id in self.edges["inheritance"]:
            from_node = self.nodes.get(from_id)
            to_node = self.nodes.get(to_id)
            if from_node and to_node and hasattr(from_node, "name") and hasattr(to_node, "name"):
                lines.append(f"{from_node.name} <|-- {to_node.name}")
        # Add usage edges
        for from_id, to_id in self.edges["usage"]:
            from_node = self.nodes.get(from_id)
            to_node = self.nodes.get(to_id)
            if from_node and to_node and hasattr(from_node, "name") and hasattr(to_node, "name"):
                lines.append(f"{from_node.name} ..> {to_node.name}")
        return "\n".join(lines)