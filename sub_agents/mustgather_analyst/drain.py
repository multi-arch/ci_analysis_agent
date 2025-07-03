import os
import logging
from typing import Tuple, Generator, Dict, List, Any, Optional

import drain3
from drain3.template_miner_config import TemplateMinerConfig
from mcp.server.fastmcp import FastMCP



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


class DrainExtractor:
    """A class that extracts information from logs using a template miner algorithm."""

    def __init__(self, verbose: bool = False, context: bool = False, max_clusters=8):
        config = TemplateMinerConfig()
        config.load(f"{os.path.dirname(__file__)}/drain3.ini")
        config.profiling_enabled = verbose
        config.drain_max_clusters = max_clusters
        self.miner = drain3.TemplateMiner(config=config)
        self.verbose = verbose
        self.context = context

    def __call__(self, log: str) -> list[Tuple[int, str]]:
        out = []
        # First pass create clusters
        for _, chunk in get_chunks(log):
            processed_chunk = self.miner.add_log_message(chunk)
            LOG.debug(processed_chunk)
        # Sort found clusters by size, descending order
        sorted_clusters = sorted(
            self.miner.drain.clusters, key=lambda it: it.size, reverse=True
        )
        # Second pass, only matching lines with clusters,
        # to recover original text
        for chunk_start, chunk in get_chunks(log):
            cluster = self.miner.match(chunk, "always")
            if cluster in sorted_clusters:
                out.append((chunk_start, chunk))
                sorted_clusters.remove(cluster)
        return out






