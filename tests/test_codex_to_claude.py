import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent2agents.adapters.claude_code import ClaudeCodeAdapter
from agent2agents.adapters.codex import CodexRolloutAdapter
from agent2agents.canonical import Conversation, Message
from agent2agents.converters.conversation_to_claude import (
    ConversationToClaudeConverter,
)


class CodexToClaudeTests(unittest.TestCase):
    @staticmethod
    def conversation(cwd):
        return Conversation(
            source_agent="test",
            cwd=str(cwd),
            session_id="source-session",
            messages=[
                Message(role="user", content=[{"type": "text", "text": "Câu hỏi"}]),
                Message(
                    role="assistant",
                    content=[{"type": "text", "text": "Câu trả lời đầy đủ"}],
                ),
            ],
        )

    def test_round_trip_keeps_text_turns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            codex_home = root / "codex-home"

            with mock.patch.object(
                CodexRolloutAdapter, "_codex_cli_version", return_value="test"
            ):
                codex_path, codex_id = CodexRolloutAdapter(
                    codex_home=codex_home
                ).write(self.conversation(project))

            restored = CodexRolloutAdapter().read(codex_path, target_cwd=project)
            claude_path = root / "claude-export" / "session.jsonl"
            exported = ConversationToClaudeConverter(
                restored,
                target_cwd=project,
                session_id=codex_id,
                output_path=claude_path,
            ).convert()
            claude_conversation = ClaudeCodeAdapter(target_cwd=project).read(exported)

            self.assertEqual(
                [message.text() for message in claude_conversation.messages],
                ["Câu hỏi", "Câu trả lời đầy đủ"],
            )


if __name__ == "__main__":
    unittest.main()
