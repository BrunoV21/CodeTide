from .models import CodeBase
import ulid

def to_mermaid_boxy_flowchart(codebase: CodeBase, include_modules: bool = False, include_types: bool = False) -> str:
    tree_dict = codebase._build_tree_dict()
    lines = ["flowchart TB"]
    _render_mermaid_node(tree_dict, lines, indent=1, include_modules=include_modules, include_types=include_types)
    return "\n".join(lines)


def _render_mermaid_node(node: dict, lines: list, indent: int, include_modules: bool, include_types: bool):
    indent_str = "    " * indent
    items = [(k, v) for k, v in node.items() if not k.startswith("_")]
    items.sort(key=lambda x: (x[1].get("_type", "directory") == "file", x[0]))

    for name, data in items:
        node_id = _safe_mermaid_id(name)
        if data.get("_type") == "file":
            code_file = data["_data"]
            lines.append(f'{indent_str}subgraph {node_id}["{name}"]')
            if include_modules:
                _render_file_contents(code_file, lines, indent + 1, include_types)
            lines.append(f'{indent_str}end')
        elif data.get("_type") == "directory":
            lines.append(f'{indent_str}subgraph {node_id}["{name}/"]')
            _render_mermaid_node(data, lines, indent + 1, include_modules, include_types)
            lines.append(f'{indent_str}end')


def _render_file_contents(code_file, lines: list, indent: int, include_types: bool):
    indent_str = "    " * indent

    # Add variables
    for variable in code_file.variables:
        label = variable.name
        style = "fill:#FFFBCC"
        node_id = _safe_mermaid_id(f"var_{code_file.file_path}_{label}")
        lines.append(f'{indent_str}{node_id}["{label}"]')
        lines.append(f'style {node_id} {style}')

    # Add functions
    for function in code_file.functions:
        label = function.name
        style = "fill:#D6EFFF"
        node_id = _safe_mermaid_id(f"func_{code_file.file_path}_{label}")
        lines.append(f'{indent_str}{node_id}["{label}()"]')
        lines.append(f'style {node_id} {style}')

    # Add classes and their contents
    for class_def in code_file.classes:
        class_label = class_def.name
        class_node_id = _safe_mermaid_id(f"class_{code_file.file_path}_{class_label}")
        lines.append(f'{indent_str}subgraph {class_node_id}["{class_label}"]')
        _render_class_contents(class_def, lines, indent + 1)
        lines.append(f'{indent_str}end')


def _render_class_contents(class_def, lines: list, indent: int):
    indent_str = "    " * indent

    for attr in class_def.attributes:
        label = attr.name
        node_id = _safe_mermaid_id(f"attr_{class_def.name}_{label}")
        lines.append(f'{indent_str}{node_id}["{label}"]')
        lines.append(f'style {node_id} fill:#E8F5E9')

    for method in class_def.methods:
        label = method.name
        node_id = _safe_mermaid_id(f"method_{class_def.name}_{label}")
        lines.append(f'{indent_str}{node_id}["{label}()"]')
        lines.append(f'style {node_id} fill:#F3E5F5')


def _safe_mermaid_id(label: str) -> str:
    return ulid.ulid() + label.replace(" ", "_").replace("-", "_").replace(".", "_").replace("/", "_").replace("\\", "_")


def save_mermaid_to_html_file(mermaid_code: str, output_path: str = "diagram.html", title: str = "CodeBase Diagram"):
    """
    Save a Mermaid diagram as a standalone HTML file.

    Args:
        mermaid_code (str): The Mermaid code to embed.
        output_path (str): Path to save the HTML file.
        title (str): Optional title for the page.
    """
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, maxTextSize: 90000}});
    </script>
    <style>
        body {{
            font-family: sans-serif;
            padding: 2rem;
        }}
        .mermaid {{
            background: white;
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 1rem;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="mermaid">
{mermaid_code}
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Mermaid diagram saved to: {output_path}")
