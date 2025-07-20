from codetide.mcp.tools.patch_code import BREAKLINE_TOKEN, replace_newline_in_quotes

class TestReplaceNewlineInQuotes:
    """Test suite for replace_newline_in_quotes function"""
    
    def test_single_quoted_string_with_newline(self):
        """Test replacement in single-quoted strings with actual newlines"""
        text = "'Hello\nWorld'"
        expected = f"'Hello{BREAKLINE_TOKEN}World'"
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_double_quoted_string_with_newline(self):
        """Test replacement in double-quoted strings with actual newlines"""
        text = '"Hello\nWorld"'
        expected = f'"Hello{BREAKLINE_TOKEN}World"'
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_single_quoted_string_with_literal_backslash_n(self):
        """Test replacement of literal \\n in single-quoted strings"""
        text = r"'Hello\nWorld'"
        expected = f"'Hello{BREAKLINE_TOKEN}World'"
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_double_quoted_string_with_literal_backslash_n(self):
        """Test replacement of literal \\n in double-quoted strings"""
        text = r'"Hello\nWorld"'
        expected = f'"Hello{BREAKLINE_TOKEN}World"'
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_triple_quoted_strings_unchanged(self):
        """Test that triple-quoted strings are not modified"""
        text = '''"""This has a
newline that should NOT change"""'''
        result = replace_newline_in_quotes(text)
        assert result == text
    
    def test_triple_single_quoted_strings_unchanged(self):
        """Test that triple single-quoted strings are not modified"""
        text = """'''This has a
newline that should NOT change'''"""
        result = replace_newline_in_quotes(text)
        assert result == text
    
    def test_mixed_quote_types(self):
        """Test handling of mixed single and double quotes"""
        text = '''single = 'Hello\\nWorld'
double = "Goodbye\\nMoon"'''
        expected = f'''single = 'Hello{BREAKLINE_TOKEN}World'
double = "Goodbye{BREAKLINE_TOKEN}Moon"'''
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_escaped_quotes_in_strings(self):
        """Test strings containing escaped quotes"""
        text = r"'He said \"Hello\nWorld\"'"
        expected = f"'He said \\\"Hello{BREAKLINE_TOKEN}World\\\"'"
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_nested_quotes_scenario(self):
        """Test complex nested quote scenarios"""
        text = '''"She said 'Hello\\nWorld' to me"'''
        expected = f'''"She said 'Hello{BREAKLINE_TOKEN}World' to me"'''
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_multiple_newlines_in_single_string(self):
        """Test multiple newlines within a single quoted string"""
        text = "'First\\nSecond\\nThird'"
        expected = f"'First{BREAKLINE_TOKEN}Second{BREAKLINE_TOKEN}Third'"
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_empty_quoted_strings(self):
        """Test empty quoted strings"""
        text = "''"
        result = replace_newline_in_quotes(text)
        assert result == text
        
        text = '""'
        result = replace_newline_in_quotes(text)
        assert result == text
    
    def test_no_quotes_in_text(self):
        """Test text with no quotes at all"""
        text = "This is plain text with\nnewlines"
        result = replace_newline_in_quotes(text)
        assert result == text
    
    def test_unmatched_quotes(self):
        """Test text with unmatched quotes (should not be processed)"""
        text = "This has an unmatched ' quote"
        result = replace_newline_in_quotes(text)
        assert result == text
    
    def test_custom_token(self):
        """Test using a custom replacement token"""
        text = "'Hello\\nWorld'"
        custom_token = "<<CUSTOM>>"
        expected = f"'Hello{custom_token}World'"
        result = replace_newline_in_quotes(text, token=custom_token)
        assert result == expected
    
    def test_function_definition_scenario(self):
        """Test the original failing scenario from your example"""
        text = '''def example():
    single = 'This has a
newline'
    double = "This also has a
newline"
    triple = """This is a triple quote
with multiple
lines that should NOT be changed"""
    another_triple = \'\'\'Another triple
with newlines
that should stay\'\'\'
    return single, double, triple'''
        
        result = replace_newline_in_quotes(text)
        
        # Check that single and double quoted strings are modified
        assert f"'This has a{BREAKLINE_TOKEN}newline'" in result
        assert f'"This also has a{BREAKLINE_TOKEN}newline"' in result
        
        # Check that triple quoted strings remain unchanged
        assert '''"""This is a triple quote
with multiple
lines that should NOT be changed"""''' in result
        assert '''\'\'\'Another triple
with newlines
that should stay\'\'\'''' in result
    
    def test_consecutive_quoted_strings(self):
        """Test consecutive quoted strings"""
        text = "'First\\nString' 'Second\\nString'"
        expected = f"'First{BREAKLINE_TOKEN}String' 'Second{BREAKLINE_TOKEN}String'"
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_mixed_actual_and_literal_newlines(self):
        """Test strings with both actual newlines and literal \\n"""
        text = """'Hello\\nWorld
Real newline here'"""
        expected = f"""'Hello{BREAKLINE_TOKEN}World{BREAKLINE_TOKEN}Real newline here'"""
        result = replace_newline_in_quotes(text)
        assert result == expected
    
    def test_quotes_within_triple_quotes(self):
        """Test single/double quotes within triple quotes (should not be processed)"""
        text = '''"""This contains 'single quotes' and "double quotes"
with newlines that should NOT change"""'''
        result = replace_newline_in_quotes(text)
        assert result == text
    
    def test_complex_python_code(self):
        """Test a complex Python code snippet"""
        text = '''def process_data():
    query = "SELECT * FROM users WHERE name = 'John\\nDoe'"
    error_msg = 'Database connection failed\\nRetrying...'
    docstring = """
    This function processes data from the database.
    It handles errors gracefully and logs appropriate messages.
    No changes should be made to this docstring.
    """
    return query, error_msg'''
        
        result = replace_newline_in_quotes(text)
        
        # Check replacements in single/double quotes
        assert f'"SELECT * FROM users WHERE name = \'John{BREAKLINE_TOKEN}Doe\'"' in result
        assert f"'Database connection failed{BREAKLINE_TOKEN}Retrying...'" in result
        
        # Check triple quotes unchanged
        assert '''"""
    This function processes data from the database.
    It handles errors gracefully and logs appropriate messages.
    No changes should be made to this docstring.
    """''' in result
    
    def test_edge_case_almost_triple_quotes(self):
        """Test strings that look almost like triple quotes but aren't"""
        text = "'' + '\\ntest'"  # Two single quotes followed by another string
        expected = f"'' + '{BREAKLINE_TOKEN}test'"
        result = replace_newline_in_quotes(text)
        assert result == expected