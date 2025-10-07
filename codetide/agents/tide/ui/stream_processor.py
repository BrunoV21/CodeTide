from typing import Dict, Literal, Optional, List, NamedTuple, Union
from dataclasses import dataclass
import chainlit as cl
import re

class CustomElementStep:
    ...

    def stream_token(self, content :str)->str:
        pass

@dataclass
class ExtractedFields:
    """Container for extracted field data from a marker block."""
    raw_content: str
    fields: Dict[str, any]

class FieldExtractor:
    """Handles extraction of structured fields from marker content."""
    
    def __init__(self, field_patterns: Dict[str, str]):
        """
        Initialize with field extraction patterns.
        
        Args:
            field_patterns: Dict mapping field names to regex patterns.
                           Patterns should have named groups or return the match.
        """
        self.field_patterns = {
            name: re.compile(pattern, re.MULTILINE | re.DOTALL)
            for name, pattern in field_patterns.items()
        }
    
    def extract(self, content: str) -> ExtractedFields:
        """
        Extract all configured fields from content.
        
        Args:
            content: Raw text content between markers
            
        Returns:
            ExtractedFields object with parsed data
        """
        fields = {}
        
        for field_name, pattern in self.field_patterns.items():
            match = pattern.search(content)
            if match:
                # If pattern has named groups, use them
                if match.groupdict():
                    fields[field_name] = match.groupdict()
                # Otherwise use the first group or full match
                elif match.groups():
                    fields[field_name] = match.group(1).strip()
                else:
                    fields[field_name] = match.group(0).strip()
            else:
                fields[field_name] = None
        
        return ExtractedFields(raw_content=content, fields=fields)
    
    def extract_list(self, content: str, field_name: str) -> List[str]:
        """
        Extract a list of items (e.g., candidate_identifiers).
        
        Args:
            content: Raw text content
            field_name: Name of the field containing list items
            
        Returns:
            List of extracted strings
        """
        pattern = self.field_patterns.get(field_name)
        if not pattern:
            return []
        
        matches = pattern.findall(content)
        return [m.strip() if isinstance(m, str) else m[0].strip() 
                for m in matches if m]

class MarkerConfig(NamedTuple):
    """Configuration for a single marker pair."""
    begin_marker: str
    end_marker: str
    start_wrapper: str = ""
    end_wrapper: str = ""
    target_step: Optional[Union[cl.Step, CustomElementStep]] = None
    fallback_msg: Optional[cl.Message] = None
    stream_mode: Literal["chunk", "full"] = "chunk"
    field_extractor: Optional[FieldExtractor] = None
    
    def process_content(self, content: str) -> Union[str, ExtractedFields]:
        """
        Process content, extracting fields if field_extractor is configured.
        
        Args:
            content: Raw content between markers
            
        Returns:
            ExtractedFields if extractor configured, otherwise raw string
        """
        if self.field_extractor:
            return self.field_extractor.extract(content)
        return content

