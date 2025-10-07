"""
Pytest test suite for StreamProcessor with field extraction in full mode.

Run with: pytest test_stream_processor.py -v -s
"""
import pytest
from typing import List
from codetide.agents.tide.ui.stream_processor import (
    ExtractedFields, 
    MarkerConfig, 
    FieldExtractor, 
    StreamProcessor,
    CustomElementStep
)


# Mock classes to simulate chainlit behavior
class MockStep:
    """Mock Step class for testing."""
    
    def __init__(self, name: str):
        self.name = name
        self.content = []
    
    async def stream_token(self, content: str):
        """Simulate streaming a token."""
        self.content.append(content)
        print(f"[{self.name}] Streamed: {content}")
    
    def get_full_content(self) -> str:
        """Get all streamed content."""
        return "".join(self.content)
    
    def clear(self):
        """Clear content for next test."""
        self.content = []


class MockMessage:
    """Mock Message class for testing."""
    
    def __init__(self, name: str = "fallback"):
        self.name = name
        self.content = []
    
    async def stream_token(self, content: str):
        """Simulate streaming a token."""
        self.content.append(content)
        print(f"[{self.name}] Streamed: {content}")
    
    async def send(self):
        """Simulate sending the message."""
        print(f"[{self.name}] Message sent!")
    
    def get_full_content(self) -> str:
        """Get all streamed content."""
        return "".join(self.content)
    
    def clear(self):
        """Clear content for next test."""
        self.content = []


class MockCustomElement:
    """Mock CustomElement class for testing."""
    
    def __init__(self, name: str):
        self.name = name
        self.props = {}
        self.update_count = 0
    
    async def update(self):
        """Simulate updating the element."""
        self.update_count += 1
        print(f"[{self.name}] Updated (count: {self.update_count})")
        print(f"[{self.name}] Current props: {self.props}")


# Fixtures
@pytest.fixture
def field_patterns():
    """Field patterns for reasoning blocks."""
    return {
        "header": r"\*\*([^*]+)\*\*(?=\s*\n\s*\*\*content\*\*)",
        "content": r"\*\*content\*\*:\s*(.+?)(?=\s*\*\*candidate_identifiers\*\*|$)",
        "candidate_identifiers": r"^\s*-\s*(.+?)$"
    }


@pytest.fixture
def reasoning_step():
    """Mock step for reasoning blocks."""
    return MockStep("Reasoning Block")


@pytest.fixture
def code_step():
    """Mock step for code blocks."""
    return MockStep("Code Block")


@pytest.fixture
def fallback_msg():
    """Mock fallback message."""
    return MockMessage("Fallback")


@pytest.fixture
def mock_custom_element():
    """Mock custom element for testing."""
    return MockCustomElement("ReasoningDisplay")


@pytest.fixture
def sample_stream():
    """Sample streaming content with reasoning blocks."""
    return """Some initial content before reasoning.

*** Begin Reasoning
**Update Authentication Module**
**content**: brief summary of the logic behind this task and the files to look into and why
**candidate_identifiers**:
  - src.auth.authenticate.AuthHandler.verify_token
  - src.auth.models.User
  - config/auth_config.yaml
*** End Reasoning

Some content between blocks.

*** Begin Reasoning
**Refactor Database Layer**
**content**: Need to update the database connection pooling to handle increased load
**candidate_identifiers**:
  - src.database.connection.ConnectionPool
  - src.database.query_builder.QueryBuilder
  - tests/database/test_connection.py
*** End Reasoning

Final content after reasoning blocks.
"""


@pytest.fixture
def mixed_content_stream():
    """Sample stream with both reasoning and code blocks."""
    return """Here's my analysis:

*** Begin Reasoning
**Analyze Code Structure**
**content**: Review the existing code architecture and identify areas for improvement
**candidate_identifiers**:
  - src.main.Application
  - src.config.settings
*** End Reasoning

Now here's the implementation:

```python
def process_data(items):
    return [item * 2 for item in items]
```

That's the solution!
"""


# Helper functions
def split_into_chunks(text: str, chunk_size: int = 30) -> List[str]:
    """Split text into chunks for simulating streaming."""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


