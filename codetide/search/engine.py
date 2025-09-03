import pickle
import asyncio
from collections import defaultdict, Counter
import math
import re
from typing import Dict, List, Tuple, Set, Optional
from concurrent.futures import ThreadPoolExecutor
from codetide.core.logs import logger

class AsyncFastCodeSearchIndex:
    def __init__(self, documents: Dict[str, str], max_workers: Optional[int] = None):
        """
        documents: {key: content} where key is your filepath/identifier
        max_workers: Number of workers for parallel processing (defaults to CPU count)
        """
        self.documents = documents
        self.doc_keys = list(documents.keys())
        self.N = len(documents)
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Will be set during index building
        self.index_ready = False
    
    async def build_index_async(self):
        """Build index asynchronously with parallel processing"""
        logger.info(f"Building search index async with {self.max_workers or 'default'} workers...")
        
        # Split documents into chunks for parallel processing
        chunk_size = max(1, len(self.documents) // (self.max_workers or 4))
        doc_items = list(self.documents.items())
        chunks = [doc_items[i:i + chunk_size] for i in range(0, len(doc_items), chunk_size)]
        
        # Process chunks in parallel
        loop = asyncio.get_event_loop()
        
        # Tokenize and count terms in parallel
        tokenize_tasks = [
            loop.run_in_executor(self.executor, self._process_chunk, chunk)
            for chunk in chunks
        ]
        
        chunk_results = await asyncio.gather(*tokenize_tasks)
        
        # Merge results from all chunks
        await self._merge_chunk_results(chunk_results)
        
        self.index_ready = True
        logger.info(f"Async index built for {self.N} documents with {len(self.idf_scores)} unique terms")
    
    def _process_chunk(self, chunk: List[Tuple[str, str]]) -> Dict:
        """Process a chunk of documents (runs in thread)"""
        if not hasattr(self, '_token_pattern'):
            self._token_pattern = re.compile(r'\b\w+\b')
        
        chunk_data = {
            'tokenized_docs': {},
            'doc_lengths': {},
            'doc_term_counts': {},
            'term_doc_freq': defaultdict(int),
            'all_terms': set()
        }
        
        for doc_key, content in chunk:
            tokens = self._token_pattern.findall(content.lower())
            term_counts = Counter(tokens)
            
            chunk_data['tokenized_docs'][doc_key] = tokens
            chunk_data['doc_lengths'][doc_key] = len(tokens)
            chunk_data['doc_term_counts'][doc_key] = term_counts
            
            unique_terms = term_counts.keys()
            chunk_data['all_terms'].update(unique_terms)
            for term in unique_terms:
                chunk_data['term_doc_freq'][term] += 1
        
        return chunk_data
    
    async def _merge_chunk_results(self, chunk_results: List[Dict]):
        """Merge results from parallel chunk processing"""
        # Initialize combined data structures
        self.tokenized_docs = {}
        self.doc_lengths = {}
        self.doc_term_counts = {}
        term_doc_freq = defaultdict(int)
        all_terms = set()
        
        # Merge all chunks
        for chunk_data in chunk_results:
            self.tokenized_docs.update(chunk_data['tokenized_docs'])
            self.doc_lengths.update(chunk_data['doc_lengths'])
            self.doc_term_counts.update(chunk_data['doc_term_counts'])
            all_terms.update(chunk_data['all_terms'])
            
            for term, freq in chunk_data['term_doc_freq'].items():
                term_doc_freq[term] += freq
        
        # Compute IDF scores
        loop = asyncio.get_event_loop()
        self.idf_scores = await loop.run_in_executor(
            self.executor, 
            self._compute_idf_scores, 
            all_terms, 
            term_doc_freq
        )
        
        # Compute TF scores in parallel
        tf_tasks = []
        chunk_size = max(1, len(self.doc_keys) // (self.max_workers or 4))
        for i in range(0, len(self.doc_keys), chunk_size):
            doc_chunk = self.doc_keys[i:i + chunk_size]
            tf_tasks.append(
                loop.run_in_executor(
                    self.executor,
                    self._compute_tf_scores_chunk,
                    doc_chunk
                )
            )
        
        tf_results = await asyncio.gather(*tf_tasks)
        
        # Merge TF scores
        self.tf_scores = {}
        for tf_chunk in tf_results:
            self.tf_scores.update(tf_chunk)
        
        # BM25 parameters
        self.k1 = 1.5
        self.b = 0.75
        self.avg_doc_length = sum(self.doc_lengths.values()) / self.N
        
        # Build inverted index
        self.inverted_index = await loop.run_in_executor(
            self.executor,
            self._build_inverted_index
        )
    
    def _compute_idf_scores(self, all_terms: Set[str], term_doc_freq: Dict[str, int]) -> Dict[str, float]:
        """Compute IDF scores (runs in thread)"""
        return {
            term: math.log(self.N / freq)
            for term, freq in term_doc_freq.items()
        }
    
    def _compute_tf_scores_chunk(self, doc_keys: List[str]) -> Dict[str, Dict[str, float]]:
        """Compute TF scores for a chunk of documents"""
        tf_scores = {}
        for doc_key in doc_keys:
            term_counts = self.doc_term_counts[doc_key]
            doc_length = self.doc_lengths[doc_key]
            tf_scores[doc_key] = {
                term: count / doc_length 
                for term, count in term_counts.items()
            }
        return tf_scores
    
    def _build_inverted_index(self) -> defaultdict:
        """Build inverted index (runs in thread)"""
        inverted_index = defaultdict(set)
        for doc_key, tokens in self.tokenized_docs.items():
            for term in set(tokens):
                inverted_index[term].add(doc_key)
        return inverted_index
    
    def _process_single_document(self, doc_key: str, content: str) -> Dict:
        """Process a single document for updating (runs in thread)"""
        if not hasattr(self, '_token_pattern'):
            self._token_pattern = re.compile(r'\b\w+\b')
        
        tokens = self._token_pattern.findall(content.lower())
        term_counts = Counter(tokens)
        doc_length = len(tokens)
        
        return {
            'doc_key': doc_key,
            'tokens': tokens,
            'term_counts': term_counts,
            'doc_length': doc_length,
            'unique_terms': set(term_counts.keys())
        }
    
    async def _remove_document_from_index(self, doc_key: str):
        """Remove document data from all indexes"""
        if doc_key not in self.doc_keys:
            return
        
        # Get old document terms for cleanup
        old_terms = set(self.doc_term_counts.get(doc_key, {}).keys())
        
        # Remove from inverted index
        for term in old_terms:
            if term in self.inverted_index:
                self.inverted_index[term].discard(doc_key)
                if not self.inverted_index[term]:  # Remove empty sets
                    del self.inverted_index[term]
        
        # Remove from all document-specific indexes
        self.tokenized_docs.pop(doc_key, None)
        self.doc_lengths.pop(doc_key, None)
        self.doc_term_counts.pop(doc_key, None)
        self.tf_scores.pop(doc_key, None)
        
        # Remove from document keys and update count
        if doc_key in self.doc_keys:
            self.doc_keys.remove(doc_key)
            self.N -= 1
        
        # Recalculate average document length
        if self.N > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.N
        else:
            self.avg_doc_length = 0
    
    async def _integrate_document_data(self, doc_data: Dict, is_update: bool):
        """Integrate new document data into indexes"""
        doc_key = doc_data['doc_key']
        tokens = doc_data['tokens']
        term_counts = doc_data['term_counts']
        doc_length = doc_data['doc_length']
        unique_terms = doc_data['unique_terms']
        
        # Update document-specific data
        self.tokenized_docs[doc_key] = tokens
        self.doc_lengths[doc_key] = doc_length
        self.doc_term_counts[doc_key] = term_counts
        self.tf_scores[doc_key] = {
            term: count / doc_length for term, count in term_counts.items()
        }
        
        # Update inverted index
        for term in unique_terms:
            self.inverted_index[term].add(doc_key)
        
        # Update IDF scores for new terms
        for term in unique_terms:
            if term not in self.idf_scores:
                # Count how many documents contain this term
                doc_freq = len(self.inverted_index[term])
                self.idf_scores[term] = math.log(self.N / doc_freq)
        
        # Recalculate average document length
        self.avg_doc_length = sum(self.doc_lengths.values()) / self.N
        
        # For efficiency, we could recalculate IDF scores for all terms periodically
        # rather than on every update, but this keeps things simple and correct
    
    async def update_document_async(self, doc_key: str, new_content: str):
        """
        Update or add a single document to the index efficiently
        """
        if not self.index_ready:
            raise RuntimeError("Index not ready. Call build_index_async() first.")
        
        logger.info(f"Updating document: {doc_key}")
        
        # Check if this is an update or insert
        is_update = doc_key in self.doc_keys
        
        # Remove old document data if updating
        if is_update:
            await self._remove_document_from_index(doc_key)
        else:
            # Add to document list for new documents
            self.doc_keys.append(doc_key)
            self.N += 1
        
        # Update documents dict
        self.documents[doc_key] = new_content
        
        # Process new content
        loop = asyncio.get_event_loop()
        doc_data = await loop.run_in_executor(
            self.executor,
            self._process_single_document,
            doc_key,
            new_content
        )
        
        # Update indexes with new data
        await self._integrate_document_data(doc_data, is_update)
        
        logger.info(f"Document {'updated' if is_update else 'added'}: {doc_key}")
    
    async def batch_update_documents_async(self, updates: Dict[str, str]):
        """Update multiple documents concurrently"""
        if not self.index_ready:
            raise RuntimeError("Index not ready. Call build_index_async() first.")
        
        logger.info(f"Batch updating {len(updates)} documents...")
        
        # Process all updates concurrently
        update_tasks = [
            self.update_document_async(doc_key, content)
            for doc_key, content in updates.items()
        ]
        
        await asyncio.gather(*update_tasks)
        logger.info(f"Batch update completed for {len(updates)} documents")
    
    async def remove_document_async(self, doc_key: str):
        """Remove a document from the index"""
        if not self.index_ready:
            raise RuntimeError("Index not ready. Call build_index_async() first.")
        
        if doc_key not in self.doc_keys:
            logger.warning(f"Document {doc_key} not found in index")
            return
        
        logger.info(f"Removing document: {doc_key}")
        
        # Remove from documents dict
        self.documents.pop(doc_key, None)
        
        # Remove from indexes
        await self._remove_document_from_index(doc_key)
        
        logger.info(f"Document removed: {doc_key}")
    
    async def incremental_rebuild_async(self, similarity_threshold: float = 0.8):
        """Smart incremental rebuild of the index"""
        if not self.index_ready:
            raise RuntimeError("Index not ready. Call build_index_async() first.")
        
        logger.info("Starting incremental rebuild...")
        
        # For now, we'll do a simple approach: recalculate IDF scores for all terms
        # In a more sophisticated implementation, we could track term frequency changes
        # and only recalculate when changes exceed the similarity threshold
        
        loop = asyncio.get_event_loop()
        
        # Recalculate term document frequencies
        term_doc_freq = defaultdict(int)
        for term, doc_set in self.inverted_index.items():
            term_doc_freq[term] = len(doc_set)
        
        # Recalculate IDF scores
        all_terms = set(self.idf_scores.keys())
        self.idf_scores = await loop.run_in_executor(
            self.executor,
            self._compute_idf_scores,
            all_terms,
            term_doc_freq
        )
        
        logger.info("Incremental rebuild completed")
    
    async def get_document_stats(self, doc_key: str) -> Dict:
        """Get statistics for a specific document"""
        if not self.index_ready:
            raise RuntimeError("Index not ready. Call build_index_async() first.")
        
        if doc_key not in self.doc_keys:
            return {'error': f'Document {doc_key} not found'}
        
        term_counts = self.doc_term_counts[doc_key]
        doc_length = self.doc_lengths[doc_key]
        
        return {
            'document_key': doc_key,
            'document_length': doc_length,
            'unique_terms': len(term_counts),
            'most_frequent_terms': term_counts.most_common(10),
            'tf_idf_top_terms': sorted([
                (term, self.tf_scores[doc_key][term] * self.idf_scores.get(term, 0))
                for term in term_counts.keys()
            ], key=lambda x: x[1], reverse=True)[:10]
        }
    
    async def search_async(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Async search with concurrent scoring of candidate documents
        """
        if not self.index_ready:
            raise RuntimeError("Index not ready. Call build_index_async() first.")
        
        # Tokenize query
        if not hasattr(self, '_token_pattern'):
            self._token_pattern = re.compile(r'\b\w+\b')
        
        query_terms = self._token_pattern.findall(query.lower())
        if not query_terms:
            return []
        
        # Get candidate documents using inverted index
        candidate_docs = set()
        query_term_counts = Counter(query_terms)
        
        for term in query_term_counts:
            if term in self.inverted_index:
                candidate_docs.update(self.inverted_index[term])
        
        if not candidate_docs:
            return []
        
        # Score candidates in parallel if we have many
        if len(candidate_docs) > 20:  # Only parallelize if worth it
            return await self._score_candidates_parallel(candidate_docs, query_term_counts, top_k)
        else:
            return await self._score_candidates_sequential(candidate_docs, query_term_counts, top_k)
    
    async def _score_candidates_parallel(self, candidate_docs: Set[str], query_term_counts: Counter, top_k: int) -> List[Tuple[str, float]]:
        """Score candidates in parallel"""
        loop = asyncio.get_event_loop()
        
        # Split candidates into chunks
        candidates_list = list(candidate_docs)
        chunk_size = max(1, len(candidates_list) // (self.max_workers or 4))
        chunks = [candidates_list[i:i + chunk_size] for i in range(0, len(candidates_list), chunk_size)]
        
        # Score each chunk in parallel
        scoring_tasks = [
            loop.run_in_executor(
                self.executor,
                self._score_chunk,
                chunk,
                query_term_counts
            )
            for chunk in chunks
        ]
        
        chunk_scores = await asyncio.gather(*scoring_tasks)
        
        # Merge all scores
        all_scores = {}
        for scores in chunk_scores:
            all_scores.update(scores)
        
        # Return top-k results
        if len(all_scores) > top_k * 3:
            import heapq
            return heapq.nlargest(top_k, all_scores.items(), key=lambda x: x[1])
        else:
            return sorted(all_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    
    async def _score_candidates_sequential(self, candidate_docs: Set[str], query_term_counts: Counter, top_k: int) -> List[Tuple[str, float]]:
        """Score candidates sequentially for small sets"""
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            self.executor,
            self._score_chunk,
            list(candidate_docs),
            query_term_counts
        )
        
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    
    def _score_chunk(self, doc_chunk: List[str], query_term_counts: Counter) -> Dict[str, float]:
        """Score a chunk of documents (runs in thread)"""
        scores = {}
        
        for doc_key in doc_chunk:
            doc_length = self.doc_lengths[doc_key]
            doc_term_counts = self.doc_term_counts[doc_key]
            
            bm25_score = 0.0
            tfidf_score = 0.0
            
            for term, query_count in query_term_counts.items():
                idf = self.idf_scores.get(term, 0)
                if idf == 0:
                    continue
                
                tf = doc_term_counts.get(term, 0)
                if tf == 0:
                    continue
                
                # BM25 calculation
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
                bm25_score += idf * (numerator / denominator)
                
                # TF-IDF calculation
                tf_normalized = self.tf_scores[doc_key].get(term, 0)
                tfidf_score += tf_normalized * idf * query_count
            
            # Combine scores
            combined_score = 0.7 * bm25_score + 0.3 * tfidf_score
            scores[doc_key] = combined_score
        
        return scores
    
    async def batch_search_async(self, queries: List[str], top_k: int = 10) -> List[List[Tuple[str, float]]]:
        """
        Search multiple queries concurrently
        """
        search_tasks = [self.search_async(query, top_k) for query in queries]
        return await asyncio.gather(*search_tasks)
    
    async def search_exact_match_async(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Async exact substring matching
        """
        loop = asyncio.get_event_loop()
        
        # Split documents for parallel processing
        doc_items = list(self.documents.items())
        chunk_size = max(1, len(doc_items) // (self.max_workers or 4))
        chunks = [doc_items[i:i + chunk_size] for i in range(0, len(doc_items), chunk_size)]
        
        # Process chunks in parallel
        match_tasks = [
            loop.run_in_executor(
                self.executor,
                self._exact_match_chunk,
                chunk,
                query.lower()
            )
            for chunk in chunks
        ]
        
        chunk_matches = await asyncio.gather(*match_tasks)
        
        # Merge results
        all_matches = []
        for matches in chunk_matches:
            all_matches.extend(matches)
        
        return sorted(all_matches, key=lambda x: x[1], reverse=True)[:top_k]
    
    def _exact_match_chunk(self, doc_chunk: List[Tuple[str, str]], query_lower: str) -> List[Tuple[str, float]]:
        """Process exact matching for a chunk of documents"""
        matches = []
        for doc_key, content in doc_chunk:
            content_lower = content.lower()
            if query_lower in content_lower:
                count = content_lower.count(query_lower)
                score = count / (len(content) + 1)
                matches.append((doc_key, score))
        return matches
    
    async def save_index_async(self, filepath: str):
        """Save pre-computed index to disk asynchronously"""
        if not self.index_ready:
            raise RuntimeError("Index not ready. Call build_index_async() first.")
        
        logger.info(f"Saving search index to {filepath}")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            self._save_index_sync,
            filepath
        )
        
        logger.info("Index saved successfully")
    
    def _save_index_sync(self, filepath: str):
        """Synchronous save operation (runs in thread)"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'tokenized_docs': self.tokenized_docs,
                'doc_lengths': self.doc_lengths,
                'doc_term_counts': self.doc_term_counts,
                'idf_scores': self.idf_scores,
                'tf_scores': self.tf_scores,
                'doc_keys': self.doc_keys,
                'N': self.N,
                'avg_doc_length': self.avg_doc_length,
                'inverted_index': dict(self.inverted_index)
            }, f)
    
    @classmethod
    async def load_index_async(cls, filepath: str, documents: Dict[str, str] = None, max_workers: Optional[int] = None):
        """Load pre-computed index from disk asynchronously"""
        logger.info(f"Loading search index from {filepath}")
        
        instance = cls.__new__(cls)
        instance.max_workers = max_workers
        instance.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            instance.executor,
            instance._load_index_sync,
            filepath
        )
        
        # Restore all pre-computed data
        instance.tokenized_docs = data['tokenized_docs']
        instance.doc_lengths = data['doc_lengths']
        instance.doc_term_counts = data['doc_term_counts']
        instance.idf_scores = data['idf_scores']
        instance.tf_scores = data['tf_scores']
        instance.doc_keys = data['doc_keys']
        instance.N = data['N']
        instance.avg_doc_length = data['avg_doc_length']
        instance.inverted_index = defaultdict(set, data['inverted_index'])
        
        # BM25 parameters
        instance.k1 = 1.5
        instance.b = 0.75
        
        instance.documents = documents or {}
        instance.index_ready = True
        
        logger.info(f"Index loaded: {instance.N} documents with {len(instance.idf_scores)} unique terms")
        return instance
    
    def _load_index_sync(self, filepath: str) -> Dict:
        """Synchronous load operation (runs in thread)"""
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    
    def get_stats(self) -> Dict:
        """Get index statistics"""
        if not self.index_ready:
            return {'status': 'Index not ready'}
        
        return {
            'total_documents': self.N,
            'total_unique_terms': len(self.idf_scores),
            'average_document_length': self.avg_doc_length,
            'max_workers': self.max_workers,
            'status': 'ready'
        }
    
    def __del__(self):
        """Clean up executor"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)

# Convenience wrapper for synchronous usage
class FastCodeSearchIndex:
    """Synchronous wrapper around AsyncFastCodeSearchIndex"""
    
    def __init__(self, documents: Dict[str, str], max_workers: Optional[int] = None):
        self.async_index = AsyncFastCodeSearchIndex(documents, max_workers)
        # Build index synchronously
        asyncio.run(self.async_index.build_index_async())
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        return asyncio.run(self.async_index.search_async(query, top_k))
    
    def batch_search(self, queries: List[str], top_k: int = 10) -> List[List[Tuple[str, float]]]:
        return asyncio.run(self.async_index.batch_search_async(queries, top_k))
    
    def search_exact_match(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        return asyncio.run(self.async_index.search_exact_match_async(query, top_k))
    
    def update_document(self, doc_key: str, new_content: str):
        """Update or add a single document"""
        return asyncio.run(self.async_index.update_document_async(doc_key, new_content))
    
    def batch_update_documents(self, updates: Dict[str, str]):
        """Update multiple documents concurrently"""
        return asyncio.run(self.async_index.batch_update_documents_async(updates))
    
    def remove_document(self, doc_key: str):
        """Remove a document from the index"""
        return asyncio.run(self.async_index.remove_document_async(doc_key))
    
    def incremental_rebuild(self, similarity_threshold: float = 0.8):
        """Smart incremental rebuild"""
        return asyncio.run(self.async_index.incremental_rebuild_async(similarity_threshold))
    
    def get_document_stats(self, doc_key: str) -> Dict:
        """Get statistics for a specific document"""
        return asyncio.run(self.async_index.get_document_stats(doc_key))
    
    def save_index(self, filepath: str):
        asyncio.run(self.async_index.save_index_async(filepath))
    
    @classmethod
    def load_index(cls, filepath: str, documents: Dict[str, str] = None, max_workers: Optional[int] = None):
        instance = cls.__new__(cls)
        instance.async_index = asyncio.run(
            AsyncFastCodeSearchIndex.load_index_async(filepath, documents, max_workers)
        )
        return instance
    
    def get_stats(self) -> Dict:
        return self.async_index.get_stats()

async def main():
    """Example usage with updates"""
    documents = {
        "examples.apply_patch.trim_to_patch_section": "function that trims patch sections and handles patch file modifications",
        "codetide.parsers.python_parser.PythonParser": "class for parsing python files and extracting code structure",
        "codetide.agents.tide.defaults.DEFAULT_AGENT_TIDE_LLM_CONFIG_PATH": "default configuration path for tide agent llm settings",
        "examples.aicore_dashboard.od": "object detection dashboard example implementation"
    }

    # Build initial index
    logger.info("=== BUILDING INITIAL INDEX ===")
    search_index = AsyncFastCodeSearchIndex(documents, max_workers=4)
    await search_index.build_index_async()
    
    # Test initial search
    logger.info("Initial search test:")
    results = await search_index.search_async("python parser", top_k=2)
    for doc_key, score in results:
        logger.info(f"  {score:.3f}: {doc_key}")
    
    # Update existing document
    logger.info("\n=== UPDATING EXISTING DOCUMENT ===")
    await search_index.update_document_async(
        "codetide.parsers.python_parser.PythonParser",
        "advanced class for parsing python files, extracting AST, and analyzing code structure with type hints"
    )
    
    # Add new document
    logger.info("\n=== ADDING NEW DOCUMENT ===")
    await search_index.update_document_async(
        "codetide.search.fast_search.FastSearchEngine",
        "high performance search engine using BM25 and TF-IDF for code retrieval"
    )
    
    # Test search after updates
    logger.info("\nSearch after updates:")
    results = await search_index.search_async("python parser", top_k=3)
    for doc_key, score in results:
        logger.info(f"  {score:.3f}: {doc_key}")
    
    # Batch update multiple documents
    logger.info("\n=== BATCH UPDATE ===")
    updates = {
        "examples.apply_patch.trim_to_patch_section": "enhanced function for trimming patch sections with better error handling",
        "new.module.data_processor": "module for processing and transforming data with advanced algorithms",
        "new.module.cache_manager": "efficient cache management system with LRU eviction policy"
    }
    
    await search_index.batch_update_documents_async(updates)
    
    # Test batch search
    logger.info("\nBatch search test:")
    queries = ["python parser", "patch trim", "cache manager", "data processor"]
    batch_results = await search_index.batch_search_async(queries, top_k=2)
    
    for query, results in zip(queries, batch_results):
        logger.info(f"\nQuery: '{query}'")
        for doc_key, score in results:
            logger.info(f"  {score:.3f}: {doc_key}")
    
    # Show final stats
    logger.info("\n=== FINAL STATS ===")
    stats = search_index.get_stats()
    logger.info(f"Final index stats: {stats}")
    
    # Test document removal
    logger.info("\n=== REMOVING DOCUMENT ===")
    await search_index.remove_document_async("examples.aicore_dashboard.od")
    
    final_stats = search_index.get_stats()
    logger.info(f"Stats after removal: {final_stats}")
    
    # Test incremental rebuild
    logger.info("\n=== INCREMENTAL REBUILD ===")
    await search_index.incremental_rebuild_async()
    
    # Save updated index
    await search_index.save_index_async("updated_index.pkl")
    logger.info("Updated index saved!")

    # # Sync wrapper usage example
    # logger.info("\n=== SYNC WRAPPER EXAMPLE ===")
    # sync_index = FastCodeSearchIndex({"test.doc": "test content"})
    # sync_index.update_document("test.doc", "updated test content")
    # sync_index.update_document("new.doc", "brand new content")
    
    # results = sync_index.search("test content")
    # logger.info("Sync wrapper results:")
    # for doc_key, score in results:
    #     logger.info(f"  {score:.3f}: {doc_key}")

if __name__ == "__main__":
    asyncio.run(main())