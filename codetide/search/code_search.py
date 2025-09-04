from codetide.search.preprocessor import CodeQueryPreprocessor
from codetide.search.engine import AsyncFastCodeSearchIndex

from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import asyncio

class SmartCodeSearch:
    """
    High-level interface for intelligent code search with preprocessing.
    """
    
    def __init__(self, 
                 documents: Optional[Dict[str, str]] = None,
                 index_path: Optional[str] = None,
                 max_workers: Optional[int] = None,
                 preprocess_documents: bool = False):
        """
        Initialize the smart code search.
        
        Args:
            documents: Dictionary of documents to index
            index_path: Path to load existing index from
            max_workers: Number of workers for parallel processing
            preprocess_documents: Whether to preprocess documents during indexing
        """
        self.preprocessor = CodeQueryPreprocessor()
        self.max_workers = max_workers
        self.preprocess_documents = preprocess_documents
        
        # Initialize the search index
        if index_path:
            self.search_index = None  # Will be loaded async
            self.index_path = index_path
        elif documents:
            processed_docs = documents
            if preprocess_documents:
                processed_docs = {
                    key: self._preprocess_document_content(content)
                    for key, content in documents.items()
                }
            
            self.search_index = AsyncFastCodeSearchIndex(processed_docs, max_workers)
            self.index_path = None
        else:
            raise ValueError("Must provide either documents or index_path")
        
        self.ready = False
    
    def _preprocess_document_content(self, content: str) -> str:
        """Preprocess document content for better indexing"""
        # For documents, we want to preserve structure but add searchable variations
        lines = content.split('\n')
        processed_lines = []
        
        for line in lines:
            processed_lines.append(line)  # Keep original
            
            # Add preprocessed version for better matching
            preprocessed = self.preprocessor.preprocess_query(
                line, 
                expand_case=True,
                expand_abbreviations=False,  # Don't expand in documents
                apply_stemming=False,
                remove_stop_words=False
            )
            
            if preprocessed and preprocessed != line.lower():
                processed_lines.append(f"  {preprocessed}")  # Add as searchable content
        
        return '\n'.join(processed_lines)
    
    async def initialize_async(self):
        """Initialize the search index asynchronously"""
        if self.index_path:
            self.search_index = await AsyncFastCodeSearchIndex.load_index_async(
                self.index_path, max_workers=self.max_workers
            )
        else:
            await self.search_index.build_index_async()
        
        self.ready = True
    
    async def search_smart(self, 
                          query: str, 
                          top_k: int = 10,
                          use_variations: bool = True,
                          exact_match_boost: float = 0.3) -> List[Tuple[str, float]]:
        """
        Perform intelligent search with query preprocessing and multiple strategies.
        
        Args:
            query: Raw user query
            top_k: Number of top results to return
            use_variations: Whether to use multiple query variations
            exact_match_boost: Boost factor for exact matches
        
        Returns:
            List of (document_key, score) tuples
        """
        if not self.ready:
            raise RuntimeError("Search index not ready. Call initialize_async() first.")
        
        if not query or not query.strip():
            return []
        
        # Generate query variations
        if use_variations:
            queries = self.preprocessor.generate_query_variations(query.strip())
        else:
            queries = [self.preprocessor.preprocess_query(query.strip())]
        
        # Remove empty queries
        queries = [q for q in queries if q and q.strip()]
        
        if not queries:
            return []
        
        # Run multiple searches concurrently
        search_tasks = []
        
        # Regular searches with different query variations
        for q in queries:
            search_tasks.append(self.search_index.search_async(q, top_k * 2))
        
        # Exact match search for the original query
        if exact_match_boost > 0:
            search_tasks.append(
                self.search_index.search_exact_match_async(query.strip(), top_k)
            )
        
        # Execute all searches concurrently
        all_results = await asyncio.gather(*search_tasks)
        
        # Combine and score results
        combined_scores = defaultdict(float)
        result_counts = defaultdict(int)
        
        # Weight different query variations
        for i, results in enumerate(all_results[:-1] if exact_match_boost > 0 else all_results):
            weight = 1.0 / (i + 1)  # First query gets highest weight
            for doc_key, score in results:
                combined_scores[doc_key] += score * weight
                result_counts[doc_key] += 1
        
        # Add exact match boost
        if exact_match_boost > 0 and len(all_results) > len(queries):
            exact_results = all_results[-1]
            for doc_key, score in exact_results:
                combined_scores[doc_key] += score * exact_match_boost
                result_counts[doc_key] += 1
        
        # Normalize scores by appearance frequency and sort
        final_scores = [
            (doc_key, score / result_counts[doc_key])
            for doc_key, score in combined_scores.items()
        ]
        
        return sorted(final_scores, key=lambda x: x[1], reverse=True)[:top_k]
    
    async def search_with_context(self, 
                                 query: str, 
                                 top_k: int = 10,
                                 context_lines: int = 2) -> List[Dict]:
        """
        Search with context lines around matches.
        
        Returns:
            List of dictionaries with doc_key, score, and context
        """
        results = await self.search_smart(query, top_k)
        
        enriched_results = []
        for doc_key, score in results:
            if doc_key in self.search_index.documents:
                content = self.search_index.documents[doc_key]
                # Simple context extraction (could be enhanced)
                lines = content.split('\n')
                context = lines[:min(context_lines * 2, len(lines))]
                
                enriched_results.append({
                    'doc_key': doc_key,
                    'score': score,
                    'context': '\n'.join(context),
                    'total_lines': len(lines)
                })
        
        return enriched_results
    
    async def update_document(self, doc_key: str, content: str):
        """Update a document with preprocessing"""
        processed_content = content
        if self.preprocess_documents:
            processed_content = self._preprocess_document_content(content)
        
        await self.search_index.update_document_async(doc_key, processed_content)
    
    async def batch_update_documents(self, updates: Dict[str, str]):
        """Update multiple documents with preprocessing"""
        processed_updates = updates
        if self.preprocess_documents:
            processed_updates = {
                key: self._preprocess_document_content(content)
                for key, content in updates.items()
            }
        
        await self.search_index.batch_update_documents_async(processed_updates)
    
    async def save_index(self, filepath: str):
        """Save the search index"""
        await self.search_index.save_index_async(filepath)
    
    def get_stats(self) -> Dict:
        """Get search index statistics"""
        stats = self.search_index.get_stats() if self.search_index else {}
        stats['preprocessor_cache_size'] = {
            'camel_case': self.preprocessor._expand_camel_case.cache_info().currsize,
            'snake_kebab': self.preprocessor._expand_snake_kebab.cache_info().currsize,
            'stemming': self.preprocessor._simple_stem.cache_info().currsize
        }
        return stats