# Tests
@pytest.mark.asyncio
async def test_full_mode_field_extraction(field_patterns, reasoning_step, fallback_msg, sample_stream):
    """Test that full mode accumulates content and processes it only at end marker."""
    
    # Setup
    extractor = FieldExtractor(field_patterns)
    reasoning_config = MarkerConfig(
        begin_marker="*** Begin Reasoning",
        end_marker="*** End Reasoning",
        marker_id="reasoning",
        start_wrapper="## Processing Reasoning Block\n\n",
        end_wrapper="\n\n---\n",
        target_step=reasoning_step,
        stream_mode="full",
        field_extractor=extractor
    )
    
    processor = StreamProcessor(
        marker_configs=[reasoning_config],
        global_fallback_msg=fallback_msg
    )
    
    # Process stream in chunks
    chunks = split_into_chunks(sample_stream, chunk_size=30)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    # Assertions
    reasoning_content = reasoning_step.get_full_content()
    fallback_content = fallback_msg.get_full_content()
    
    # Should have processed 2 reasoning blocks
    assert reasoning_content.count("## Processing Reasoning Block") == 2
    assert reasoning_content.count("---") == 2
    
    # Should have extracted headers
    assert "Update Authentication Module" in reasoning_content
    assert "Refactor Database Layer" in reasoning_content
    
    # Should have extracted candidate_identifiers
    assert "src.auth.authenticate.AuthHandler.verify_token" in reasoning_content
    assert "src.database.connection.ConnectionPool" in reasoning_content
    
    # Fallback should have content outside markers
    assert "Some initial content before reasoning" in fallback_content
    assert "Some content between blocks" in fallback_content
    assert "Final content after reasoning blocks" in fallback_content
    
    print("\n✓ Full mode field extraction test passed!")


@pytest.mark.asyncio
async def test_custom_element_step_list_accumulation(field_patterns, mock_custom_element, fallback_msg, sample_stream):
    """Test CustomElementStep accumulating extracted fields in a list."""
    
    # Setup CustomElementStep
    props_schema = {
        "reasoning": list,  # Will accumulate reasoning blocks as list
    }
    custom_step = CustomElementStep(mock_custom_element, props_schema)
    
    # Setup extractor and config
    extractor = FieldExtractor(field_patterns)
    reasoning_config = MarkerConfig(
        begin_marker="*** Begin Reasoning",
        end_marker="*** End Reasoning",
        marker_id="reasoning",  # Matches props_schema key
        target_step=custom_step,
        stream_mode="full",
        field_extractor=extractor
    )
    
    processor = StreamProcessor(
        marker_configs=[reasoning_config],
        global_fallback_msg=fallback_msg
    )
    
    # Process stream
    chunks = split_into_chunks(sample_stream, chunk_size=30)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    # Assertions
    assert mock_custom_element.update_count == 2  # Updated twice (one per block)
    assert "reasoning" in mock_custom_element.props
    
    reasoning_list = mock_custom_element.props["reasoning"]
    assert isinstance(reasoning_list, list)
    assert len(reasoning_list) == 2
    
    # Check first block
    first_block = reasoning_list[0]
    assert first_block["header"] == "Update Authentication Module"
    assert "brief summary" in first_block["content"]
    
    # Check second block
    second_block = reasoning_list[1]
    assert second_block["header"] == "Refactor Database Layer"
    assert "database connection pooling" in second_block["content"]
    
    print("\n✓ CustomElementStep list accumulation test passed!")


@pytest.mark.asyncio
async def test_custom_element_step_string_concatenation(field_patterns, mock_custom_element, fallback_msg):
    """Test CustomElementStep concatenating extracted fields as string."""
    
    # Setup CustomElementStep with string type
    props_schema = {
        "reasoning_text": str,
    }
    custom_step = CustomElementStep(mock_custom_element, props_schema)
    
    # Setup extractor and config
    extractor = FieldExtractor(field_patterns)
    reasoning_config = MarkerConfig(
        begin_marker="*** Begin Reasoning",
        end_marker="*** End Reasoning",
        marker_id="reasoning_text",  # Matches props_schema key
        target_step=custom_step,
        stream_mode="full",
        field_extractor=extractor
    )
    
    processor = StreamProcessor(
        marker_configs=[reasoning_config],
        global_fallback_msg=fallback_msg
    )
    
    # Process stream with single block
    test_stream = """
*** Begin Reasoning
**First Task**
**content**: This is the first task description
**candidate_identifiers**:
  - src.module.Class
*** End Reasoning

*** Begin Reasoning
**Second Task**
**content**: This is the second task description
**candidate_identifiers**:
  - src.another.Class
*** End Reasoning
"""
    
    chunks = split_into_chunks(test_stream, chunk_size=30)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    # Assertions
    assert mock_custom_element.update_count == 2
    assert "reasoning_text" in mock_custom_element.props
    
    reasoning_text = mock_custom_element.props["reasoning_text"]
    assert isinstance(reasoning_text, str)
    
    # Both blocks should be concatenated
    assert "First Task" in reasoning_text
    assert "Second Task" in reasoning_text
    assert "src.module.Class" in reasoning_text
    assert "src.another.Class" in reasoning_text
    
    print("\n✓ CustomElementStep string concatenation test passed!")


