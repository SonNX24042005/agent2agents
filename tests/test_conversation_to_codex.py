import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent2agents.adapters.codex import CodexRolloutAdapter
from agent2agents.canonical import Conversation, Message
from agent2agents.converters.conversation_to_codex import (
    ConversationToCodexConverter,
)


class ConversationToCodexConverterTests(unittest.TestCase):
    def test_writes_a_codex_rollout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "rollout.jsonl"
            conversation = Conversation(
                source_agent="test",
                cwd=temp_dir,
                messages=[
                    Message(
                        role="user",
                        content=[{"type": "text", "text": "Question"}],
                    ),
                    Message(
                        role="assistant",
                        content=[{"type": "text", "text": "Answer"}],
                    ),
                ],
            )

            with mock.patch.object(
                CodexRolloutAdapter,
                "_codex_cli_version",
                return_value="test",
            ):
                converter = ConversationToCodexConverter(
                    conversation,
                    output_path=output_path,
                )
                exported = converter.convert()

            self.assertEqual(exported, str(output_path.resolve()))
            self.assertEqual(converter.output_path, str(output_path.resolve()))
            self.assertIsNotNone(converter.session_id)
            self.assertTrue(output_path.is_file())


if __name__ == "__main__":
    unittest.main()
