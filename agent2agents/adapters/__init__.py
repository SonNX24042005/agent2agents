"""Source and destination adapters for the canonical conversation format."""

from .antigravity import AntigravityTranscriptAdapter
from .claude_code import ClaudeCodeAdapter
from .codex import CodexRolloutAdapter

__all__ = [
    "AntigravityTranscriptAdapter",
    "ClaudeCodeAdapter",
    "CodexRolloutAdapter",
]