@pytest.mark.asyncio
async def test_custom_element_step_dict_merging(mock_custom_element, fallback_msg):
    """Test CustomElementStep merging extracted fields into dict."""
    
    # Setup CustomElementStep with dict type
    props_schema = {
        "metadata": dict,
    }
    custom_step = CustomElementStep(mock_custom_element, props_schema)
    
    # Simple field patterns for metadata
    field_patterns = {
        "status": r"status:\s*(\w+)",
        "count": r"count:\s*(\d+)",
    }
    
    extractor = FieldExtractor(field_patterns)
    metadata_config = MarkerConfig(
        begin_marker="### Begin Metadata",
        end_marker="### End Metadata",
        marker_id="metadata",
        target_step=custom_step,
        stream_mode="full",
        field_extractor=extractor
    )
    
    processor = StreamProcessor(
        marker_configs=[metadata_config],
        global_fallback_msg=fallback_msg
    )
    
    # Process stream
    test_stream = """
### Begin Metadata
status: active
count: 42
### End Metadata
"""
    
    chunks = split_into_chunks(test_stream, chunk_size=20)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    # Assertions
    assert "metadata" in mock_custom_element.props
    metadata = mock_custom_element.props["metadata"]
    assert isinstance(metadata, dict)
    assert metadata.get("status") == "active"
    assert metadata.get("count") == "42"
    
    print("\n✓ CustomElementStep dict merging test passed!")


@pytest.mark.asyncio
async def test_chunk_mode_immediate_streaming(code_step, fallback_msg):
    """Test that chunk mode streams content immediately without accumulation."""
    
    # Setup
    code_config = MarkerConfig(
        begin_marker="```python",
        end_marker="```",
        marker_id="code",
        start_wrapper="```python\n",
        end_wrapper="\n```",
        target_step=code_step,
        stream_mode="chunk"
    )
    
    processor = StreamProcessor(
        marker_configs=[code_config],
        global_fallback_msg=fallback_msg
    )
    
    # Process stream
    test_stream = """Some text before.

```python
def hello():
    print("world")
```

Some text after.
"""
    
    chunks = split_into_chunks(test_stream, chunk_size=20)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    # Assertions
    code_content = code_step.get_full_content()
    
    assert "```python\n" in code_content
    assert "def hello():" in code_content
    assert 'print("world")' in code_content
    assert "\n```" in code_content
    
    print("\n✓ Chunk mode immediate streaming test passed!")


@pytest.mark.asyncio
async def test_multiple_configs_mixed_modes(
    field_patterns, reasoning_step, code_step, fallback_msg, mixed_content_stream
):
    """Test multiple marker configs with different streaming modes."""
    
    # Setup reasoning config (full mode)
    reasoning_extractor = FieldExtractor(field_patterns)
    reasoning_config = MarkerConfig(
        begin_marker="*** Begin Reasoning",
        end_marker="*** End Reasoning",
        marker_id="reasoning",
        target_step=reasoning_step,
        stream_mode="full",
        field_extractor=reasoning_extractor
    )
    
    # Setup code config (chunk mode)
    code_config = MarkerConfig(
        begin_marker="```python",
        end_marker="```",
        marker_id="code",
        start_wrapper="```python\n",
        end_wrapper="\n```",
        target_step=code_step,
        stream_mode="chunk"
    )
    
    processor = StreamProcessor(
        marker_configs=[reasoning_config, code_config],
        global_fallback_msg=fallback_msg
    )
    
    # Process stream
    chunks = split_into_chunks(mixed_content_stream, chunk_size=25)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    # Assertions
    reasoning_content = reasoning_step.get_full_content()
    code_content = code_step.get_full_content()
    fallback_content = fallback_msg.get_full_content()
    
    # Reasoning should be processed with field extraction
    assert "Analyze Code Structure" in reasoning_content
    assert "src.main.Application" in reasoning_content
    
    # Code should be streamed as-is
    assert "def process_data(items):" in code_content
    assert "return [item * 2 for item in items]" in code_content
    
    # Fallback should have content outside both markers
    assert "Here's my analysis:" in fallback_content
    assert "Now here's the implementation:" in fallback_content
    assert "That's the solution!" in fallback_content
    
    print("\n✓ Multiple configs mixed modes test passed!")


