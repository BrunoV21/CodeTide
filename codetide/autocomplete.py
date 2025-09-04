from typing import List
import difflib
import os

class AutoComplete:
    def __init__(self, word_list: List[str]) -> None:
        """Initialize with a list of strings to search from"""
        self.words = word_list
        # Sort words for better organization (optional)
        self.words.sort()
    
    def get_suggestions(self, prefix: str, max_suggestions: int = 10, case_sensitive: bool = False) -> List[str]:
        """
        Get autocomplete suggestions based on prefix
        
        Args:
            prefix (str): The text to search for
            max_suggestions (int): Maximum number of suggestions to return
            case_sensitive (bool): Whether matching should be case sensitive
        
        Returns:
            list: List of matching suggestions
        """
        if not prefix:
            return []
        
        suggestions = []
        search_prefix = prefix if case_sensitive else prefix.lower()
        
        for word in self.words:
            search_word = word if case_sensitive else word.lower()
            
            if search_word.startswith(search_prefix):
                suggestions.append(word)
                
                # Stop when we reach max suggestions
                if len(suggestions) >= max_suggestions:
                    break
        
        return suggestions
    
    def get_fuzzy_suggestions(self, prefix: str, max_suggestions: int = 10, case_sensitive: bool = False) -> List[str]:
        """
        Get suggestions that contain the prefix anywhere in the string
        
        Args:
            prefix (str): The text to search for
            max_suggestions (int): Maximum number of suggestions to return
            case_sensitive (bool): Whether matching should be case sensitive
        
        Returns:
            list: List of matching suggestions
        """
        if not prefix:
            return []
        
        suggestions = []
        search_prefix = prefix if case_sensitive else prefix.lower()
        
        for word in self.words:
            search_word = word if case_sensitive else word.lower()
            
            if search_prefix in search_word:
                suggestions.append(word)
                
                if len(suggestions) >= max_suggestions:
                    break
        
        return suggestions
    
    def validate_code_identifier(self, code_identifier, max_suggestions=5, case_sensitive=False):
        """
        Validate a code identifier and return similar matches if not found
        
        Args:
            code_identifier (str): The code identifier to validate
            max_suggestions (int): Maximum number of similar suggestions to return
            case_sensitive (bool): Whether matching should be case sensitive
        
        Returns:
            dict: Dictionary with validation result
        """
        if not code_identifier:
            return {
                "code_identifier": code_identifier,
                "is_valid": False,
                "matching_identifiers": []
            }
        
        # Check for perfect match
        search_word = code_identifier if case_sensitive else code_identifier.lower()
        words_to_check = self.words if case_sensitive else [word.lower() for word in self.words]
        
        if search_word in words_to_check:
            return {
                "code_identifier": code_identifier,
                "is_valid": True,
                "matching_identifiers": []
            }
        
        # If not perfect match, find most similar ones using difflib
        # Get close matches using sequence matching
        close_matches = difflib.get_close_matches(
            code_identifier, 
            self.words, 
            n=max_suggestions, 
            cutoff=0.3  # Minimum similarity threshold
        )
        
        # If we don't have enough close matches, supplement with fuzzy matches
        if len(close_matches) < max_suggestions:
            fuzzy_matches = self.get_fuzzy_suggestions(
                code_identifier, 
                max_suggestions * 2,  # Get more to filter
                case_sensitive
            )
            
            # Add fuzzy matches that aren't already in close_matches
            for match in fuzzy_matches:
                if match not in close_matches and len(close_matches) < max_suggestions:
                    close_matches.append(match)
        
        # Sort by similarity score (difflib ratio)
        if close_matches:
            similarity_scores = []
            for match in close_matches:
                score = difflib.SequenceMatcher(None, code_identifier, match).ratio()
                similarity_scores.append((match, score))
            
            # Sort by score descending (most similar first)
            similarity_scores.sort(key=lambda x: x[1], reverse=True)
            close_matches = [match for match, score in similarity_scores[:max_suggestions]]
        
        return {
            "code_identifier": code_identifier,
            "is_valid": False,
            "matching_identifiers": close_matches
        }
    
    def validate_paths(self, file_paths):
        """
        Validate a list of file paths. For each path, check if it is valid; if not, try to match it to a valid one using autocomplete logic.
        Args:
            file_paths (list of str): List of file paths to validate.
        Returns:
            list of str: List of valid file paths (matched or original).
        Raises:
            ValueError: If a path cannot be matched to a valid entry.
        """
        valid_paths = []
        valid_set = set(self.words)
        for path in file_paths:
            # Direct match
            if path in valid_set:
                valid_paths.append(path)
                continue
            # Try normalization: replace '.' with os.sep, strip leading/trailing spaces
            normalized = path.replace('.', os.sep).replace('\\', os.sep).replace('/', os.sep).strip()
            # Try to match normalized path
            if normalized in valid_set:
                valid_paths.append(normalized)
                continue
                
            # Try to find close matches using autocomplete logic
            suggestions = []
            if hasattr(self, "get_fuzzy_suggestions"):
                suggestions = self.get_fuzzy_suggestions(path, 1)
                if not suggestions:
                    raise ValueError(f"Invalid file path: '{path}'")
        return valid_paths