"""Export canonical conversations as native Antigravity sessions."""

from ..adapters.antigravity_session_writer import AntigravitySessionWriter


class ConversationToAntigravityConverter(AntigravitySessionWriter):
    """Export any canonical conversation to a native Antigravity session."""

    def __init__(self, conversation, target_cwd=None):
        super().__init__(target_cwd=target_cwd, conversation=conversation)

    def convert(self):
        if not self.qa_pairs:
            raise ValueError("No valid user-assistant turns found in the conversation!")
        return self.create_native_session()


__all__ = ["ConversationToAntigravityConverter"]