class StreamProcessor:
    """
    A reusable class for processing streaming content with multiple configurable markers and wrappers.
    """
    
    def __init__(
        self,
        marker_configs: List[MarkerConfig],
        global_fallback_msg: Optional[cl.Message] = None
    ):
        """
        Initialize the stream processor with multiple marker configurations.
        
        Args:
            marker_configs: List of MarkerConfig objects defining different marker behaviors
            global_fallback_msg: Default fallback message for content not matching any markers
        """
        self.marker_configs = marker_configs
        self.global_fallback_msg = global_fallback_msg
        
        self.buffer = ""
        self.current_config = None  # Currently active marker config
        self.current_config_index = None
        self.accumulated_content = ""  # For full mode with field extractor
    
    def __init_single__(
        self,
        begin_marker: str,
        end_marker: str,
        start_wrapper: str = "",
        end_wrapper: str = "",
        target_step: Optional[cl.Step] = None,
        fallback_msg: Optional[cl.Message] = None
    ):
        """
        Backward compatibility constructor for single marker configuration.
        """
        config = MarkerConfig(
            begin_marker=begin_marker,
            end_marker=end_marker,
            start_wrapper=start_wrapper,
            end_wrapper=end_wrapper,
            target_step=target_step,
            fallback_msg=fallback_msg
        )
        self.__init__([config], fallback_msg)

    async def process_chunk(self, chunk: str) -> bool:
        """
        Process a chunk of streaming content.
        
        Args:
            chunk: The content chunk to process
            
        Returns:
            True if currently in a special block OR if buffer contains a potential partial begin_marker
        """
        self.buffer += chunk
        
        # Process buffer until no more complete markers can be found
        while True:
            if self.current_config is None:
                if not await self._process_outside_block():
                    break
            else:
                if not await self._process_inside_block():
                    break
        
        # Return True if in special block OR if buffer might contain partial begin_marker
        return self.current_config is not None # or self._buffer_might_contain_partial_marker()
    
    def _buffer_might_contain_partial_marker(self) -> bool:
        """Check if buffer might contain a partial begin marker."""
        if not self.buffer:
            return False
            
        for config in self.marker_configs:
            marker_len = len(config.begin_marker)
            if len(self.buffer) < marker_len:
                # Check if buffer could be start of this marker
                if config.begin_marker.startswith(self.buffer):
                    return True
        return False
    
    async def _process_outside_block(self) -> bool:
        """
        Process buffer content when outside a special block.
        
        Returns:
            True if processing should continue (found a marker), False otherwise
        """
        # Find the earliest begin marker
        earliest_idx = len(self.buffer)
        earliest_config = None
        earliest_config_index = None
        
        for i, config in enumerate(self.marker_configs):
            idx = self.buffer.find(config.begin_marker)
            if idx != -1 and idx < earliest_idx:
                earliest_idx = idx
                earliest_config = config
                earliest_config_index = i
        
        if earliest_config is None:
            # No begin marker found, stream everything except potential partial markers
            max_marker_len = max(len(config.begin_marker) for config in self.marker_configs)
            if len(self.buffer) >= max_marker_len:
                stream_content = self.buffer[:-max_marker_len+1]
                if stream_content:
                    fallback_msg = self._get_fallback_msg()
                    if fallback_msg:
                        await fallback_msg.stream_token(stream_content)
                self.buffer = self.buffer[-max_marker_len+1:]
            return False
        else:
            # Found begin marker
            if earliest_idx > 0:
                # Stream content before the marker to fallback message
                fallback_msg = self._get_fallback_msg()
                if fallback_msg:
                    await fallback_msg.stream_token(self.buffer[:earliest_idx])
            
            # Start the special block
            if earliest_config.target_step and earliest_config.start_wrapper:
                await earliest_config.target_step.stream_token(earliest_config.start_wrapper)
            
            self.current_config = earliest_config
            self.current_config_index = earliest_config_index
            self.accumulated_content = ""  # Reset accumulator for full mode
            
            # Remove everything up to and including the begin marker
            self.buffer = self.buffer[earliest_idx + len(earliest_config.begin_marker):]
            if self.buffer.startswith('\n'):
                self.buffer = self.buffer[1:]
            
            return True
    
    async def _process_inside_block(self) -> bool:
        """
        Process buffer content when inside a special block.
        
        Returns:
            True if processing should continue (found end marker), False otherwise
        """
        if self.current_config is None:
            return False
            
        idx = self.buffer.find(self.current_config.end_marker)
        
        # Check if we're in full mode with field extractor
        is_full_mode = (self.current_config.stream_mode == "full" and 
                       self.current_config.field_extractor is not None)
        
        if idx == -1:
            # No end marker found
            marker_len = len(self.current_config.end_marker)
            if len(self.buffer) >= marker_len:
                stream_content = self.buffer[:-marker_len+1]
                
                if is_full_mode:
                    # Accumulate content for processing at the end
                    self.accumulated_content += stream_content
                else:
                    # Stream immediately in chunk mode
                    if stream_content and self.current_config.target_step:
                        await self.current_config.target_step.stream_token(stream_content)
                
                self.buffer = self.buffer[-marker_len+1:]
            return False
        else:
            # Found end marker
            block_content = self.buffer[:idx]
            
            if is_full_mode:
                # Add final content to accumulator
                self.accumulated_content += block_content
                
                # Process the complete content with field extractor
                extracted = self.current_config.process_content(self.accumulated_content)
                
                # Stream the processed result
                if self.current_config.target_step:
                    processed_output = self._format_extracted_fields(extracted)
                    await self.current_config.target_step.stream_token(processed_output)
            else:
                # Stream content before the end marker in chunk mode
                if block_content and self.current_config.target_step:
                    await self.current_config.target_step.stream_token(block_content)
            
            # Close the special block
            if self.current_config.target_step and self.current_config.end_wrapper:
                await self.current_config.target_step.stream_token(self.current_config.end_wrapper)
            
            self.buffer = self.buffer[idx + len(self.current_config.end_marker):]
            self.current_config = None
            self.current_config_index = None
            self.accumulated_content = ""  # Clear accumulator
            
            # Remove everything up to and including the end marker
            if self.buffer.startswith('\n'):
                self.buffer = self.buffer[1:]
            
            return True
    
    def _format_extracted_fields(self, extracted: Union[str, ExtractedFields]) -> str:
        """
        Format extracted fields for streaming output.
        
        Args:
            extracted: Either raw string or ExtractedFields object
            
        Returns:
            Formatted string representation
        """
        if isinstance(extracted, str):
            return extracted
        
        # Format ExtractedFields into a readable output
        output_parts = []
        
        for field_name, field_value in extracted.fields.items():
            if field_value is None:
                continue
                
            # Handle list fields specially (like candidate_identifiers)
            if field_name in self.current_config.field_extractor.field_patterns:
                # Try to extract as list
                list_items = self.current_config.field_extractor.extract_list(
                    extracted.raw_content, 
                    field_name
                )
                if list_items:
                    output_parts.append(f"**{field_name}**:")
                    for item in list_items:
                        output_parts.append(f"  - {item}")
                    continue
            
            # Handle regular fields
            if isinstance(field_value, dict):
                output_parts.append(f"**{field_name}**: {field_value}")
            else:
                output_parts.append(f"**{field_name}**: {field_value}")
        
        return "\n".join(output_parts) if output_parts else extracted.raw_content
    
    def _get_fallback_msg(self) -> Optional[cl.Message]:
        """Get the appropriate fallback message."""
        return self.global_fallback_msg
    
    async def finalize(self) -> None:
        """
        Handle any remaining content in buffer and clean up.
        """
        if self.buffer:
            if self.current_config is not None:
                is_full_mode = (self.current_config.stream_mode == "full" and 
                               self.current_config.field_extractor is not None)
                
                if is_full_mode:
                    # Process accumulated content with field extractor
                    self.accumulated_content += self.buffer
                    extracted = self.current_config.process_content(self.accumulated_content)
                    
                    if self.current_config.target_step:
                        processed_output = self._format_extracted_fields(extracted)
                        await self.current_config.target_step.stream_token(processed_output)
                else:
                    # Stream remaining content in chunk mode
                    if self.current_config.target_step:
                        await self.current_config.target_step.stream_token(self.buffer)
                
                if self.current_config.target_step and self.current_config.end_wrapper:
                    await self.current_config.target_step.stream_token(self.current_config.end_wrapper)
            else:
                fallback_msg = self._get_fallback_msg()
                if fallback_msg:
                    await fallback_msg.stream_token(self.buffer)
                    await fallback_msg.send()
        
        # Reset state
        self.buffer = ""
        self.current_config = None
        self.current_config_index = None
        self.accumulated_content = ""
