# 🧑‍💻 Contributing to CodeTide

Thanks for your interest in contributing to CodeTide!

This document outlines how to contribute a **new language parser**, along with general guidelines to maintain the quality and consistency of the codebase.

---

## 🧩 Adding a New Language Parser

To add support for a new programming language:

### 1. **Create a Parser Class**

- Your parser must inherit from the abstract base class `BaseParser` in `codetide.parsers.base_parser`.
- Parsers live in `codetide/parsers/` and should be named `<language>_parser.py`, e.g., `rust_parser.py`.

Here’s a minimal example:

```python
# codetide/parsers/rust_parser.py

from codetide.parsers.base_parser import BaseParser

class RustParser(BaseParser):
    extension = ".rs"
    language = "rust"
    import_statement_template = "use {module};"

    def parse_file(self, filepath):
        # Implement Tree-sitter-based file parsing
        pass

    def resolve_intra_file_dependencies(self, codefile):
        # Optional: resolve internal references
        pass

    def resolve_inter_files_dependencies(self, codebase):
        # Optional: resolve external references
        pass
````

> ✅ Use [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) as the parser backend.

---

### 2. **Register Your Parser**

Make sure your parser is registered in the `codetide.core.defaults.LANGUAGE_EXTENSIONS` dictionary, so CodeTide can associate it with relevant file extensions.

---

### 3. **Write Tests**

You must include **comprehensive test coverage** for your parser:

* Add your test file(s) to `tests/parsers/`.
* Follow existing examples like `test_python_parser.py` and `test_typescript_parser.py`.

Tests should verify:

* Core structural parsing (classes, functions, imports, variables)
* Reference resolution behavior (intra- and inter-file, if applicable)

Run tests with:

```bash
pytest
```

---

### 4. **Verify Integration**

Before submitting a pull request:

* ✅ Run all tests (`pytest`)
* ✅ Ensure your parser handles a minimal real-world sample file
* ✅ Confirm your parser does not break existing functionality

---

## 🧹 Code Style & Standards

* Use **Python 3.9+** syntax
* Format code with `ruff`
* Follow type annotations and PEP8
* Keep functions small and focused

---

## 💬 Questions?

Feel free to open an issue or start a discussion if you're unsure about the best way to contribute.

---

Thank you for helping improve CodeTide! 🌊