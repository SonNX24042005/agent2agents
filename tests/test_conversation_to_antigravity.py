import unittest
from unittest import mock

from agent2agents.canonical import Conversation, Message
from agent2agents.converters.conversation_to_antigravity import (
    ConversationToAntigravityConverter,
)


class ConversationToAntigravityConverterTests(unittest.TestCase):
    def test_uses_the_native_session_writer(self):
        conversation = Conversation(
            source_agent="test",
            cwd="/tmp/project",
            messages=[
                Message(role="user", content=[{"type": "text", "text": "Question"}]),
                Message(
                    role="assistant",
                    content=[{"type": "text", "text": "Answer"}],
                ),
            ],
        )
        converter = ConversationToAntigravityConverter(conversation)

        with mock.patch.object(
            converter,
            "create_native_session",
            return_value="new-session",
        ) as create_native_session:
            self.assertEqual(converter.convert(), "new-session")

        create_native_session.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
