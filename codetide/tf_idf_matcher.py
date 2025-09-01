from collections import defaultdict
from typing import List, Optional, Tuple
import re

class TfIdfFastMatcher:
    """
    Even faster implementation using only exact matching + fuzzy scoring.
    Good for when you have 10k+ files and need microsecond inference.
    """
    
    def __init__(self):
        self.filepaths = []
        self.path_tokens = []  # Pre-extracted tokens for each path
        self.token_to_paths = defaultdict(set)  # inverted index
        
    def _extract_tokens(self, text: str) -> set:
        """Extract searchable tokens"""
        # CamelCase splitting
        text = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
        
        # Split on separators
        tokens = set()
        parts = re.split(r'[/\\_\-\.]', text.lower())
        
        for part in parts:
            if len(part) >= 2:
                tokens.add(part)
                
                # Add prefixes for partial matching
                if len(part) >= 4:
                    for i in range(2, min(len(part), 6)):
                        tokens.add(part[:i])
        
        return tokens
    
    def fit(self, filepaths: List[str]):
        """Build inverted index"""
        self.filepaths = filepaths
        self.path_tokens = []
        self.token_to_paths = defaultdict(set)
        
        for i, filepath in enumerate(filepaths):
            tokens = self._extract_tokens(filepath)
            self.path_tokens.append(tokens)
            
            # Build inverted index
            for token in tokens:
                self.token_to_paths[token].add(i)
    
    def predict_scores(self, query: str) -> List[Tuple[str, float]]:
        """Ultra-fast scoring using inverted index"""
        query_tokens = self._extract_tokens(query)
        
        # Find candidate files using inverted index
        candidates = set()
        for token in query_tokens:
            if token in self.token_to_paths:
                candidates.update(self.token_to_paths[token])
        
        # Score only candidates
        results = []
        query_len = len(query_tokens)
        
        for i in candidates:
            path_tokens = self.path_tokens[i]
            
            # Jaccard similarity + exact match bonus
            intersection = len(query_tokens.intersection(path_tokens))
            union = len(query_tokens.union(path_tokens))
            jaccard = intersection / union if union > 0 else 0
            
            # Bonus for exact token matches
            exact_matches = sum(1 for token in query_tokens if token in path_tokens)
            exact_bonus = exact_matches / query_len if query_len > 0 else 0
            
            # Combined score
            score = 0.6 * jaccard + 0.4 * exact_bonus
            
            results.append((self.filepaths[i], score))
        
        # Add non-candidates with 0 score if needed
        for i, filepath in enumerate(self.filepaths):
            if i not in candidates:
                results.append((filepath, 0.0))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_filepaths(self, query :str, top_k :Optional[int]=None, threshold :float=0.1)->List[str]:
        results = self.predict_scores(query)
        results = [
            filepath for filepath, score in results
            if score > threshold
        ]
        return results if top_k is None else results[:top_k]

# Benchmark and example usage
if __name__ == "__main__":
    import time
    
    # Sample data
    filepaths = [
        "src/components/auth/LoginForm.js",
        "src/services/auth.js", 
        "src/models/User.py",
        "src/components/ui/Button.js",
        "src/utils/validation.js",
        "src/pages/admin/UserManagement.js",
        "backend/auth/authentication_service.py",
        "frontend/components/LoginModal.tsx",
        "src/hooks/useAuth.js",
        "tests/auth/login.test.js"
    ]
    
    queries = [
        "authentication logic in frontend",
        "user management admin",
        "login form component",
        "validation utils"
    ]
    
    
    ultra_matcher = TfIdfFastMatcher()
    
    start = time.time()
    ultra_matcher.fit(filepaths)
    train_time = time.time() - start
    print(f"Training time: {train_time*1000:.1f}ms")
    
    total_inference = 0
    for query in queries:
        start = time.time()
        results = ultra_matcher.predict_scores(query)[:5]
        inference_time = time.time() - start
        total_inference += inference_time
        
        print(f"\nQuery: '{query}'")
        print(f"Inference time: {inference_time*1000:.1f}ms")
        for filepath, score in results:
            print(f"  {score:.3f}: {filepath}")
    
    print(f"\nAvg inference time: {(total_inference/len(queries))*1000:.1f}ms")