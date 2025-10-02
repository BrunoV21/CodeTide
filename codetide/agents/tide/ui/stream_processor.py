from typing import Optional, List, NamedTuple
import chainlit as cl

class MarkerConfig(NamedTuple):
    """Configuration for a single marker pair."""
    begin_marker: str
    end_marker: str
    start_wrapper: str = ""
    end_wrapper: str = ""
    target_step: Optional[cl.Step] = None
    fallback_msg: Optional[cl.Message] = None

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
        if idx == -1:
            # No end marker found, stream everything except potential partial marker
            marker_len = len(self.current_config.end_marker)
            if len(self.buffer) >= marker_len:
                stream_content = self.buffer[:-marker_len+1]
                ### TODO target step cannot receive stream_token or can it? Maybe we could just build a wrapper aound custom element
                if stream_content and self.current_config.target_step:
                    await self.current_config.target_step.stream_token(stream_content)
                self.buffer = self.buffer[-marker_len+1:]
            return False
        else:
            # Found end marker
            if idx > 0 and self.current_config.target_step:
                # Stream content before the end marker to target step
                await self.current_config.target_step.stream_token(self.buffer[:idx])
            
            # Close the special block
            if self.current_config.target_step and self.current_config.end_wrapper:
                await self.current_config.target_step.stream_token(self.current_config.end_wrapper)
            
            self.buffer = self.buffer[idx + len(self.current_config.end_marker):]
            self.current_config = None
            self.current_config_index = None
            
            # Remove everything up to and including the end marker
            if self.buffer.startswith('\n'):
                self.buffer = self.buffer[1:]
            
            return True
    
    def _get_fallback_msg(self) -> Optional[cl.Message]:
        """Get the appropriate fallback message."""
        return self.global_fallback_msg
    
    async def finalize(self) -> None:
        """
        Handle any remaining content in buffer and clean up.
        """
        if self.buffer:
            if self.current_config is not None:
                if self.current_config.target_step:
                    await self.current_config.target_step.stream_token(self.buffer)
                    if self.current_config.end_wrapper:
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