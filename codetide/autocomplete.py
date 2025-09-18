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
    
    def extract_words_from_text(
        self,
        text: str,
        similarity_threshold: float = 0.6,
        case_sensitive: bool = False,
        max_matches_per_word: int = None,
        preserve_dotted_identifiers: bool = True
    ) -> dict:
        """
        Extract words from the word list that are present in the given text, including similar words (potential typos).
        Optionally limit the number of matches returned per word found in the text.

        Args:
            text (str): The input text to analyze
            similarity_threshold (float): Minimum similarity score for fuzzy matching (0.0 to 1.0)
            case_sensitive (bool): Whether matching should be case sensitive
            max_matches_per_word (int, optional): Maximum number of matches to return per word in the text.
                If None, all matches are returned. If 1, only the top match per word is returned.
            preserve_dotted_identifiers (bool): If True, treats dot-separated strings as single tokens
                (e.g., "module.submodule.function" stays as one word)

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

        # Extract words from text - handle dotted identifiers
        if preserve_dotted_identifiers:
            # Match word characters, dots, and underscores as single tokens
            # This will capture things like "module.submodule.function" as one word
            text_words = re.findall(r'\b[\w.]+\b', text)
        else:
            # Original behavior - split on non-word characters
            text_words = re.findall(r'\b\w+\b', text)
        
        if not text_words:
            return {
                'exact_matches': [],
                'fuzzy_matches': [],
                'all_found_words': []
            }

        exact_matches = []
        fuzzy_candidates = []
        all_found_words = set()

        # Convert to appropriate case for comparison
        if case_sensitive:
            text_words_set = set(text_words)
            text_words_search = text_words
        else:
            text_words_set = set(word.lower() for word in text_words)
            text_words_search = [word.lower() for word in text_words]

        # Find exact matches first
        for word_from_list in self.words:
            if word_from_list in all_found_words:
                continue
                
            search_word = word_from_list if case_sensitive else word_from_list.lower()
            
            if search_word in text_words_set:
                exact_matches.append(word_from_list)
                all_found_words.add(word_from_list)

        # Find fuzzy matches for words that didn't match exactly
        remaining_words = [word for word in self.words if word not in all_found_words]
        
        for word_from_list in remaining_words:
            search_word = word_from_list if case_sensitive else word_from_list.lower()
            
            # Find all potential matches with their similarity scores
            for i, text_word in enumerate(text_words_search):
                similarity = difflib.SequenceMatcher(None, search_word, text_word).ratio()
                if similarity >= similarity_threshold:
                    # Get the original case text word
                    original_text_word = text_words[i] if case_sensitive else next(
                        (orig for orig in text_words if orig.lower() == text_word), text_word
                    )
                    fuzzy_candidates.append((word_from_list, original_text_word, similarity))

        # Remove duplicates and sort by similarity score (highest first)
        # Use a dict to keep only the best match per word_from_list
        best_fuzzy_matches = {}
        for word_from_list, text_word, score in fuzzy_candidates:
            if word_from_list not in best_fuzzy_matches or score > best_fuzzy_matches[word_from_list][2]:
                best_fuzzy_matches[word_from_list] = (word_from_list, text_word, score)
        
        # Convert back to list and sort by score
        fuzzy_matches = list(best_fuzzy_matches.values())
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)
        
        # Add fuzzy matches to all_found_words
        for word_from_list, _, _ in fuzzy_matches:
            all_found_words.add(word_from_list)

        # Apply max_matches_per_word limit AFTER finding the best matches
        if max_matches_per_word is not None:
            # Combine exact and fuzzy matches, prioritizing exact matches
            all_matches = [(word, 'exact', 1.0) for word in exact_matches] + \
                        [(word, 'fuzzy', score) for word, text_word, score in fuzzy_matches]
            
            # Sort by type (exact first) then by score
            all_matches.sort(key=lambda x: (x[1] != 'exact', -x[2]))
            
            # Take only the top matches
            top_matches = all_matches[:max_matches_per_word]
            
            # Rebuild the lists
            exact_matches = [word for word, match_type, _ in top_matches if match_type == 'exact']
            fuzzy_matches = [(word, next(text_word for w, text_word, _ in fuzzy_matches if w == word), score) 
                            for word, match_type, score in top_matches if match_type == 'fuzzy']
            all_found_words = set(word for word, _, _ in top_matches)

        # Sort results
        exact_matches.sort()
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)

        return {
            'exact_matches': exact_matches,
            'fuzzy_matches': fuzzy_matches,
            'all_found_words': sorted(list(all_found_words))
        }

        # Sort results
        exact_matches.sort()
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)  # Sort by similarity score

        return {
            'exact_matches': exact_matches,
            'fuzzy_matches': fuzzy_matches,
            'all_found_words': sorted(list(all_found_words))
        }
