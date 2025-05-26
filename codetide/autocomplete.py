class AutoComplete:
    def __init__(self, word_list):
        """Initialize with a list of strings to search from"""
        self.words = word_list
        # Sort words for better organization (optional)
        self.words.sort()
    
    def get_suggestions(self, prefix, max_suggestions=10, case_sensitive=False):
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
    
    def get_fuzzy_suggestions(self, prefix, max_suggestions=10, case_sensitive=False):
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
