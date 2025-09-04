
from functools import lru_cache
from typing import List
import unicodedata
import re


class CodeQueryPreprocessor:
    """
    Blazingly fast query preprocessor optimized for code search.
    Handles camelCase, snake_case, kebab-case, stemming, and code-specific terms.
    """
    
    def __init__(self):
        # Compile regex patterns once for maximum performance
        self._camel_case_pattern = re.compile(r'([a-z])([A-Z])')
        self._snake_kebab_pattern = re.compile(r'[_\-]+')
        self._word_boundary_pattern = re.compile(r'\b\w+\b')
        self._non_alphanumeric = re.compile(r'[^\w\s]')
        self._multiple_spaces = re.compile(r'\s+')
        self._number_pattern = re.compile(r'\d+')
        
        # Common code abbreviations and their expansions (cached for speed)
        self._code_expansions = {
            'btn': 'button',
            'cfg': 'config configuration',
            'ctx': 'context',
            'db': 'database',
            'fn': 'function',
            'func': 'function',
            'impl': 'implementation implement',
            'mgr': 'manager',
            'obj': 'object',
            'param': 'parameter',
            'proc': 'process processor',
            'repo': 'repository',
            'req': 'request require',
            'res': 'response result',
            'str': 'string',
            'temp': 'temporary template',
            'util': 'utility utilities',
            'val': 'value',
            'var': 'variable',
            'auth': 'authentication authorize',
            'admin': 'administrator administration',
            'api': 'application programming interface',
            'ui': 'user interface',
            'url': 'uniform resource locator link',
            'http': 'hypertext transfer protocol',
            'json': 'javascript object notation',
            'xml': 'extensible markup language',
            'sql': 'structured query language',
            'css': 'cascading style sheets',
            'html': 'hypertext markup language',
            'js': 'javascript',
            'py': 'python',
            'ts': 'typescript',
            'async': 'asynchronous',
            'sync': 'synchronous',
        }
        
        # Simple stemming rules for common programming terms
        self._stem_rules = [
            (r'ies$', 'y'),      # utilities -> utility
            (r'ied$', 'y'),      # applied -> apply
            (r'ying$', 'y'),     # applying -> apply
            (r'ing$', ''),       # processing -> process
            (r'ed$', ''),        # processed -> process
            (r'er$', ''),        # processor -> process
            (r'est$', ''),       # fastest -> fast
            (r's$', ''),         # functions -> function
        ]
        self._compiled_stem_rules = [(re.compile(pattern), replacement) 
                                   for pattern, replacement in self._stem_rules]
        
        # Stop words for code (less aggressive than natural language)
        self._stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
            'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 
            'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
            'we', 'they', 'me', 'him', 'her', 'us', 'them'
        }
    
    @lru_cache(maxsize=1000)
    def _expand_camel_case(self, word: str) -> str:
        """Convert camelCase to space-separated words with caching"""
        # Handle camelCase: getUserName -> get User Name
        expanded = self._camel_case_pattern.sub(r'\1 \2', word)
        return expanded.lower()
    
    @lru_cache(maxsize=1000)
    def _expand_snake_kebab(self, word: str) -> str:
        """Convert snake_case and kebab-case to space-separated with caching"""
        # Handle snake_case and kebab-case: get_user_name -> get user name
        return self._snake_kebab_pattern.sub(' ', word).lower()
    
    @lru_cache(maxsize=500)
    def _simple_stem(self, word: str) -> str:
        """Apply simple stemming rules with caching"""
        if len(word) <= 3:  # Don't stem very short words
            return word
            
        for pattern, replacement in self._compiled_stem_rules:
            if pattern.search(word):
                stemmed = pattern.sub(replacement, word)
                if len(stemmed) >= 2:  # Don't create words that are too short
                    return stemmed
        return word
    
    def _expand_abbreviations(self, words: List[str]) -> List[str]:
        """Expand common code abbreviations"""
        expanded = []
        for word in words:
            if word in self._code_expansions:
                expanded.extend(self._code_expansions[word].split())
            expanded.append(word)
        return expanded
    
    def preprocess_query(self, query: str, 
                        expand_case: bool = True,
                        expand_abbreviations: bool = True, 
                        apply_stemming: bool = True,
                        remove_stop_words: bool = False,
                        min_word_length: int = 2) -> str:
        """
        Preprocess a query for optimal code search performance.
        
        Args:
            query: Raw user query
            expand_case: Whether to expand camelCase, snake_case, kebab-case
            expand_abbreviations: Whether to expand common code abbreviations
            apply_stemming: Whether to apply simple stemming
            remove_stop_words: Whether to remove stop words (usually False for code)
            min_word_length: Minimum word length to keep
        
        Returns:
            Preprocessed query string
        """
        if not query or not query.strip():
            return ""
        
        # Normalize unicode characters
        query = unicodedata.normalize('NFKD', query)
        
        # Remove excessive punctuation but keep some code-relevant chars
        query = self._non_alphanumeric.sub(' ', query)
        
        # Extract words
        words = self._word_boundary_pattern.findall(query.lower())
        
        # Process each word
        processed_words = []
        
        for word in words:
            if len(word) < min_word_length:
                continue
                
            # Skip if it's just numbers (unless it's a version number context)
            if self._number_pattern.fullmatch(word):
                processed_words.append(word)  # Keep numbers as they might be important
                continue
            
            # Expand case conventions
            if expand_case:
                # Handle camelCase
                if any(c.isupper() for c in word[1:]):  # Has uppercase after first char
                    expanded = self._expand_camel_case(word)
                    processed_words.extend(expanded.split())
                
                # Handle snake_case and kebab-case
                if '_' in word or '-' in word:
                    expanded = self._expand_snake_kebab(word)
                    processed_words.extend(expanded.split())
            
            # Add original word
            processed_words.append(word)
        
        # Remove duplicates while preserving order
        unique_words = []
        seen = set()
        for word in processed_words:
            if word not in seen and len(word) >= min_word_length:
                unique_words.append(word)
                seen.add(word)
        
        # Expand abbreviations
        if expand_abbreviations:
            unique_words = self._expand_abbreviations(unique_words)
        
        # Apply stemming
        if apply_stemming:
            unique_words = [self._simple_stem(word) for word in unique_words]
        
        # Remove stop words (usually not recommended for code search)
        if remove_stop_words:
            unique_words = [word for word in unique_words 
                          if word not in self._stop_words]
        
        # Final cleanup and deduplication
        final_words = []
        seen = set()
        for word in unique_words:
            if word and len(word) >= min_word_length and word not in seen:
                final_words.append(word)
                seen.add(word)
        
        return ' '.join(final_words)
    
    def generate_query_variations(self, query: str) -> List[str]:
        """Generate multiple query variations for better search coverage"""
        variations = []
        
        # Original query
        variations.append(query)
        
        # Preprocessed with different settings
        variations.append(self.preprocess_query(query, 
                                              expand_case=True, 
                                              expand_abbreviations=True, 
                                              apply_stemming=False))
        
        variations.append(self.preprocess_query(query, 
                                              expand_case=True, 
                                              expand_abbreviations=False, 
                                              apply_stemming=True))
        
        variations.append(self.preprocess_query(query, 
                                              expand_case=False, 
                                              expand_abbreviations=True, 
                                              apply_stemming=True))
        
        # Remove empty and duplicate variations
        return list(filter(None, list(dict.fromkeys(variations))))
    
if __name__ == "__main__":        
    # Test the preprocessor
    print("=== QUERY PREPROCESSOR DEMO ===")
    preprocessor = CodeQueryPreprocessor()
    
    test_queries = [
        "getUserByEmail",
        "find-user-by-email", 
        "API_Controller",
        "db cfg",
        "string helpers",
        "camelCase to snake",
        "Hi lets update the DataBaseManager!"
    ]
    
    for query in test_queries:
        processed = preprocessor.preprocess_query(query)
        variations = preprocessor.generate_query_variations(query)
        print(f"\nOriginal: {query}")
        print(f"Processed: {processed}")
        print(f"Variations: {variations}")