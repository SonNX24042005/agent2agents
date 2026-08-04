import tempfile
import unittest
import json
from pathlib import Path
from unittest import mock

from agent2agents.adapters.claude_code import ClaudeCodeAdapter
from agent2agents.adapters.codex import CodexRolloutAdapter
from agent2agents.canonical import Conversation, Message
from agent2agents.converters.conversation_to_agent import ConversationToClaudeConverter


class AllRouteTests(unittest.TestCase):
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

    def test_codex_to_claude_round_trip_keeps_text_turns(self):
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

    def test_codex_session_picker_is_limited_to_the_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            other_project = root / "other"
            project.mkdir()
            other_project.mkdir()
            codex_home = root / "codex-home"

            with mock.patch.object(
                CodexRolloutAdapter, "_codex_cli_version", return_value="test"
            ):
                current_path, current_id = CodexRolloutAdapter(
                    codex_home=codex_home
                ).write(self.conversation(project))
                CodexRolloutAdapter(codex_home=codex_home).write(
                    self.conversation(other_project)
                )

            sessions = CodexRolloutAdapter(codex_home=codex_home).get_project_sessions(
                target_cwd=project
            )
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["id"], current_id)
            self.assertEqual(sessions[0]["path"], str(current_path))

    def test_codex_reader_falls_back_to_event_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "event-only.jsonl"
            records = [
                {
                    "type": "session_meta",
                    "payload": {"id": "event-session", "cwd": temp_dir},
                },
                {
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Câu hỏi"},
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": "Câu trả lời",
                    },
                },
            ]
            source.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            conversation = CodexRolloutAdapter().read(source)
            self.assertEqual(
                [message.text() for message in conversation.messages],
                ["Câu hỏi", "Câu trả lời"],
            )


if __name__ == "__main__":
    unittest.main()
