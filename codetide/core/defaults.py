from pathlib import Path
import os

INSTALLATION_DIR = Path(os.path.abspath(os.path.dirname(__file__))).parent

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
    'scala': ['.scala'],
    # Web and templates
    'html': ['.html', '.htm', '.xhtml', '.html5'],
    'css': ['.css', '.scss', '.sass', '.less', '.styl'],
    'xml': ['.xml', '.xsd', '.xsl', '.xslt', '.rss', '.svg', '.svgz'],
    'yaml': ['.yaml', '.yml'],
    'json': ['.json', '.json5', '.jsonl', '.geojson', '.topojson', '.jsonc'],
    'markdown': ['.md', '.markdown', '.mdown', '.mdwn', '.mkd', '.mkdn'],
    'jinja': ['.j2', '.jinja', '.jinja2'],
    # Configuration files
    'config': [
        '.ini', '.cfg', '.conf', '.properties', '.toml', 
        '.env', '.env.local', '.env.dev', '.env.prod'
    ],
    # Documentation
    'documentation': [
        '.txt', '.text',
        '.tex', '.bib'
    ],
    # Container and deployment
    'container': [
        'Dockerfile', 'docker-compose.yml',
        'docker-compose.yaml', '.dockerignore'
    ]
    
}

DEFAULT_MAX_CONCURRENT_TASKS = 50
DEFAULT_BATCH_SIZE = 128

DEFAULT_ENCODING = "utf8"

DEFAULT_SERIALIZATION_PATH = "./storage/tide.json"
DEFAULT_CACHED_ELEMENTS_FILE = "cached_elements.json"
DEFAULT_CACHED_IDS_FILE = "cached_ids.json"

BREAKLINE = "\n"