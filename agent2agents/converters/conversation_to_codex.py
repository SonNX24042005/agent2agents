"""Export canonical conversations as local Codex rollouts."""

from ..adapters.codex import CodexRolloutAdapter


def _has_text_turns(conversation):
    return any(
        message.role in ("user", "assistant") and message.text()
        for message in conversation.messages
    )


class ConversationToCodexConverter:
    """Export a canonical conversation as a local Codex rollout."""

    def __init__(self, conversation, codex_home=None, output_path=None):
        self.conversation = conversation
        self.codex_home = codex_home
        self.output_path = output_path
        self.session_id = None

    def convert(self):
        if not _has_text_turns(self.conversation):
            raise ValueError("No text user-assistant turns found in the conversation!")
        exporter = CodexRolloutAdapter(codex_home=self.codex_home)
        output_path, session_id = exporter.write(
            self.conversation,
            output_path=self.output_path,
        )
        self.output_path = output_path
        self.session_id = session_id
        return output_path


__all__ = ["ConversationToCodexConverter"]
