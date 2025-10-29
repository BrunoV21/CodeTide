from typing import List
import difflib
import asyncio
import os
import re
import time

class AutoComplete:
    def __init__(self, word_list: List[str]) -> None:
        """Initialize with a list of strings to search from"""
        self.words = word_list
        self._sorted = False
        # Sort words for better organization (optional)

    def sort(self):
        if not self._sorted:
            self._sorted = True
            self.words.sort()

    async def async_sort(self):
        if not self._sorted:
            self._sorted = True
            loop = asyncio.get_running_loop()
            # Offload sorting to a background thread
            self.words = await loop.run_in_executor(None, sorted, self.words)
    
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
        Extract words from the word list that are present in the given text, including similar words (potential typos)
        and substring/subpath matches.
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
                - 'substring_matches': List of tuples (word_from_list, matched_text_word, match_type)
                - 'all_found_words': Combined list of all matched words from the word list
        """        
        if not text:
            return {
                'exact_matches': [],
                'fuzzy_matches': [],
                'substring_matches': [],
                'all_found_words': []
            }
        
        self.sort()

        # Extract words from text - handle dotted identifiers
        if preserve_dotted_identifiers:
            # Match word characters, dots, underscores, and forward slashes as single tokens
            # This will capture things like "module.submodule.function" and "path/to/file.ext" as one word
            text_words = re.findall(r'\b[\w./]+\b', text)
        else:
            # Original behavior - split on non-word characters
            text_words = re.findall(r'\b\w+\b', text)
        
        if not text_words:
            return {
                'exact_matches': [],
                'fuzzy_matches': [],
                'substring_matches': [],
                'all_found_words': []
            }

        exact_matches = []
        fuzzy_candidates = []
        substring_matches = []
        all_found_words = set()
        matched_text_words = set()  # Track which text words have been matched

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
                # Mark all instances of this text word as matched
                for tw in text_words:
                    tw_search = tw if case_sensitive else tw.lower()
                    if tw_search == search_word:
                        matched_text_words.add(tw)

        # Find substring/subpath matches for words that didn't match exactly
        remaining_words = [word for word in self.words if word not in all_found_words]
        
        def is_valid_path_substring(longer_path, shorter_path):
            """Check if shorter_path is a valid subpath of longer_path"""
            if not ('/' in longer_path and '/' in shorter_path):
                return False
                
            # Must have meaningful length (at least 3 characters and contain a slash)
            if len(shorter_path) < 3:
                return False
                
            longer_parts = longer_path.split('/')
            shorter_parts = shorter_path.split('/')
            
            # Don't match single character parts or very short parts
            if any(len(part) <= 1 for part in shorter_parts):
                return False
            
            # Check if shorter_parts is a contiguous subsequence of longer_parts
            if len(shorter_parts) > len(longer_parts):
                return False
                
            for start_idx in range(len(longer_parts) - len(shorter_parts) + 1):
                if longer_parts[start_idx:start_idx + len(shorter_parts)] == shorter_parts:
                    return True
            return False
        
        def is_valid_substring(longer_str, shorter_str):
            """Check if shorter_str is a valid substring of longer_str (non-path case)"""
            # Must be at least 4 characters for non-path substrings
            if len(shorter_str) < 4:
                return False
            # Don't match very short strings or single words
            if len(shorter_str) / len(longer_str) < 0.3:  # At least 30% of the longer string
                return False
            return shorter_str in longer_str
        
        # Collect all potential substring matches first, then pick the best ones
        substring_candidates = []
        
        for word_from_list in remaining_words:
            search_word = word_from_list if case_sensitive else word_from_list.lower()
            
            # Check for substring matches
            for i, text_word in enumerate(text_words_search):
                original_text_word = text_words[i]
                
                # Skip if this text word has already been matched
                if original_text_word in matched_text_words:
                    continue
                    
                # Skip very short text words that are likely to cause false positives
                if len(text_word) <= 2:
                    continue
                
                # Case 1: text_word is a substring/subpath of word_from_list
                if text_word in search_word and text_word != search_word:
                    if '/' in search_word and '/' in text_word:
                        if is_valid_path_substring(search_word, text_word):
                            # Calculate a score based on how much of the path matches
                            score = len(text_word) / len(search_word)
                            substring_candidates.append((word_from_list, original_text_word, 'subpath', score))
                    elif is_valid_substring(search_word, text_word):
                        score = len(text_word) / len(search_word)
                        substring_candidates.append((word_from_list, original_text_word, 'substring', score))
                
                # Case 2: word_from_list is a substring/subpath of text_word
                elif search_word in text_word and search_word != text_word:
                    if '/' in search_word and '/' in text_word:
                        if is_valid_path_substring(text_word, search_word):
                            score = len(search_word) / len(text_word)
                            substring_candidates.append((word_from_list, original_text_word, 'reverse_subpath', score))
                    elif is_valid_substring(text_word, search_word):
                        score = len(search_word) / len(text_word)
                        substring_candidates.append((word_from_list, original_text_word, 'reverse_substring', score))

        # Sort substring candidates by score (higher is better) and select the best matches
        # ensuring each text word is only matched once
        substring_candidates.sort(key=lambda x: x[3], reverse=True)
        
        for word_from_list, original_text_word, match_type, score in substring_candidates:
            if original_text_word not in matched_text_words and word_from_list not in all_found_words:
                substring_matches.append((word_from_list, original_text_word, match_type))
                all_found_words.add(word_from_list)
                matched_text_words.add(original_text_word)

        # Find fuzzy matches for words that didn't match exactly or as substrings
        remaining_words = [word for word in self.words if word not in all_found_words]
        
        for word_from_list in remaining_words:
            search_word = word_from_list if case_sensitive else word_from_list.lower()
            
            # Find all potential matches with their similarity scores
            for i, text_word in enumerate(text_words_search):
                original_text_word = text_words[i]
                
                # Skip if this text word has already been matched
                if original_text_word in matched_text_words:
                    continue
                    
                similarity = difflib.SequenceMatcher(None, search_word, text_word).ratio()
                if similarity >= similarity_threshold:
                    # Get the original case text word
                    original_text_word = text_words[i] if case_sensitive else next(
                        (orig for orig in text_words if orig.lower() == text_word), text_word
                    )
                    fuzzy_candidates.append((word_from_list, original_text_word, similarity))

        # Remove duplicates and sort by similarity score (highest first)
        # Use a dict to keep only the best match per word_from_list, ensuring each text word is matched only once
        best_fuzzy_matches = {}
        used_text_words = set()
        
        # Sort fuzzy candidates by similarity score first
        fuzzy_candidates.sort(key=lambda x: x[2], reverse=True)
        
        for word_from_list, text_word, score in fuzzy_candidates:
            if (word_from_list not in best_fuzzy_matches and 
                text_word not in used_text_words and 
                text_word not in matched_text_words):
                best_fuzzy_matches[word_from_list] = (word_from_list, text_word, score)
                used_text_words.add(text_word)
        
        # Convert back to list and sort by score
        fuzzy_matches = list(best_fuzzy_matches.values())
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)
        
        # Add fuzzy matches to all_found_words
        for word_from_list, _, _ in fuzzy_matches:
            all_found_words.add(word_from_list)

        # Apply max_matches_per_word limit AFTER finding the best matches
        if max_matches_per_word is not None:
            # Group matches by word from list and apply limit per word
            final_exact_matches = []
            final_substring_matches = []
            final_fuzzy_matches = []
            final_all_found_words = set()
            
            # Get all unique words that had matches
            all_matched_words = set(exact_matches) | set(word for word, _, _ in substring_matches) | set(word for word, _, _ in fuzzy_matches)
            
            for word_from_list in all_matched_words:
                # Collect all matches for this specific word, with type priority
                word_matches = []
                
                # Add exact match if exists (priority 0)
                if word_from_list in exact_matches:
                    word_matches.append((word_from_list, 'exact', 1.0, 0))
                
                # Add substring matches (priority 1)
                for w, text_word, match_type in substring_matches:
                    if w == word_from_list:
                        # Use a score based on match type and coverage
                        score = 0.9 if match_type in ['subpath', 'substring'] else 0.85
                        word_matches.append((w, 'substring', score, 1, text_word, match_type))
                
                # Add fuzzy matches (priority 2)
                for w, text_word, score in fuzzy_matches:
                    if w == word_from_list:
                        word_matches.append((w, 'fuzzy', score, 2, text_word))
                
                # Sort by priority (lower is better) then by score (higher is better)
                word_matches.sort(key=lambda x: (x[3], -x[2]))
                
                # Take only the top matches for this word
                top_word_matches = word_matches[:max_matches_per_word]
                
                # Add to final results
                for match in top_word_matches:
                    final_all_found_words.add(match[0])
                    
                    if match[1] == 'exact':
                        final_exact_matches.append(match[0])
                    elif match[1] == 'substring':
                        final_substring_matches.append((match[0], match[4], match[5]))
                    elif match[1] == 'fuzzy':
                        final_fuzzy_matches.append((match[0], match[4], match[2]))
            
            # Update the results
            exact_matches = final_exact_matches
            substring_matches = final_substring_matches
            fuzzy_matches = final_fuzzy_matches
            all_found_words = final_all_found_words

        # Sort results
        exact_matches.sort()
        substring_matches.sort(key=lambda x: x[0])  # Sort by word_from_list
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)

        return {
            'exact_matches': exact_matches,
            'fuzzy_matches': fuzzy_matches,
            'substring_matches': substring_matches,
            'all_found_words': sorted(list(all_found_words))
        }

    async def async_extract_words_from_text(
        self,
        text: str,
        similarity_threshold: float = 0.6,
        case_sensitive: bool = False,
        max_matches_per_word: int = None,
        preserve_dotted_identifiers: bool = True,
        timeout: float = None
    ) -> dict:
        """
        Async non-blocking version of extract_words_from_text.
        Extract words from the word list that are present in the given text, including similar words (potential typos)
        and substring/subpath matches.
        Optionally limit the number of matches returned per word found in the text.

        Args:
            text (str): The input text to analyze
            similarity_threshold (float): Minimum similarity score for fuzzy matching (0.0 to 1.0)
            case_sensitive (bool): Whether matching should be case sensitive
            max_matches_per_word (int, optional): Maximum number of matches to return per word in the text.
                If None, all matches are returned. If 1, only the top match per word is returned.
            preserve_dotted_identifiers (bool): If True, treats dot-separated strings as single tokens
                (e.g., "module.submodule.function" stays as one word)
            timeout (float, optional): Maximum time in seconds to spend searching for matches.
                If None, no timeout is applied. If exceeded, returns matches found so far.

        Returns:
            dict: Dictionary containing:
                - 'exact_matches': List of words found exactly in the text
                - 'fuzzy_matches': List of tuples (word_from_list, similar_word_in_text, similarity_score)
                - 'substring_matches': List of tuples (word_from_list, matched_text_word, match_type)
                - 'all_found_words': Combined list of all matched words from the word list
        """
        if not text:
            return {
                'exact_matches': [],
                'fuzzy_matches': [],
                'substring_matches': [],
                'all_found_words': []
            }
         
        start_time = time.time() if timeout is not None else None
        
        await self.async_sort()

        if preserve_dotted_identifiers:
            text_words = re.findall(r'\b[\w./]+\b', text)
        else:
            text_words = re.findall(r'\b\w+\b', text)
        
        if not text_words:
            return {
                'exact_matches': [],
                'fuzzy_matches': [],
                'substring_matches': [],
                'all_found_words': []
            }

        exact_matches = []
        fuzzy_candidates = []
        substring_matches = []
        all_found_words = set()
        matched_text_words = set()

        if case_sensitive:
            text_words_set = set(text_words)
            text_words_search = text_words
        else:
            text_words_set = set(word.lower() for word in text_words)
            text_words_search = [word.lower() for word in text_words]

        chunk_size = max(1, len(self.words) // 100)
        for i in range(0, len(self.words), chunk_size):
            if start_time is not None and (time.time() - start_time) >= timeout:
                break
 
            chunk = self.words[i:i + chunk_size]
            
            for word_from_list in chunk:
                if word_from_list in all_found_words:
                    continue
                    
                search_word = word_from_list if case_sensitive else word_from_list.lower()
                
                if search_word in text_words_set:
                    exact_matches.append(word_from_list)
                    all_found_words.add(word_from_list)
                    for tw in text_words:
                        tw_search = tw if case_sensitive else tw.lower()
                        if tw_search == search_word:
                            matched_text_words.add(tw)
            
            await asyncio.sleep(0)

        remaining_words = [word for word in self.words if word not in all_found_words]
        
        def is_valid_path_substring(longer_path, shorter_path):
            if not ('/' in longer_path and '/' in shorter_path):
                return False
                
            if len(shorter_path) < 3:
                return False
                
            longer_parts = longer_path.split('/')
            shorter_parts = shorter_path.split('/')
            
            if any(len(part) <= 1 for part in shorter_parts):
                return False
            
            if len(shorter_parts) > len(longer_parts):
                return False
                
            for start_idx in range(len(longer_parts) - len(shorter_parts) + 1):
                if longer_parts[start_idx:start_idx + len(shorter_parts)] == shorter_parts:
                    return True
            return False
        
        def is_valid_substring(longer_str, shorter_str):
            if len(shorter_str) < 4:
                return False
            if len(shorter_str) / len(longer_str) < 0.3:
                return False
            return shorter_str in longer_str
        
        substring_candidates = []
        
        chunk_size = max(1, len(remaining_words) // 100)
        for i in range(0, len(remaining_words), chunk_size):
            if start_time is not None and (time.time() - start_time) >= timeout:
                break

            if start_time is not None and (time.time() - start_time) >= timeout:
                break
 
            chunk = remaining_words[i:i + chunk_size]
            
            for word_from_list in chunk:
                search_word = word_from_list if case_sensitive else word_from_list.lower()
                
                for idx, text_word in enumerate(text_words_search):
                    original_text_word = text_words[idx]
                    
                    if original_text_word in matched_text_words:
                        continue
                        
                    if len(text_word) <= 2:
                        continue
                    
                    if text_word in search_word and text_word != search_word:
                        if '/' in search_word and '/' in text_word:
                            if is_valid_path_substring(search_word, text_word):
                                score = len(text_word) / len(search_word)
                                substring_candidates.append((word_from_list, original_text_word, 'subpath', score))
                        elif is_valid_substring(search_word, text_word):
                            score = len(text_word) / len(search_word)
                            substring_candidates.append((word_from_list, original_text_word, 'substring', score))
                    
                    elif search_word in text_word and search_word != text_word:
                        if '/' in search_word and '/' in text_word:
                            if is_valid_path_substring(text_word, search_word):
                                score = len(search_word) / len(text_word)
                                substring_candidates.append((word_from_list, original_text_word, 'reverse_subpath', score))
                        elif is_valid_substring(text_word, search_word):
                            score = len(search_word) / len(text_word)
                            substring_candidates.append((word_from_list, original_text_word, 'reverse_substring', score))
            
            await asyncio.sleep(0)

        substring_candidates.sort(key=lambda x: x[3], reverse=True)
        
        for word_from_list, original_text_word, match_type, score in substring_candidates:
            if original_text_word not in matched_text_words and word_from_list not in all_found_words:
                substring_matches.append((word_from_list, original_text_word, match_type))
                all_found_words.add(word_from_list)
                matched_text_words.add(original_text_word)

        remaining_words = [word for word in self.words if word not in all_found_words]
        
        chunk_size = max(1, len(remaining_words) // 100)
        for i in range(0, len(remaining_words), chunk_size):
            chunk = remaining_words[i:i + chunk_size]
            
            for word_from_list in chunk:
                search_word = word_from_list if case_sensitive else word_from_list.lower()
                
                for idx, text_word in enumerate(text_words_search):
                    original_text_word = text_words[idx]
                    
                    if original_text_word in matched_text_words:
                        continue
                        
                    similarity = difflib.SequenceMatcher(None, search_word, text_word).ratio()
                    if similarity >= similarity_threshold:
                        original_text_word = text_words[idx] if case_sensitive else next(
                            (orig for orig in text_words if orig.lower() == text_word), text_word
                        )
                        fuzzy_candidates.append((word_from_list, original_text_word, similarity))
            
            await asyncio.sleep(0)

        best_fuzzy_matches = {}
        used_text_words = set()
        
        fuzzy_candidates.sort(key=lambda x: x[2], reverse=True)
        
        for word_from_list, text_word, score in fuzzy_candidates:
            if (word_from_list not in best_fuzzy_matches and 
                text_word not in used_text_words and 
                text_word not in matched_text_words):
                best_fuzzy_matches[word_from_list] = (word_from_list, text_word, score)
                used_text_words.add(text_word)
        
        fuzzy_matches = list(best_fuzzy_matches.values())
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)
        
        for word_from_list, _, _ in fuzzy_matches:
            all_found_words.add(word_from_list)

        if max_matches_per_word is not None:
            final_exact_matches = []
            final_substring_matches = []
            final_fuzzy_matches = []
            final_all_found_words = set()
            
            all_matched_words = set(exact_matches) | set(word for word, _, _ in substring_matches) | set(word for word, _, _ in fuzzy_matches)
            
            for word_from_list in all_matched_words:
                word_matches = []
                
                if word_from_list in exact_matches:
                    word_matches.append((word_from_list, 'exact', 1.0, 0))
                
                for w, text_word, match_type in substring_matches:
                    if w == word_from_list:
                        score = 0.9 if match_type in ['subpath', 'substring'] else 0.85
                        word_matches.append((w, 'substring', score, 1, text_word, match_type))
                
                for w, text_word, score in fuzzy_matches:
                    if w == word_from_list:
                        word_matches.append((w, 'fuzzy', score, 2, text_word))
                
                word_matches.sort(key=lambda x: (x[3], -x[2]))
                
                top_word_matches = word_matches[:max_matches_per_word]
                
                for match in top_word_matches:
                    final_all_found_words.add(match[0])
                    
                    if match[1] == 'exact':
                        final_exact_matches.append(match[0])
                    elif match[1] == 'substring':
                        final_substring_matches.append((match[0], match[4], match[5]))
                    elif match[1] == 'fuzzy':
                        final_fuzzy_matches.append((match[0], match[4], match[2]))
            
            exact_matches = final_exact_matches
            substring_matches = final_substring_matches
            fuzzy_matches = final_fuzzy_matches
            all_found_words = final_all_found_words

        exact_matches.sort()
        substring_matches.sort(key=lambda x: x[0])
        fuzzy_matches.sort(key=lambda x: x[2], reverse=True)

        return {
            'exact_matches': exact_matches,
            'fuzzy_matches': fuzzy_matches,
            'substring_matches': substring_matches,
            'all_found_words': sorted(list(all_found_words))
        }
