"""Workflow for importing a Claude Code session into Antigravity."""

import os

from ..adapters.antigravity_session_writer import AntigravitySessionWriter
from ..adapters.claude_code import ClaudeCodeAdapter
from .conversation_to_antigravity import ConversationToAntigravityConverter


class ClaudeToAntigravityConverter(AntigravitySessionWriter):
    """Read a Claude Code session and write a native Antigravity session."""

    def __init__(
        self,
        claude_jsonl_path=None,
        target_cwd=None,
        conversation=None,
    ):
        self.claude_jsonl_path = (
            os.path.abspath(claude_jsonl_path) if claude_jsonl_path else None
        )
        super().__init__(target_cwd=target_cwd, conversation=conversation)

    @staticmethod
    def get_project_sessions(target_cwd=None):
        """Discover Claude sessions through the Claude Code adapter."""
        return ClaudeCodeAdapter.get_project_sessions(target_cwd=target_cwd)

    @staticmethod
    def clean_user_text(text):
        return ClaudeCodeAdapter.clean_user_text(text)

    def parse_claude_jsonl(self):
        """Parse Claude JSONL into the shared canonical conversation format."""
        if not self.claude_jsonl_path or not os.path.exists(self.claude_jsonl_path):
            raise FileNotFoundError(
                f"Claude JSONL file not found: {self.claude_jsonl_path}"
            )

        print(f"📖 Parsing Claude JSONL log: {self.claude_jsonl_path}")
        conversation = ClaudeCodeAdapter(target_cwd=self.target_cwd).read(
            self.claude_jsonl_path
        )
        self.set_conversation(conversation)
        print(f"✅ Extracted {len(self.qa_pairs)} clean user-assistant QA turns.")
        return self.conversation


__all__ = [
    "ClaudeToAntigravityConverter",
    "ConversationToAntigravityConverter",
]
