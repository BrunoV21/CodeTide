from pathlib import Path
import os

INSTALLATION_DIR = Path(os.path.abspath(os.path.dirname(__file__)))

GITINGORE_FILE = ".gitignore"

DEFAULT_GITIGNORE = [
    ".git/",
    "*.pyc"
]

# Language extensions mapping
LANGUAGE_EXTENSIONS = {
    'python': ['.py'],
    'javascript': ['.js'],
    'typescript': ['.ts', '.tsx'],
    'java': ['.java'],
    'c': ['.c', '.h'],
    'cpp': ['.cpp', '.hpp', '.cc', '.hh', '.cxx', '.hxx'],
    'ruby': ['.rb'],
    'go': ['.go'],
    'rust': ['.rs'],
    'swift': ['.swift'],
    'php': ['.php'],
    'csharp': ['.cs'],
    'kotlin': ['.kt', '.kts'],
    'scala': ['.scala']
}

# Default file patterns to ignore
DEFAULT_IGNORE_PATTERNS = [
    '*.pyc', '*.pyo', '*.so', '*.o', '*.a', '*.lib', '*.dll', '*.exe',
    '*.jar', '*.war', '*.ear', '*.zip', '*.tar', '*.gz', '*.bz2', '*.7z',
    '*.egg', '*.egg-info', '*.whl',
    '__pycache__', '.git', '.hg', '.svn', '.DS_Store', 
    'node_modules', 'venv', 'env', '.env', '.venv',
    'build', 'dist', 'target', '.idea', '.vscode'
]


DEFAULT_REGEX_DEFS_PATH = INSTALLATION_DIR / "parsers" / "regex" / "regex_definitions"

DEFAULT_TEMPLATES_PATH = INSTALLATION_DIR / "parsers" / "templates"

DEFAULT_ENCODING = "utf8"

DEFAULT_ENCODINGS = ['utf-8', 'latin1', 'cp1252']

LOGGING_DIR = "./logs/"

SERIALIZATION_DIR = "./storage"

SERIALIZED_GRAPH = "graph.json"

SERIALIZED_CODEBASE = "codebase.json"

SERIALIZED_CLASSFUNCREPO = "knowledge.json"

SERIALZIED_PARSER_OBJ = "parser.json"

SERIALIZED_ANNOTATIONS = "annotations.json"

SERIALIZED_AICORE_LLM_CONFIG = "aicore_llm_config.json"