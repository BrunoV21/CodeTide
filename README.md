<div align="center">

<!-- [![Docs](https://img.shields.io/badge/docs-CodeTide.github.io-red)](https://brunov21.github.io/CodeTide/) -->
<img src="https://mclovinittt-agenttidedemo.hf.space/codetide-banner.png" alt="code-tide-logo" width="900" height="auto"/>



[![GitHub Stars](https://img.shields.io/github/stars/BrunoV21/CodeTide?style=social)](https://github.com/BrunoV21/CodeTide/stargazers)
[![PyPI Downloads](https://static.pepy.tech/badge/CodeTide)](https://pepy.tech/projects/CodeTide)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/CodeTide?style=flat)](https://pypi.org/pypi/codetide/)
[![PyPI - Version](https://img.shields.io/pypi/v/CodeTide?style=flat)](https://pypi.org/pypi/codetide/)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)

</div>

---

**CodeTide** is a fully local, privacy-preserving tool for parsing and understanding Python codebases using symbolic, structural analysis. No internet, no LLMs, no embeddings - just fast, explainable, and deterministic code intelligence.


## ✅ Key Features

- ✅ 100% **local & private** - all parsing and querying happens on your machine.
- 📦 Structured parsing of codebases using [Tree-sitter](https://tree-sitter.github.io/tree-sitter/).
- 🧠 Retrieval of relevant code snippets by symbolic ID - not vector similarity.
- 🧱 Visualize the architecture and hierarchy of your project.
- ⚡ Fast, cacheable parsing with smart update detection.
- 🔁 Designed to work alongside tools like Copilot, GPT, and Claude - on your terms.


---
# Entrypoints & Usage

CodeTide provides several entrypoints for interacting with the system via command-line and web UI. These entrypoints are exposed through the `uvx` launcher and require the appropriate extras to be installed.

## CodeTide CLI

To use the main CodeTide CLI:

```sh
uvx --from codetide codetide-cli --help
```
## AgentTide

AgentTide consists of a demo, showing how CodeTide can integrate with LLMs and augment code generation and condebase related workflows. If you ask Tide to describe himself, he will say something like this: I'm the next-generation, precision-driven software engineering agent built on top of CodeTide. You can use it via the command-line interface (CLI) or a beautiful interactive UI.

> **Demo available:** Try AgentTide live on Hugging Face Spaces: [https://mclovinittt-agenttidedemo.hf.space/](https://mclovinittt-agenttidedemo.hf.space/)

---

<div align="center">
<!-- [![Docs](https://img.shields.io/badge/docs-CodeTide.github.io-red)](https://brunov21.github.io/CodeTide/) -->
<img src="https://mclovinittt-agenttidedemo.hf.space/agent-tide-demo.gif" alt="agent-tide-demo" width="100%" height="auto"/>
</div>

---

**AgentTide CLI**

To use the AgentTide conversational CLI, you must install the `[agents]` extra and launch via:

```sh
uvx --from codetide[agents] agent-tide
```

This will start an interactive terminal session with AgentTide.

**AgentTide UI**

To use the AgentTide web UI, you must install the `[agents-ui]` extra and launch via:

```sh
uvx --from codetide[agents-ui] agent-tide-ui
```

This will start a web server for the AgentTide UI. Follow the on-screen instructions to interact with the agent in your browser at [http://localhost:9753](http://localhost:9753) (or the port you specified)

### Why Try AgentTide? ([Full Guide & Tips Here](codetide/agents/tide/ui/chainlit.md))

**Local-First & Private:** All code analysis and patching is performed locally. Your code never leaves your machine.
- **Transparent & Stepwise:** See every plan and patch before it's applied. Edit, reorder, or approve steps—you're always in control.
- **Context-Aware:** AgentTide loads only the relevant code identifiers and dependencies for your request, making it fast and precise.
- **Human-in-the-Loop:** After each step, review the patch, provide feedback, or continue—no black-box agent behavior.
- **Patch-Based Editing:** All changes are atomic diffs, not full file rewrites, for maximum clarity and efficiency.

**Usage Tips:**  
If you know the exact code context, specify identifiers directly in your request (e.g., `module.submodule.file_withoutextension.object`).  
You can use the `plan` command to generate a step-by-step implementation plan for your request, review and edit the plan, and then proceed step-by-step. The `commit` command allows you to review and finalize changes before they are applied. See the [chainlit.md](codetide/agents/tide/ui/chainlit.md) for full details and advanced workflows, including the latest specifications for these commands!

---

## 🔌 VSCode Extension

<div align="center">
<img src="https://raw.githubusercontent.com/BrunoV21/CodeTide-vsExtension/main/assets/codetide-demo.gif" alt="codetide-vs-extension" width="100%" height="auto"/>
</div>

---

CodeTide is available as a native [**Visual Studio Code extension**](https://marketplace.visualstudio.com/items?itemName=BrunoV21.codetide), giving you direct access to structural code understanding inside your editor.

- Navigate code intelligently
- Retrieve context-aware snippets
- Send context directly to LLMs like Copilot or GPT
- Works seamlessly with any other extensions

---

🔗 **Install it now**: [CodeTide on VSCode Marketplace](https://marketplace.visualstudio.com/items?itemName=BrunoV21.codetide)  
🔧 **Extension source code**: [CodeTide VSCode Extension on GitHub](https://github.com/BrunoV21/CodeTide-vsExtension/tree/main)

---

## 🖧 CodeTide as an MCP Server

CodeTide now supports acting as an **MCP Server**, enabling seamless integration with AI agents and tools. This feature allows agents to dynamically interact with your codebase and retrieve context efficiently.

To enable CodeTide as an MCP server in your environment, add the following entry to your servers configuration file:
```json
{
  "mcpServers": {
    "codetide": {
      "command": "uvx",
      "args": [
        "--from",
        "codetide",
        "codetide-mcp-server"
      ],
      "env": {
        "CODETIDE_WORKSPACE": "./"
      }
    }
  }
}
```

#### Why This Helps Agents
Agents working with codebases often need:
- **Contextual Understanding**: Retrieve declarations, imports, and references for any part of the code.
- **Tool Integration**: Use built-in tools to navigate and analyze code.

#### Available Tools
CodeTide provides the following tools for agents:
1. **`getContext`**: Retrieve code context for identifiers (e.g., functions, classes).
2. **`getRepoTree`**: Explore the repository structure.

#### Example: Initializing an LLM with CodeTide
Here’s a snippet from `agent_tide.py` demonstrating how to initialize an LLM with CodeTide as an MCP server:

```python
from aicore.llm import Llm, LlmConfig
from codetide.mcp import codeTideMCPServer
import os

def init_llm() -> Llm:
    llm = Llm.from_config(
        LlmConfig(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
            api_key=os.getenv("DEEPSEEK-API-KEY")
        )
    )
    llm.provider.mcp.add_server(name=codeTideMCPServer.name, parameters=codeTideMCPServer)
    return llm
```

This setup allows the LLM to leverage CodeTide’s tools for codebase interactions.

CodeTide can now be used as an MCP Server! This allows seamless integration with AI tools and workflows. Below are the tools available:
The available tools are:
- **getContext**: Retrieve code context for identifiers.
- **getRepoTree**: Generate a visual tree representation of the repository.

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

## 🧠 Philosophy

CodeTide is about giving developers structure-aware tools that are **fast, predictable, and private**. Your code is parsed, navigated, and queried as a symbolic graph - not treated as a black box of tokens. Whether you’re building, refactoring, or feeding context into an LLM - **you stay in control**.

> Like a tide, your codebase evolves - and CodeTide helps you move with it, intelligently.

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
  → **TypeScript** is the top priority. **Now available in Beta**
  
~~- 🧭 **Handle relative imports** in Python projects  
  → Improve resolution for intra-package navigation.~~

- 🚀 **AgentTideUi Hugging Face Space**  
  → We are planning to make AgentTideUi available as a Hugging Face Space, supporting GitHub OAuth for user session and allowing users to provide a repo URL for one-time conversations.

---

## 🤖 Agents Module: AgentTide

> **Demo available:** Try AgentTide live on Hugging Face Spaces: [https://mclovinittt-agenttidedemo.hf.space/](https://mclovinittt-agenttidedemo.hf.space/)

CodeTide now includes an `agents` module, featuring **AgentTide**—a precision-driven software engineering agent that connects directly to your codebase and executes your requests with full code context.

**AgentTide** leverages CodeTide’s symbolic code understanding to:
- Retrieve and reason about relevant code context for any request
- Generate atomic, high-precision patches using strict protocols
- Apply changes directly to your codebase, with robust validation

### Where to Find It
- Source: [`codetide/agents/tide/agent.py`](codetide/agents/tide/agent.py)

### What It Does
AgentTide acts as an autonomous agent that:
- Connects to your codebase using CodeTide’s parsing and context tools
- Interacts with users via a conversational interface
- Identifies relevant files, classes, and functions for any request
- Generates and applies diff-style patches, ensuring code quality and requirements fidelity

### Example Usage
To use AgentTide, ensure you have the `aicore` package installed (`pip install codetide[agents]`), then instantiate and run the agent:

```python
from codetide import CodeTide
from codetide.agents.tide.agent import AgentTide
from aicore.llm import Llm, LlmConfig
import os, asyncio

async def main():
    tide = await CodeTide.from_path("/path/to/your/repo")
    llm = Llm.from_config(
        LlmConfig(
            model="deepseek-chat",
            provider="deepseek",
            temperature=0,
            api_key=os.getenv("DEEPSEEK-API-KEY")
        )
    )
    agent = AgentTide(llm=llm, tide=tide)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
```

AgentTide will prompt you for requests, retrieve the relevant code context, and generate precise patches to fulfill your requirements.

**Disclaimer:**
AgentTide is designed for focused, context-aware code editing, not for generating entire applications from vague ideas. While CodeTide as a platform can support larger workflows, the current version of AgentTide is optimized for making precise, well-scoped changes. For best results, provide one clear request at a time. AgentTide does not yet have access to your terminal or the ability to execute commands, but support for test-based validation is planned in future updates.

For more details, see the [agents module source code](codetide/agents/tide/agent.py).

---

## 📄 License

CodeTide is licensed under the **Apache 2.0 License**.

---

## 🧑‍💻 Contributing
Interested in contributing to CodeTide? We welcome contributions of all kinds - especially new language parsers!

If you'd like to add support for a new language (e.g., Rust, Java, Go), see our [CONTRIBUTING.md](./CONTRIBUTING.md) guide. You'll implement your parser by extending our BaseParser interface and providing robust test coverage. Reference implementations are available for Python and TypeScript in the tests/parsers directory.
