<!-- [![Docs](https://img.shields.io/badge/docs-CodeTide.github.io-red)](https://brunov21.github.io/CodeTide/) -->
# <img src="./docs/assets/codetide-logo.png" alt="code-tide-logo" width="35" height="auto"/> CodeTide
[![GitHub Stars](https://img.shields.io/github/stars/BrunoV21/CodeTide?style=social)](https://github.com/BrunoV21/CodeTide/stargazers)
[![PyPI Downloads](https://static.pepy.tech/badge/CodeTide)](https://pepy.tech/projects/CodeTide)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/CodeTide?style=flat)
![PyPI - Version](https://img.shields.io/pypi/v/CodeTide?style=flat)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)
--- 

**CodeTide** is a fully local, privacy-preserving tool for parsing and understanding Python codebases using symbolic, structural analysis. No internet, no LLMs, no embeddings - just fast, explainable, and deterministic code intelligence.

---

## ✅ Key Features

- ✅ 100% **local & private** - all parsing and querying happens on your machine.
- 📦 Structured parsing of codebases using [Tree-sitter](https://tree-sitter.github.io/tree-sitter/).
- 🧠 Retrieval of relevant code snippets by symbolic ID - not vector similarity.
- 🧱 Visualize the architecture and hierarchy of your project.
- ⚡ Fast, cacheable parsing with smart update detection.
- 🔁 Designed to work alongside tools like Copilot, GPT, and Claude - on your terms.

---

## 🔌 VSCode Extension

CodeTide is available as a native [**Visual Studio Code extension**](https://marketplace.visualstudio.com/items?itemName=BrunoV21.codetide), giving you direct access to structural code understanding inside your editor.

- Navigate code intelligently
- Retrieve context-aware snippets
- Send context directly to LLMs like Copilot or GPT
- Works seamlessly with any other extensions

🔗 **Install it now**: [CodeTide on VSCode Marketplace](https://marketplace.visualstudio.com/items?itemName=BrunoV21.codetide)  
🔧 **Extension source code**: [CodeTide VSCode Extension on GitHub](https://github.com/BrunoV21/CodeTide-vsExtension/tree/main)

---

## ⚙️ Installation

### 📦 From PyPI

```bash
pip install codetide --upgrade
````

### 🛠️ From Source

```bash
git clone https://github.com/BrunoV21/CodeTide.git
cd CodeTide
pip install -e .
```

---

## 🚀 Example: Running CodeTide on Itself

Here's how to parse the CodeTide repository and extract a snippet from the Python parser:

```python
from codetide import CodeTide
from codetide.core.common import writeFile
from dotenv import load_dotenv
import asyncio
import time
import os

async def main():
    st = time.time()
    tide = await CodeTide.from_path(os.getenv("CODETIDE_REPO_PATH"))
    tide.serialize(include_cached_ids=True)
    output = tide.get(["codetide.parsers.python_parser.PythonParser"], degree=1, as_string=True)

    writeFile(output, "./storage/context.txt")
    print(f"took {time.time()-st:.2f}s")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
```

This example:

* Parses the codebase using Tree-sitter
* Serializes the result for fast reuse
* Retrieves a specific class with full local context

---

Here's how to deserialize a CodeTide repository and reuse it:

```python
from codetide import CodeTide
from codetide.core.common import writeFile
from dotenv import load_dotenv
import asyncio
import time
import os

async def main():
    st = time.time()
    tide = CodeTide.deserialize(rootpath=os.getenv("CODETIDE_REPO_PATH"))
    tide.codebase._build_cached_elements()
    await tide.check_for_updates(include_cached_ids=True)
    output = tide.get(["codetide.parsers.python_parser.PythonParser"], degree=2, as_string=True)

    writeFile(output, "./storage/context.txt")
    print(f"took {time.time()-st:.2f}s")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
```

This example:

* Deserializes the previously serialized CodeTide
* Checks for updates to the codebase
* Retrieves a specific class with full local context (up to second degree connections)
---

Here's how to levarage CodeTide's tree view functionalites to get a broad picture of your project:

```python
from codetide import CodeTide
from dotenv import load_dotenv
import time
import os

def main():
    st = time.time()
    tide = CodeTide.deserialize(rootpath=os.getenv("CODETIDE_REPO_PATH"))

    modules_tree_view = tide.codebase.get_tree_view(include_modules=True)
    print(modules_tree_view)
    
    print(f"took {time.time()-st:.2f}s")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
```

<details>
<summary>Output:</summary>

```bash
├── codetide
│   ├── core
│   │   ├── common.py
│   │   │   ├── CONTEXT_INTRUCTION
│   │   │   ├── TARGET_INSTRUCTION
│   │   │   ├── readFile
│   │   │   ├── wrap_content
│   │   │   ├── wrap_package_dependencies   
│   │   │   └── writeFile
│   │   ├── defaults.py
│   │   │   ├── DEFAULT_BATCH_SIZE
│   │   │   ├── DEFAULT_CACHED_ELEMENTS_FILE
│   │   │   ├── DEFAULT_CACHED_IDS_FILE     
│   │   │   ├── DEFAULT_ENCODING
│   │   │   ├── DEFAULT_MAX_CONCURRENT_TASKS
│   │   │   ├── DEFAULT_SERIALIZATION_PATH
│   │   │   ├── INSTALLATION_DIR
│   │   │   └── LANGUAGE_EXTENSIONS
│   │   ├── html.py
│   │   │   └── render_html_view
│   │   ├── mermaid.py
│   │   │   ├── _render_class_contents
│   │   │   ├── _render_file_contents
│   │   │   ├── _render_mermaid_node
│   │   │   ├── _safe_mermaid_id
│   │   │   ├── save_mermaid_to_html_file
│   │   │   └── to_mermaid_boxy_flowchart
│   │   └── models.py
│   │       ├── BaseCodeElement
│   │       │   ├── file_path
│   │       │   ├── raw
│   │       │   ├── stored_unique_id
│   │       │   ├── apply_second_line_indent_to_first
│   │       │   ├── file_path_without_suffix
│   │       │   ├── unique_id
│   │       │   └── unique_id
│   │       ├── ClassAttribute
│   │       │   ├── class_id
│   │       │   └── visibility
│   │       ├── ClassDefinition
│   │       │   ├── attributes
│   │       │   ├── bases
│   │       │   ├── bases_references
│   │       │   ├── methods
│   │       │   ├── name
│   │       │   ├── add_attribute
│   │       │   ├── add_method
│   │       │   ├── all_methods_ids
│   │       │   └── references
│   │       ├── CodeBase
│   │       │   ├── _cached_elements
│   │       │   ├── root
│   │       │   ├── _build_cached_elements
│   │       │   ├── _build_tree_dict
│   │       │   ├── _list_all_unique_ids_for_property
│   │       │   ├── _render_class_contents
│   │       │   ├── _render_file_contents
│   │       │   ├── _render_tree_node
│   │       │   ├── all_classes
│   │       │   ├── all_functions
│   │       │   ├── all_imports
│   │       │   ├── all_variables
│   │       │   ├── deserialize_cache_elements
│   │       │   ├── get
│   │       │   ├── get_import
│   │       │   ├── get_tree_view
│   │       │   ├── serialize_cache_elements
│   │       │   └── unique_ids
│   │       ├── CodeContextStructure
│   │       │   ├── _cached_elements
│   │       │   ├── _unique_class_elements_ids
│   │       │   ├── class_attributes
│   │       │   ├── class_methods
│   │       │   ├── classes
│   │       │   ├── functions
│   │       │   ├── imports
│   │       │   ├── preloaded
│   │       │   ├── requested_elements
│   │       │   ├── variables
│   │       │   ├── add_class
│   │       │   ├── add_class_attribute
│   │       │   ├── add_class_method
│   │       │   ├── add_function
│   │       │   ├── add_import
│   │       │   ├── add_preloaded
│   │       │   ├── add_variable
│   │       │   ├── as_list_str
│   │       │   └── from_list_of_elements
│   │       ├── CodeFileModel
│   │       │   ├── classes
│   │       │   ├── file_path
│   │       │   ├── functions
│   │       │   ├── imports
│   │       │   ├── raw
│   │       │   ├── variables
│   │       │   ├── _list_all
│   │       │   ├── add_class
│   │       │   ├── add_function
│   │       │   ├── add_import
│   │       │   ├── add_variable
│   │       │   ├── all_classes
│   │       │   ├── all_functions
│   │       │   ├── all_imports
│   │       │   ├── all_variables
│   │       │   ├── get
│   │       │   ├── get_import
│   │       │   └── list_raw_contents
│   │       ├── CodeReference
│   │       │   ├── name
│   │       │   └── unique_id
│   │       ├── FunctionDefinition
│   │       │   ├── decorators
│   │       │   ├── modifiers
│   │       │   ├── name
│   │       │   ├── references
│   │       │   └── signature
│   │       ├── FunctionSignature
│   │       │   ├── parameters
│   │       │   └── return_type
│   │       ├── ImportStatement
│   │       │   ├── alias
│   │       │   ├── definition_id
│   │       │   ├── import_type
│   │       │   ├── name
│   │       │   ├── raw
│   │       │   ├── source
│   │       │   └── as_dependency
│   │       ├── MethodDefinition
│   │       │   └── class_id
│   │       ├── Parameter
│   │       │   ├── default_value
│   │       │   ├── name
│   │       │   ├── type_hint
│   │       │   └── is_optional
│   │       ├── PartialClasses
│   │       │   ├── attributes
│   │       │   ├── class_header
│   │       │   ├── class_id
│   │       │   ├── filepath
│   │       │   ├── methods
│   │       │   └── raw
│   │       └── VariableDeclaration
│   │           ├── modifiers
│   │           ├── name
│   │           ├── raw
│   │           ├── references
│   │           ├── type_hint
│   │           └── value
│   ├── parsers
│   │   ├── base_parser.py
│   │   │   └── BaseParser
│   │   │       ├── extension
│   │   │       ├── import_statement_template
│   │   │       ├── language
│   │   │       ├── parse_file
│   │   │       ├── resolve_inter_files_dependencies
│   │   │       ├── resolve_intra_file_dependencies
│   │   │       └── tree_parser
│   │   ├── generic_parser.py
│   │   │   └── GenericParser
│   │   │       ├── _filepath
│   │   │       ├── extension
│   │   │       ├── import_statement_template
│   │   │       ├── language
│   │   │       ├── parse_code
│   │   │       ├── parse_file
│   │   │       ├── resolve_inter_files_dependencies
│   │   │       ├── resolve_intra_file_dependencies
│   │   │       └── tree_parser
│   │   └── python_parser.py
│   │       └── PythonParser
│   │           ├── _filepath
│   │           ├── _tree_parser
│   │           ├── _default_unique_import_id
│   │           ├── _find_elements_references
│   │           ├── _find_references
│   │           ├── _generate_unique_import_id
│   │           ├── _get_content
│   │           ├── _get_element_count
│   │           ├── _process_aliased_import
│   │           ├── _process_assignment
│   │           ├── _process_block
│   │           ├── _process_class_node
│   │           ├── _process_decorated_definition
│   │           ├── _process_expression_statement
│   │           ├── _process_function_definition
│   │           ├── _process_import_node
│   │           ├── _process_node
│   │           ├── _process_parameters
│   │           ├── _process_type_parameter
│   │           ├── _skip_init_paths
│   │           ├── count_occurences_in_code
│   │           ├── extension
│   │           ├── filepath
│   │           ├── filepath
│   │           ├── import_statement_template
│   │           ├── init_tree_parser
│   │           ├── language
│   │           ├── parse_code
│   │           ├── parse_file
│   │           ├── resolve_inter_files_dependencies
│   │           ├── resolve_intra_file_dependencies
│   │           ├── tree_parser
│   │           └── tree_parser
│   └── autocomplete.py
│       └── AutoComplete
│           ├── __init__
│           ├── get_fuzzy_suggestions
│           └── get_suggestions
├── examples
│   ├── parse_codetide.py
│   │   └── main
│   └── parse_project.py
│       └── main
└── setup.py
    ├── here
    ├── long_description
    ├── requirements
    └── requirements_visualization
```
</details>

## ❌ What CodeTide *Does Not* Use

To be clear, CodeTide **does not rely on**:

* ❌ Large Language Models (LLMs)
* ❌ Embedding models or token similarity
* ❌ Vector databases or search indexes
* ❌ External APIs or cloud services

Instead, it uses:

* ✅ [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) for lightweight, fast, and accurate parsing
* ✅ Deterministic logic and symbolic references to navigate your codebase

---

## 🗺️ Roadmap

Here’s what’s next for CodeTide:

- 🧩 **Support more languages** already integrated with [Tree-sitter](https://tree-sitter.github.io/tree-sitter/)  
  → **TypeScript** is the top priority.
- 🧭 **Handle relative imports** in Python projects  
  → Improve resolution for intra-package navigation.
- 🤖 **Long-term vision**: Release a native **CodeTide Agent**  
  → Seamless, intelligent context resolution directly integrated into the CodeTide core.  
  → Unlock **clinical issue detection**, **guided refactors**, and **agent-level navigation**.

Stay tuned - or contribute to shape the tide. 🌊

---

## 📄 License

CodeTide is licensed under the **Apache 2.0 License**.

---

## 🧠 Philosophy

CodeTide is about giving developers structure-aware tools that are **fast, predictable, and private**. Your code is parsed, navigated, and queried as a symbolic graph - not treated as a black box of tokens. Whether you’re building, refactoring, or feeding context into an LLM - **you stay in control**.

> Like a tide, your codebase evolves - and CodeTide helps you move with it, intelligently.