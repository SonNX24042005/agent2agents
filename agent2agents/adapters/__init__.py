"""Source and destination adapters for the canonical conversation format."""

from .antigravity import AntigravityTranscriptAdapter
from .antigravity_session_writer import AntigravitySessionWriter
from .claude_code import ClaudeCodeAdapter
from .codex import CodexRolloutAdapter

__all__ = [
    "AntigravityTranscriptAdapter",
    "AntigravitySessionWriter",
    "ClaudeCodeAdapter",
    "CodexRolloutAdapter",
]
