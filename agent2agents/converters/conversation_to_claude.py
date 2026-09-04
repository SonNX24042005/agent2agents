"""Export canonical conversations as Claude Code project sessions."""

import os
import uuid

from ..adapters.claude_code import ClaudeCodeAdapter


def _has_text_turns(conversation):
    return any(
        message.role in ("user", "assistant") and message.text()
        for message in conversation.messages
    )


class ConversationToClaudeConverter:
    """Export a canonical conversation as a Claude Code project session."""

    def __init__(self, conversation, target_cwd=None, session_id=None, output_path=None):
        self.conversation = conversation
        self.target_cwd = os.path.abspath(target_cwd or conversation.cwd or os.getcwd())
        # A reverse conversion creates a new Claude session. Do not reuse the
        # source ID and risk overwriting an existing Claude transcript.
        self.session_id = session_id or str(uuid.uuid4())
        self.output_path = output_path

    def _default_output_path(self):
        sanitized = "-" + self.target_cwd.strip("/").replace("/", "-")
        project_dir = os.path.expanduser(os.path.join("~/.claude/projects", sanitized))
        return os.path.join(project_dir, "{}.jsonl".format(self.session_id))

    def convert(self):
        if not _has_text_turns(self.conversation):
            raise ValueError("No text user-assistant turns found in the conversation!")
        target = self.output_path or self._default_output_path()
        exported_file = ClaudeCodeAdapter(target_cwd=self.target_cwd).write(
            self.conversation,
            target,
            session_id=self.session_id,
        )
        self.output_path = exported_file
        return exported_file


__all__ = ["ConversationToClaudeConverter"]
