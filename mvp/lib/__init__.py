"""Cross-cutting utilities for the MVP.

``lib`` contains pure engineering code: hashing, date parsing, PDF text
extraction, SEC EDGAR HTTP, and the Anthropic SDK wrapper. It does not
load YAML configs, does not know about skills, and does not depend on any
other layer.

Only the data-carrying types are re-exported here. Client classes
(:class:`mvp.lib.edgar.EdgarClient`, :class:`mvp.lib.llm.LlmClient`) must
be imported from their modules so it's visible to reviewers which layer
constructs them.
"""

from .citation import Citation
from .llm import LlmResponse

__all__ = ["Citation", "LlmResponse"]
