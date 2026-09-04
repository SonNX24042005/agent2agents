import tempfile
import unittest
from pathlib import Path

from agent2agents.canonical import Conversation, Message


class CanonicalConversationTests(unittest.TestCase):
    def test_round_trip_preserves_text_and_extended_content_parts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            conversation = Conversation(
                source_agent="test",
                cwd=temp_dir,
                messages=[
                    Message(
                        role="user",
                        content=[{"type": "text", "text": "Xin chào"}],
                    ),
                    Message(
                        role="assistant",
                        content=[
                            {"type": "text", "text": "Phản hồi"},
                            {"type": "tool_call", "name": "example"},
                        ],
                    ),
                ],
            )
            path = conversation.write_jsonl(
                str(Path(temp_dir) / "conversation.jsonl")
            )
            restored = Conversation.read_jsonl(path)

            self.assertEqual(restored.source_agent, "test")
            self.assertEqual(restored.messages[0].text(), "Xin chào")
            self.assertEqual(restored.messages[1].text(), "Phản hồi")
            self.assertEqual(restored.messages[1].content[1]["type"], "tool_call")


if __name__ == "__main__":
    unittest.main()
