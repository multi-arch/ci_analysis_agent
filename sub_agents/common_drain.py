"""Common drain functionality for all sub-agents to filter log content."""

import logging
import re
from typing import Tuple, Generator, List, Optional

import drain3
from drain3.template_miner_config import TemplateMinerConfig

# Set up logging
LOG = logging.getLogger("drain")

def chunk_continues(text: str, index: int) -> bool:
    """Set of heuristics for determining whether or not
    does the current chunk of log text continue on next line.

    Following rules are checked, in order:
    * is the next character is whitespace
    * is the previous character backslash '\\'
    * is the previous character colon ':'

    """
    conditionals = [
        lambda i, string: string[i + 1].isspace(),
        lambda i, string: string[i - 1] == "\\",
        lambda i, string: string[i - 1] == ":",
    ]

    for c in conditionals:
        y = c(index, text)
        if y:
            return True

    return False


def get_chunks(text: str) -> Generator[Tuple[int, str], None, None]:
    """Split log into chunks according to heuristic
    based on whitespace and backslash presence.
    """
    text_len = len(text)
    i = 0
    chunk = ""
    # Keep track of the original and next line number
    # every `\n` hit increases the next_line_number by one.
    original_line_number = 0
    next_line_number = 0
    while i < text_len:
        chunk += text[i]
        if text[i] == "\n":
            next_line_number += 1
            if i + 1 < text_len and chunk_continues(text, i):
                i += 1
                continue
            yield (original_line_number, chunk)
            original_line_number = next_line_number + 1
            chunk = ""
        i += 1


class SimpleDrainExtractor:
    """A simplified drain extractor for filtering log content in CI analysis agents."""

    def __init__(self, config_file: str, verbose: bool = False, max_clusters: int = 8, 
                 exclude_patterns: Optional[List[str]] = None):
        """Initialize with a specific drain3.ini config file.
        
        Args:
            config_file: Path to drain3.ini configuration
            verbose: Enable verbose logging
            max_clusters: Maximum number of clusters for drain
            exclude_patterns: List of regex patterns to exclude lines from processing.
                            Lines matching these patterns will be skipped entirely.
        """
        config = TemplateMinerConfig()
        config.load(config_file)
        config.profiling_enabled = verbose
        config.drain_max_clusters = max_clusters
        self.miner = drain3.TemplateMiner(config=config)
        self.verbose = verbose
        
        # Compile exclusion patterns for efficiency
        self.exclude_regex = None
        if exclude_patterns:
            combined_pattern = '|'.join(f'({pattern})' for pattern in exclude_patterns)
            self.exclude_regex = re.compile(combined_pattern, re.IGNORECASE)

    def filter_log(self, log_content: str, max_lines: int = 100) -> str:
        """Filter log content to extract most important parts using drain clustering.
        
        Args:
            log_content: Full log content to filter
            max_lines: Maximum number of lines to return in filtered output
            
        Returns:
            Filtered log content with most representative lines
        """
        if not log_content or not log_content.strip():
            return log_content
            
        # First pass: create clusters by processing all chunks (skip excluded lines)
        chunk_data = []
        for chunk_start, chunk in get_chunks(log_content):
            # Skip chunks matching exclusion patterns
            if self.exclude_regex and self.exclude_regex.search(chunk):
                continue
                
            self.miner.add_log_message(chunk)
            chunk_data.append((chunk_start, chunk))
        
        # Sort clusters by size (most frequent patterns first) 
        sorted_clusters = sorted(
            self.miner.drain.clusters, key=lambda it: it.size, reverse=True
        )
        
        # Second pass: find representative lines from ALL clusters
        # Don't limit to top clusters - failures are often rare (small clusters)
        important_lines = []
        used_clusters = set()
        
        for chunk_start, chunk in chunk_data:
            if len(important_lines) >= max_lines:
                break
                
            # Match chunk to a cluster
            cluster = self.miner.match(chunk, "always")
            # Include lines from ALL clusters (removed cluster rank filtering)
            if cluster and cluster not in used_clusters:
                important_lines.append(chunk.strip())
                used_clusters.add(cluster)
        
        # If we don't have enough important lines, add some from beginning and end
        # BUT respect exclusion patterns - don't add back excluded lines!
        if len(important_lines) < max_lines:
            lines = log_content.split('\n')
            # Add first few lines if not already represented AND not excluded
            for line in lines[:10]:
                if line.strip() and len(important_lines) < max_lines:
                    # Skip if matches exclusion pattern
                    if self.exclude_regex and self.exclude_regex.search(line):
                        continue
                    if not any(line.strip() in existing for existing in important_lines):
                        important_lines.append(line.strip())
            
            # Add last few lines if not already represented AND not excluded
            for line in lines[-10:]:
                if line.strip() and len(important_lines) < max_lines:
                    # Skip if matches exclusion pattern
                    if self.exclude_regex and self.exclude_regex.search(line):
                        continue
                    if not any(line.strip() in existing for existing in important_lines):
                        important_lines.append(line.strip())
        
        return '\n'.join(important_lines) if important_lines else log_content[:2000]  # Fallback to first 2000 chars
