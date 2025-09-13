from typing import List
import difflib
import os
import re

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
    
    def extract_words_from_text(self, text: str, similarity_threshold: float = 0.6, case_sensitive: bool = False) -> dict:
        """
        Extract words from the word list that are present in the given text, including similar words (potential typos).
        
        Args:
            text (str): The input text to analyze
            similarity_threshold (float): Minimum similarity score for fuzzy matching (0.0 to 1.0)
            case_sensitive (bool): Whether matching should be case sensitive
        
        Returns:
            dict: Dictionary containing:
                - 'exact_matches': List of words found exactly in the text
                - 'fuzzy_matches': List of tuples (word_from_list, similar_word_in_text, similarity_score)
                - 'all_found_words': Combined list of all matched words from the word list
        """
        if not text:
            return {
                'exact_matches': [],
                'fuzzy_matches': [],
                'all_found_words': []
            }
        
        # Split text into words (remove punctuation and split by whitespace)
        text_words = re.findall(r'\b\w+\b', text)
        
        exact_matches = []
        fuzzy_matches = []
        all_found_words = set()
        
        # Convert to appropriate case for comparison
        if case_sensitive:
            text_words_search = text_words
            word_list_search = self.words
        else:
            text_words_search = [word.lower() for word in text_words]
            word_list_search = [word.lower() for word in self.words]
        
        # Find exact matches
        for i, text_word in enumerate(text_words_search):
            for j, list_word in enumerate(word_list_search):
                if text_word == list_word:
                    original_word = self.words[j]
                    if original_word not in all_found_words:
                        exact_matches.append(original_word)
                        all_found_words.add(original_word)
        
        # Find fuzzy matches for words that didn't match exactly
        matched_text_words = set()
        for match in exact_matches:
            search_match = match if case_sensitive else match.lower()
            for i, text_word in enumerate(text_words_search):
                if text_word == search_match:
                    matched_text_words.add(i)
        
        # Check remaining text words for fuzzy matches
        for i, text_word in enumerate(text_words_search):
            if i in matched_text_words:
                continue
                
            # Find the most similar word from our word list
            best_matches = []
            for j, list_word in enumerate(word_list_search):
                similarity = difflib.SequenceMatcher(None, text_word, list_word).ratio()
                if similarity >= similarity_threshold:
                    best_matches.append((self.words[j], text_words[i], similarity))
            
            # Sort by similarity and add to results
            if best_matches:
                best_matches.sort(key=lambda x: x[2], reverse=True)
                for match in best_matches:
                    word_from_list, word_in_text, score = match
                    if word_from_list not in all_found_words:
                        fuzzy_matches.append((word_from_list, word_in_text, score))
                        all_found_words.add(word_from_list)
        
        # Sort results
        exact_matches.sort()
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)  # Sort by similarity score
        
        return {
            'exact_matches': exact_matches,
            'fuzzy_matches': fuzzy_matches,
            'all_found_words': sorted(list(all_found_words))
        }