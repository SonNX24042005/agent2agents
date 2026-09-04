import json
import tempfile
import unittest
from pathlib import Path

from agent2agents import ClaudeToAntigravityConverter
from agent2agents.adapters.antigravity_session_writer import (
    AntigravitySessionWriter,
)
from agent2agents.converters.claude_to_antigravity import (
    ConversationToAntigravityConverter as LegacyConversationToAntigravityConverter,
)
from agent2agents.converters.conversation_to_antigravity import (
    ConversationToAntigravityConverter,
)


class ClaudeToAntigravityConverterTests(unittest.TestCase):
    def test_parses_claude_jsonl_before_native_export(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "claude-session.jsonl"
            records = [
                {
                    "sessionId": "claude-session",
                    "type": "user",
                    "timestamp": "2026-01-01T01:02:03.123Z",
                    "message": {"role": "user", "content": "User question"},
                },
                {
                    "sessionId": "claude-session",
                    "type": "assistant",
                    "timestamp": "2026-01-01T01:02:04.123Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Assistant answer"}],
                    },
                },
            ]
            source.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            converter = ClaudeToAntigravityConverter(
                claude_jsonl_path=source,
                target_cwd=temp_dir,
            )
            conversation = converter.parse_claude_jsonl()

            self.assertIsInstance(converter, AntigravitySessionWriter)
            self.assertEqual(conversation.source_agent, "claude_code")
            self.assertEqual(converter.session_id, "claude-session")
            self.assertEqual(
                converter.qa_pairs[0]["user"],
                "User question",
            )
            self.assertEqual(
                converter.qa_pairs[0]["assistant"],
                "Assistant answer",
            )

    def test_previous_direct_import_resolves_to_the_new_module(self):
        self.assertIs(
            LegacyConversationToAntigravityConverter,
            ConversationToAntigravityConverter,
        )

    def test_previous_payload_helper_api_remains_available(self):
        encoded = ClaudeToAntigravityConverter.encode_varint(300)
        self.assertEqual(
            ClaudeToAntigravityConverter.decode_varint(encoded, 0),
            (300, len(encoded)),
        )


if __name__ == "__main__":
    unittest.main()
