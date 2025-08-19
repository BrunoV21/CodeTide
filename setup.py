from setuptools import setup, find_packages
from pathlib import Path

here = Path(__file__).resolve().parent
long_description = (here / "README.md").read_text(encoding="utf-8")
requirements = (here / "requirements.txt").read_text(encoding="utf-8").splitlines()
requirements_visualization = (here / "requirements-visualization.txt").read_text(encoding="utf-8").splitlines()
requirements_agents = (here / "requirements-agents.txt").read_text(encoding="utf-8").splitlines()
requirements_agents_ui = (here / "requirements-agents-ui.txt").read_text(encoding="utf-8").splitlines()
requirements_agents_ui.extend(requirements_agents)

setup(
    name="codetide",
    version="0.0.25",
    author="Bruno V.",
    author_email="bruno.vitorino@tecnico.ulisboa.pt",
    description="CodeTide is a fully local, privacy-preserving tool for parsing and understanding Python codebases using symbolic, structural analysis. No internet, no LLMs, no embeddings - just fast, explainable, and deterministic code intelligence.",
    packages=find_packages(),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BrunoV21/CodeTide",
    install_requires=requirements,
    include_package_data=True,
    extras_require={
        "visualization": requirements_visualization,
        "agents": requirements_agents,
        "agents-ui": requirements_agents_ui
    },
    entry_points={
        "console_scripts": [
            "codetide-mcp-server=codetide.mcp.server:serve",
            "codetide-cli=codetide.cli:main",
            # agent-tide-step requires the [agents] extra: pip install codetide[agents] or to execute uvx --from codetide[agents] agent-tide-step -h
            "agent-tide-step=codetide.agents.tide.cli_step:main",
            "agent-tide=codetide.agents.tide.cli:main",
            "agent-tide-ui=codetide.agents.tide.ui:main"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)