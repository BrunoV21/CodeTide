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

SKIP_EXTENSIONS = [
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.heic', '.heif',
    '.ico', '.icns', '.psd', '.ai', '.eps',

    # Audio
    '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff',

    # Video
    '.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm', '.mpeg', '.mpg', '.3gp',

    # Fonts
    '.ttf', '.otf', '.woff', '.woff2', '.eot',

    # Archives & Compressed
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z', '.iso', '.dmg',

    # Database & Data Dumps
    '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb', '.dbf',
    '.frm', '.myd', '.myi', '.ndf', '.ldf',

    # System / OS junk
    '.sys', '.dll', '.exe', '.bin', '.msi', '.obj', '.o', '.so', '.dylib', '.class',
    '.lock', '.tmp', '.log', '.bak', '.swp', '.swo', '.DS_Store', 'Thumbs.db',

    # 3D / CAD
    '.stl', '.obj', '.fbx', '.blend', '.dae', '.3ds',

    # Other binary documents
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.odt', '.ods', '.odp'
]

DEFAULT_MAX_CONCURRENT_TASKS = 50
DEFAULT_BATCH_SIZE = 128

DEFAULT_ENCODING = "utf8"

DEFAULT_SERIALIZATION_PATH = "./storage/tide.json"
DEFAULT_CACHED_ELEMENTS_FILE = "cached_elements.json"
DEFAULT_CACHED_IDS_FILE = "cached_ids.json"

BREAKLINE = "\n"

CODETIDE_ASCII_ART = """

███████╗ ██████╗ ██████╗ ███████╗████████╗██╗██████╗ ███████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚══██╔══╝██║██╔══██╗██╔════╝
██║     ██║   ██║██║  ██║█████╗     ██║   ██║██║  ██║█████╗  
██║     ██║   ██║██║  ██║██╔══╝     ██║   ██║██║  ██║██╔══╝  
╚██████╗╚██████╔╝██████╔╝███████╗   ██║   ██║██████╔╝███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝╚═════╝ ╚══════╝
 
"""