import unittest

from agent2agents import ConversationToClaudeConverter, ConversationToCodexConverter
from agent2agents.converters.conversation_to_agent import (
    ConversationToClaudeConverter as LegacyConversationToClaudeConverter,
)
from agent2agents.converters.conversation_to_agent import (
    ConversationToCodexConverter as LegacyConversationToCodexConverter,
)
from agent2agents.converters.conversation_to_claude import (
    ConversationToClaudeConverter as TargetSpecificConversationToClaudeConverter,
)
from agent2agents.converters.conversation_to_codex import (
    ConversationToCodexConverter as TargetSpecificConversationToCodexConverter,
)


class ConverterImportCompatibilityTests(unittest.TestCase):
    def test_legacy_and_public_imports_resolve_to_target_specific_classes(self):
        self.assertIs(
            LegacyConversationToClaudeConverter,
            TargetSpecificConversationToClaudeConverter,
        )
        self.assertIs(
            LegacyConversationToCodexConverter,
            TargetSpecificConversationToCodexConverter,
        )
        self.assertIs(
            ConversationToClaudeConverter,
            TargetSpecificConversationToClaudeConverter,
        )
        self.assertIs(
            ConversationToCodexConverter,
            TargetSpecificConversationToCodexConverter,
        )


if __name__ == "__main__":
    unittest.main()
