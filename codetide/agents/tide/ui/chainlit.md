# Welcome to Agent Tide! 🚀🤖

```
█████╗  ██████╗ ███████╗███╗   ██╗████████╗    ████████╗██╗██████╗ ███████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝    ╚══██╔══╝██║██╔══██╗██╔════╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║          ██║   ██║██║  ██║█████╗  
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║          ██║   ██║██║  ██║██╔══╝  
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║          ██║   ██║██████╔╝███████╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝          ╚═╝   ╚═╝╚═════╝ ╚══════╝
```


# CodeTide & AgentTide

Welcome! This project uses **[CodeTide](https://github.com/BrunoV21/CodeTide)** — a fully local, privacy-preserving tool for parsing and understanding Python codebases using symbolic, structural analysis. CodeTide does not use LLMs, embeddings, or external APIs: all analysis is fast, explainable, and deterministic, running entirely on your machine.

## What is AgentTide?

**AgentTide** is a precision-driven software engineering agent built on top of CodeTide. It connects directly to your codebase, retrieves relevant code context, and generates atomic, high-precision patches to fulfill your requests. AgentTide is designed for focused, context-aware code editing, ensuring code quality and requirements fidelity.

---

**Original repository:** [https://github.com/BrunoV21/CodeTide](https://github.com/BrunoV21/CodeTide)


---

## Example Things to Ask Agent Tide

You can ask Agent Tide to perform a wide variety of code-related tasks. Here are some example prompts to get you started:

- **Add new functionality**
  - "Add a function to calculate the factorial of a number in `utils.py`."
  - "Implement a REST API endpoint for user registration."

- **Refactor or improve code**
  - "Refactor the `process_data` function to improve readability and performance."
  - "Rename the variable `x` to `user_id` throughout `models/user.py`."

- **Fix bugs**
  - "Fix the bug where the login form crashes on empty input."
  - "Resolve the off-by-one error in the `get_page` method."

- **Write or update tests**
  - "Add unit tests for the `EmailSender` class."
  - "Increase test coverage for `api/views.py`."

- **Documentation**
  - "Generate a docstring for the `parse_config` function."
  - "Update the README with installation instructions."

- **Code analysis and suggestions**
  - "List all functions in `main.py` that are missing type annotations."
  - "Suggest performance improvements for the `data_loader` module."

- **Other codebase tasks**
  - "Delete the deprecated `old_utils.py` file."
  - "Move the `helpers` directory into `core/`."

Feel free to be specific or general in your requests. Agent Tide will analyze your codebase and generate precise, production-ready patches to fulfill your needs!
