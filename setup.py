from setuptools import setup, find_packages

setup(
    name="codetide",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "colorlog==6.9.0",
        "pathspec==0.12.1",
        "pydantic==2.10.3",
        "pyyaml==6.0.2",
        "tree-sitter==0.24.0",
        "tree-sitter-python==0.23.6",
        "json-repair==0.35.0"
    ],
    extras_require={
        "visualization": [
            "plotly==5.24.1",
            "networkx==3.4.2",
            "numpy==2.2.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "codetide=codetide.__main__:main",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache 2.0",
        "Operating System :: OS Independent",
    ],
)