# Synchronous wrapper
class SmartCodeSearchSync:
    """Synchronous wrapper for SmartCodeSearch"""
    
    def __init__(self, 
                 documents: Optional[Dict[str, str]] = None,
                 index_path: Optional[str] = None,
                 max_workers: Optional[int] = None,
                 preprocess_documents: bool = False):
        
        self.async_search = SmartCodeSearch(
            documents, index_path, max_workers, preprocess_documents
        )
        
        # Initialize synchronously
        asyncio.run(self.async_search.initialize_async())
    
    def search(self, query: str, top_k: int = 10, use_variations: bool = True) -> List[Tuple[str, float]]:
        """Synchronous smart search"""
        return asyncio.run(self.async_search.search_smart(query, top_k, use_variations))
    
    def search_with_context(self, query: str, top_k: int = 10, context_lines: int = 2) -> List[Dict]:
        """Synchronous search with context"""
        return asyncio.run(self.async_search.search_with_context(query, top_k, context_lines))
    
    def update_document(self, doc_key: str, content: str):
        """Synchronous document update"""
        asyncio.run(self.async_search.update_document(doc_key, content))
    
    def save_index(self, filepath: str):
        """Synchronous index save"""
        asyncio.run(self.async_search.save_index(filepath))
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        return self.async_search.get_stats()


# Example usage and testing
async def demo_smart_search():
    """Demonstrate the smart code search functionality"""
    
    # Sample code documents
    documents = {
        "user_manager.py": """
        class UserManager:
            def __init__(self):
                self.users = []
            
            def getUserByEmail(self, email):
                return self.find_user_by_email(email)
            
            def find_user_by_email(self, email_address):
                for user in self.users:
                    if user.email == email_address:
                        return user
                return None
        """,
        
        "api_controller.js": """
        const APIController = {
            async handleUserRequest(req, res) {
                const userData = await this.processUserData(req.body);
                res.json(userData);
            },
            
            processUserData: function(data) {
                return validateUserInput(data);
            }
        };
        """,
        
        "database_config.py": """
        DB_CONFIG = {
            'host': 'localhost',
            'port': 5432,
            'database': 'myapp',
            'user': 'admin',
            'password': 'secret'
        }
        
        class DatabaseManager:
            def __init__(self, config):
                self.cfg = config
                self.connection = None
        """,
        
        "utils/string_helpers.py": """
        def camelCaseToSnake(input_string):
            return re.sub('([A-Z])', r'_\1', input_string).lower()
        
        def snake_case_to_camel(snake_str):
            components = snake_str.split('_')
            return components[0] + ''.join(x.title() for x in components[1:])
        """
    }
    
    # Test the smart search
    print("\n=== SMART CODE SEARCH DEMO ===")
    search = SmartCodeSearch(documents)
    await search.initialize_async()
    
    search_queries = [
        "getUserByEmail",
        "find user email", 
        "API controller",
        "db config",
        "camel snake conversion",
        "Hi lets update the DataBaseManager!"
    ]
    
    for query in search_queries:
        print(f"\n--- Searching for: '{query}' ---")
        results = await search.search_smart(query, top_k=3)
        
        for doc_key, score in results:
            print(f"  {score:.3f}: {doc_key}")
    
    # Test with context
    print("\n=== SEARCH WITH CONTEXT ===")
    context_results = await search.search_with_context("user email", top_k=2, context_lines=3)
    
    for result in context_results:
        print(f"\n{result['doc_key']} (score: {result['score']:.3f}):")
        print(result['context'][:200] + "..." if len(result['context']) > 200 else result['context'])
    
    # Show stats
    print("\n=== STATS ===")
    stats = search.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")

if __name__ == "__main__":

    asyncio.run(demo_smart_search())