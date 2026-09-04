import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent2agents.adapters.codex import CodexRolloutAdapter
from agent2agents.canonical import Conversation, Message


class CodexRolloutAdapterTests(unittest.TestCase):
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

    def test_session_title_ignores_injected_instructions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            codex_home = root / "codex-home"
            session_dir = codex_home / "sessions" / "2026" / "09" / "04"
            session_dir.mkdir(parents=True)
            rollout_path = session_dir / "rollout-session.jsonl"
            records = [
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "session-id",
                        "cwd": str(project),
                        "timestamp": "2026-09-04T01:02:03.000Z",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "# AGENTS.md instructions\n\n"
                                    "<INSTRUCTIONS>Internal rules</INSTRUCTIONS>"
                                ),
                            },
                            {
                                "type": "input_text",
                                "text": (
                                    "<environment_context>Internal context"
                                    "</environment_context>"
                                ),
                            },
                        ],
                        "internal_chat_message_metadata_passthrough": {
                            "content_item_kinds": [
                                "agents_md.instructions",
                                "environments.environment_context",
                            ]
                        },
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "Câu hỏi thực tế của người dùng",
                            }
                        ],
                        "internal_chat_message_metadata_passthrough": {
                            "content_item_kinds": ["user.text"]
                        },
                    },
                },
            ]
            rollout_path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            adapter = CodexRolloutAdapter(codex_home=codex_home)
            conversation = adapter.read(rollout_path)
            sessions = adapter.get_project_sessions(target_cwd=project)

            self.assertEqual(
                [message.text() for message in conversation.messages],
                ["Câu hỏi thực tế của người dùng"],
            )
            self.assertEqual(len(sessions), 1)
            self.assertEqual(
                sessions[0]["first_prompt"],
                "Câu hỏi thực tế của người dùng",
            )

    def test_reader_preserves_user_text_in_a_mixed_content_record(self):
        payload = {
            "content": [
                {
                    "type": "input_text",
                    "text": "# AGENTS.md instructions\n<INSTRUCTIONS>Rules</INSTRUCTIONS>",
                },
                {"type": "input_text", "text": "Câu hỏi cần giữ lại"},
            ],
            "internal_chat_message_metadata_passthrough": {
                "content_item_kinds": [
                    "agents_md.instructions",
                    "user.text",
                ]
            },
        }

        self.assertEqual(
            CodexRolloutAdapter._response_message_text(payload, "user"),
            "Câu hỏi cần giữ lại",
        )

    def test_reader_filters_legacy_internal_context_without_metadata(self):
        payload = {
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "# AGENTS.md instructions\n\n"
                        "<INSTRUCTIONS>Internal rules</INSTRUCTIONS>"
                    ),
                }
            ]
        }

        self.assertEqual(
            CodexRolloutAdapter._response_message_text(payload, "user"),
            "",
        )

    def test_reader_preserves_user_text_beside_legacy_internal_context(self):
        payload = {
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "# AGENTS.md instructions\n\n"
                        "<INSTRUCTIONS>Internal rules</INSTRUCTIONS>"
                    ),
                },
                {"type": "input_text", "text": "Câu hỏi cần giữ lại"},
            ]
        }

        self.assertEqual(
            CodexRolloutAdapter._response_message_text(payload, "user"),
            "Câu hỏi cần giữ lại",
        )

    def test_reader_filters_contextual_content_kinds(self):
        internal_kinds = (
            "agents_md.instructions",
            "environments.environment_context",
            "skills.selected_skill_instructions",
            "permissions.instructions",
            "model_switch.instructions",
            "generic.turn_aborted",
        )
        for kind in internal_kinds:
            with self.subTest(kind=kind):
                payload = {
                    "content": [{"type": "input_text", "text": "Internal data"}],
                    "internal_chat_message_metadata_passthrough": {
                        "content_item_kinds": [kind]
                    },
                }
                self.assertEqual(
                    CodexRolloutAdapter._response_message_text(payload, "user"),
                    "",
                )

    def test_explicit_user_text_takes_precedence_over_marker_fallback(self):
        text = (
            "# AGENTS.md instructions\n"
            "<INSTRUCTIONS>Please explain this example</INSTRUCTIONS>"
        )
        payload = {
            "content": [{"type": "input_text", "text": text}],
            "internal_chat_message_metadata_passthrough": {
                "content_item_kinds": ["user.text"]
            },
        }

        self.assertEqual(
            CodexRolloutAdapter._response_message_text(payload, "user"),
            text,
        )

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

    def test_codex_writer_marks_intermediate_and_final_answers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            conversation = Conversation(
                source_agent="test",
                cwd=temp_dir,
                messages=[
                    Message(role="user", content=[{"type": "text", "text": "Hỏi"}]),
                    Message(
                        role="assistant",
                        content=[{"type": "text", "text": "Đang kiểm tra"}],
                    ),
                    Message(
                        role="assistant",
                        content=[{"type": "text", "text": "Đã xong"}],
                    ),
                ],
            )
            output_path = Path(temp_dir) / "rollout.jsonl"
            with mock.patch.object(
                CodexRolloutAdapter, "_codex_cli_version", return_value="test"
            ):
                CodexRolloutAdapter().write(conversation, output_path=output_path)

            phases = [
                record["payload"]["phase"]
                for record in (
                    json.loads(line)
                    for line in output_path.read_text(encoding="utf-8").splitlines()
                )
                if record["type"] == "response_item"
                and record["payload"].get("role") == "assistant"
            ]
            self.assertEqual(phases, ["commentary", "final_answer"])


if __name__ == "__main__":
    unittest.main()
