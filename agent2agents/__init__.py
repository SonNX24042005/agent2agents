"""Agent-to-agent conversation migration primitives and adapters."""

from .canonical import CANONICAL_FORMAT, CANONICAL_VERSION, Conversation, Message
from .converters import (
    AntigravityToClaudeConverter,
    ClaudeToAntigravityConverter,
    ClaudeToCodexConverter,
    ConversationToAntigravityConverter,
    ConversationToClaudeConverter,
    ConversationToCodexConverter,
)

__all__ = [
    "CANONICAL_FORMAT",
    "CANONICAL_VERSION",
    "Conversation",
    "Message",
    "AntigravityToClaudeConverter",
    "ClaudeToAntigravityConverter",
    "ClaudeToCodexConverter",
    "ConversationToAntigravityConverter",
    "ConversationToClaudeConverter",
    "ConversationToCodexConverter",
]

__version__ = "1.5.1"
