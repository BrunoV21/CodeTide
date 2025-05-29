def render_html_view(codebase, include_modules: bool = True, include_types: bool = True) -> str:
    tree = codebase._build_tree_dict()
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<title>Codebase Block View</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: var(--bg); color: var(--text); transition: background 0.3s, color 0.3s; }",
        ":root {",
        "  --bg: #ffffff;",
        "  --text: #000000;",
        "}",
        ".dark {",
        "  --bg: #121212;",
        "  --text: #eeeeee;",
        "}",
        ".toolbar { margin-bottom: 20px; }",
        ".grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }",
        ".block { aspect-ratio: 1 / 1; display: flex; flex-direction: column; justify-content: center; align-items: center;",
        "         border-radius: 10px; color: white; font-size: 1.2em; font-weight: bold; cursor: pointer; position: relative; }",
        ".file { background-color: #008080; }",
        ".directory { background-color: #0055cc; }",
        ".class { background-color: #e67e22; }",
        ".function { background-color: #8e44ad; }",
        ".variable { background-color: #27ae60; }",
        ".attribute { background-color: #f1c40f; }",
        ".method { background-color: #c0392b; }",
        ".hidden { display: none; }",
        ".close-btn { position: absolute; top: 10px; right: 10px; font-size: 20px; cursor: pointer; }",
        ".dark-toggle { padding: 8px 14px; border: none; background: #444; color: white; border-radius: 5px; cursor: pointer; }",
        "</style>",
        "<script>",
        "function toggleView(showId, hideClass) {",
        "  document.querySelectorAll('.' + hideClass).forEach(el => el.classList.add('hidden'));",
        "  document.getElementById(showId).classList.remove('hidden');",
        "}",
        "function closeView(id, parentClass) {",
        "  document.getElementById(id).classList.add('hidden');",
        "  document.querySelectorAll('.' + parentClass).forEach(el => el.classList.remove('hidden'));",
        "}",
        "function toggleDarkMode() {",
        "  document.body.classList.toggle('dark');",
        "  localStorage.setItem('darkMode', document.body.classList.contains('dark') ? 'true' : 'false');",
        "}",
        "window.onload = function() {",
        "  if (localStorage.getItem('darkMode') === 'true') {",
        "    document.body.classList.add('dark');",
        "  }",
        "}",
        "</script>",
        "</head>",
        "<body>",
        "<div class='toolbar'>",
        "<button class='dark-toggle' onclick='toggleDarkMode()'>Toggle Dark Mode</button>",
        "</div>",
        "<div class='grid root-grid'>"
    ]

    id_counter = [0]

    def next_id():
        id_counter[0] += 1
        return f"block_{id_counter[0]}"

    def block_div(name, label, cls, onclick=None, block_id=None):
        div = f"<div class='block {cls}'"
        if onclick:
            div += f" onclick=\"{onclick}\""
        if block_id:
            div += f" id='{block_id}'"
        div += f">{label}<br>{name}</div>"
        return div

    def _render_node(node, container_class, parent_id=None):
        nonlocal html_lines # noqa: F824
        items = [(k, v) for k, v in node.items() if not k.startswith("_")]
        items.sort(key=lambda x: (x[1].get("_type") != "directory", x[0]))

        html_lines.append(f"<div class='grid {container_class}'>")
        for name, data in items:
            block_id = next_id()  # <- Single ID for both the block and its content
            label = "📁" if data["_type"] == "directory" else "📄"
            cls = data["_type"]
            onclick = f"toggleView('{block_id}_content', '{container_class}')"
            html_lines.append(block_div(name, label, cls, onclick=onclick))
            
            # Hidden container for clicked block
            html_lines.append(f"<div id='{block_id}_content' class='hidden'>")
            html_lines.append(f"<div class='close-btn' onclick=\"closeView('{block_id}_content', '{container_class}')\">×</div>")
            html_lines.append("<div class='grid'>")
            if data["_type"] == "directory":
                _render_node(data, f"{block_id}_content", parent_id=block_id)
            elif data["_type"] == "file" and include_modules:
                _render_file_contents(data["_data"], f"{block_id}_content", container_class)
            html_lines.append("</div></div>")
        html_lines.append("</div>")

    def _render_file_contents(code_file, container_id, parent_class):
        nonlocal html_lines # noqa: F824

        def block(label, name, cls):
            return f"<div class='block {cls}'>{label}<br>{name}</div>"

        html_lines.append("<div class='grid'>")

        for var in code_file.variables:
            html_lines.append(block("V", var.name, "variable"))

        for func in code_file.functions:
            html_lines.append(block("ƒ", func.name, "function"))

        for cls in code_file.classes:
            class_id = next_id()
            html_lines.append(f"<div class='block class' onclick=\"toggleView('{class_id}_content', '{container_id}')\">C<br>{cls.name}</div>")

            html_lines.append(f"<div id='{class_id}_content' class='hidden'>")
            html_lines.append(f"<div class='close-btn' onclick=\"closeView('{class_id}_content', '{container_id}')\">×</div>")
            html_lines.append("<div class='grid'>")
            for attr in cls.attributes:
                html_lines.append(block("A", attr.name, "attribute"))
            for method in cls.methods:
                html_lines.append(block("M", method.name, "method"))
            html_lines.append("</div></div>")

        html_lines.append("</div>")

    _render_node(tree, "root-grid")

    html_lines.extend([
        "</body>",
        "</html>"
    ])
    return "\n".join(html_lines)
