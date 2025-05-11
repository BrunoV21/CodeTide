![code-tide-logo](./docs/assets/codetide-logo.png)

## 🌊 What is CodeTide?

**CodeTide** is a developer tool and AI assistant framework designed to help both humans and language models (LLMs) better understand, generate, and navigate complex codebases through structural and graph-based insights.

The name **CodeTide** reflects the dynamic, flowing nature of code—how modules, functions, and dependencies ripple through a project like waves in a tide. CodeTide doesn’t just statically analyze; it adapts, helps you plan, and evolves your codebase through agentic and intelligent generation. Whether you're starting from scratch or exploring a legacy repo, CodeTide keeps your development flow smooth and synchronized.

Currently, CodeTide supports **Python** projects.

---

## 🚀 Project Goals

CodeTide aims to provide a comprehensive graph-based interface for understanding code dependencies and structure. It supports:
- **File-level and object-level (classes/functions)** dependency analysis.
- **LLM-aided summarization** and **contextual retrieval** of code components.
- **Graph-guided codebase generation**, enabling structured agentic workflows.

---

## ⚙️ Setup

```bash
conda create --name codetide python=3.13
````

### Clone From Source

```bash
git clone https://github.com/BrunoV21/CodeTide.git
cd CodeTide
pip install -r requirements.txt
pip install -e .
```

### Install From PyPI

```bash
pip install codetide --upgrade
```

---

## 🧠 Usage

There are two primary use cases where **CodeTide** integrates with your workflow:

### 1. 🌱 Starting from Scratch

When no codebase exists yet, CodeTide allows agents or developers to generate a modular architecture via **graph planning** and **LLM-powered validation**:

* Design core file structure as a graph
* Add modules and dependencies incrementally
* Automatically verify interconnections via logic-based edge assertions

This helps generate maintainable and extensible projects from day one.

### 2. 🔍 Collaborating on Existing Codebases

For larger or unfamiliar codebases:

* Use `codetide.knowledge.generate_annotations()` to generate LLM-powered summaries of each class/function/module
* Use `codetide.knowledge.retrieve_annotations()` to retrieve relevant code fragments based on a task

> CodeTide works in **token-aware batches** to stay within your model's context window. No embeddings or vector DBs are used — this is fully symbolic and graph-based.

---

## 🐳 Docker

*TODO: Add Docker instructions*

---

## 🤝 Contributing

We welcome contributions to CodeTide!

1. Fork the repository
2. Create a feature or fix branch
3. Make and test your changes
4. Push and open a Pull Request

Please ensure your code adheres to the style guide and includes tests if possible.

---

## 📄 License

CodeTide is licensed under the **Apache 2.0 License**.

---

## 🛠️ TODOs

* Add `delete()` support in `knowledge` and `ClassFuncRepo`
* Port `ideal_rcf` to Pydantic BaseModel + Mermaid graph support
* Add dynamic update method for annotations based on changed files

### Future Directions

* ✅ Dynamic graph construction from scratch with LLM validation
* ✅ Agentic code generation workflows
* 🧠 Better import handling via `repo-tree + classfunc` index
* 📈 Performance metrics (e.g., token usage, latency, task success rate)
* 📦 SWE-Bench style evaluation (may require cloud infra)
* 🧪 Add a `contribute.md`
* 🧊 Gradio or Web Frontend

---

## 💡 Example Use Cases

* Generate a new repo structure from scratch via graph planning
* Use LLMs to summarize and retrieve context for modification
* Integrate with multi-agent frameworks that require structured file planning
* Maintain code quality via structural validation over time

---

## 🌐 Why CodeTide?

Like the tide, your codebase is in constant motion — expanding, refactoring, adapting to new ideas. CodeTide embraces that motion. It gives LLMs and developers a shared graph to reason over and generate from, supporting the future of intelligent, structured software design.

---