@pytest.mark.asyncio
async def test_field_extractor_list_extraction(field_patterns):
    """Test that list extraction works correctly for candidate_identifiers."""
    
    extractor = FieldExtractor(field_patterns)
    
    test_content = """**Task Header**
**content**: Some description here
**candidate_identifiers**:
  - src.module.Class.method
  - src.another.module.function
  - config/settings.yaml
"""
    
    # Extract fields
    extracted = extractor.extract(test_content, marker_id="test")
    
    # Extract list specifically
    identifiers = extractor.extract_list(test_content, "candidate_identifiers")
    
    # Assertions
    assert isinstance(extracted, ExtractedFields)
    assert extracted.marker_id == "test"
    assert extracted.fields["header"] == "Task Header"
    assert "Some description here" in extracted.fields["content"]
    
    assert len(identifiers) == 3
    assert "src.module.Class.method" in identifiers
    assert "src.another.module.function" in identifiers
    assert "config/settings.yaml" in identifiers
    
    print("\n✓ Field extractor list extraction test passed!")


@pytest.mark.asyncio
async def test_incomplete_block_handling(field_patterns, reasoning_step, fallback_msg):
    """Test that incomplete blocks are handled properly in finalize."""
    
    extractor = FieldExtractor(field_patterns)
    reasoning_config = MarkerConfig(
        begin_marker="*** Begin Reasoning",
        end_marker="*** End Reasoning",
        marker_id="reasoning",
        target_step=reasoning_step,
        stream_mode="full",
        field_extractor=extractor
    )
    
    processor = StreamProcessor(
        marker_configs=[reasoning_config],
        global_fallback_msg=fallback_msg
    )
    
    # Stream with incomplete block (no end marker)
    incomplete_stream = """Some content.

*** Begin Reasoning
**Incomplete Task**
**content**: This block never closes
**candidate_identifiers**:
  - src.test.module
"""
    
    chunks = split_into_chunks(incomplete_stream, chunk_size=25)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    # Should still process the incomplete block in finalize
    reasoning_content = reasoning_step.get_full_content()
    assert "Incomplete Task" in reasoning_content
    assert "src.test.module" in reasoning_content
    
    print("\n✓ Incomplete block handling test passed!")


@pytest.mark.asyncio
async def test_no_field_extractor_full_mode(reasoning_step, fallback_msg):
    """Test full mode without field extractor (should stream raw content)."""
    
    reasoning_config = MarkerConfig(
        begin_marker="*** Begin Reasoning",
        end_marker="*** End Reasoning",
        marker_id="reasoning",
        target_step=reasoning_step,
        stream_mode="full",
        field_extractor=None  # No extractor
    )
    
    processor = StreamProcessor(
        marker_configs=[reasoning_config],
        global_fallback_msg=fallback_msg
    )
    
    test_stream = """
*** Begin Reasoning
This is raw content without structured fields.
Just plain text.
*** End Reasoning
"""
    
    chunks = split_into_chunks(test_stream, chunk_size=25)
    for chunk in chunks:
        await processor.process_chunk(chunk)
    
    await processor.finalize()
    
    reasoning_content = reasoning_step.get_full_content()
    
    # Should stream raw content without formatting
    assert "This is raw content without structured fields." in reasoning_content
    assert "Just plain text." in reasoning_content
    
    print("\n✓ Full mode without field extractor test passed!")


@pytest.mark.asyncio
async def test_extracted_fields_to_dict():
    """Test ExtractedFields.to_dict() method."""
    
    fields_data = {
        "header": "Test Header",
        "content": "Test content",
        "items": ["item1", "item2"]
    }
    
    extracted = ExtractedFields(
        marker_id="test_marker",
        raw_content="raw text",
        fields=fields_data
    )
    
    result = extracted.to_dict()
    
    assert result["marker_id"] == "test_marker"
    assert result["fields"] == fields_data
    assert "raw_content" not in result  # to_dict should not include raw_content
    
    print("\n✓ ExtractedFields.to_dict() test passed!")


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v", "-s"])