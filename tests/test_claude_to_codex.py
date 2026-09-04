import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent2agents.adapters.codex import CodexRolloutAdapter
from agent2agents.converters.claude_to_codex import ClaudeToCodexConverter


class ClaudeToCodexConverterTests(unittest.TestCase):
    def test_writes_resumeable_rollout_with_text_turns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            source = root / "claude-session.jsonl"
            source.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "user",
                                "message": {
                                    "role": "user",
                                    "content": "<local-command-stdout>ignored</local-command-stdout>",
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "user",
                                "timestamp": "2026-01-01T01:02:03.123Z",
                                "message": {"role": "user", "content": "Tạo báo cáo"},
                            }
                        ),
                        json.dumps(
                            {
                                "type": "assistant",
                                "message": {
                                    "role": "assistant",
                                    "content": [
                                        {"type": "text", "text": "Đã tạo xong."},
                                        {"type": "tool_use", "name": "ignored_tool"},
                                        {"type": "text", "text": "Bạn có thể kiểm tra."},
                                    ],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "user",
                                "timestamp": "2026-01-01T01:03:03.123Z",
                                "message": {"role": "user", "content": "Mở rộng báo cáo"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                CodexRolloutAdapter, "_codex_cli_version", return_value="test"
            ):
                converter = ClaudeToCodexConverter(
                    claude_jsonl_path=source,
                    target_cwd=project,
                    codex_home=root / "codex-home",
                )
                output_path = Path(converter.convert())

            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.parents[4], root / "codex-home")
            self.assertRegex(output_path.name, r"^rollout-\d{4}-\d{2}-\d{2}T.*\.jsonl$")

            records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["type"], "session_meta")
            self.assertEqual(records[0]["payload"]["cwd"], str(project.resolve()))
            self.assertEqual(records[0]["payload"]["id"], converter.codex_session_id)

            response_roles = [
                record["payload"]["role"]
                for record in records
                if record["type"] == "response_item"
                and record["payload"].get("type") == "message"
            ]
            self.assertEqual(response_roles, ["user", "assistant", "user"])

            response_texts = [
                record["payload"]["content"][0]["text"]
                for record in records
                if record["type"] == "response_item"
                and record["payload"].get("type") == "message"
            ]
            self.assertEqual(
                response_texts,
                ["Tạo báo cáo", "Đã tạo xong.\n\nBạn có thể kiểm tra.", "Mở rộng báo cáo"],
            )

            assistant_phases = [
                record["payload"]["phase"]
                for record in records
                if record["type"] == "response_item"
                and record["payload"].get("type") == "message"
                and record["payload"].get("role") == "assistant"
            ]
            self.assertEqual(assistant_phases, ["final_answer"])
            self.assertIsNotNone(
                next(
                    record["payload"]["internal_chat_message_metadata_passthrough"]
                    for record in records
                    if record["type"] == "response_item"
                    and record["payload"].get("type") == "message"
                    and record["payload"].get("role") == "assistant"
                )["turn_id"]
            )

            user_events = [
                record["payload"]["message"]
                for record in records
                if record["type"] == "event_msg"
                and record["payload"].get("type") == "user_message"
            ]
            self.assertEqual(user_events, ["Tạo báo cáo", "Mở rộng báo cáo"])

            restored = CodexRolloutAdapter().read(output_path)
            self.assertEqual(restored.source_agent, "codex")
            self.assertEqual(restored.cwd, str(project.resolve()))
            self.assertEqual(
                [message.role for message in restored.messages],
                ["user", "assistant", "user"],
            )
            self.assertEqual(
                [message.text() for message in restored.messages],
                [
                    "Tạo báo cáo",
                    "Đã tạo xong.\n\nBạn có thể kiểm tra.",
                    "Mở rộng báo cáo",
                ],
            )

    def test_rejects_transcript_without_user_turns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "empty.jsonl"
            source.write_text("{\"type\":\"assistant\",\"message\":{}}\n", encoding="utf-8")
            converter = ClaudeToCodexConverter(
                claude_jsonl_path=source,
                codex_home=Path(temp_dir) / "codex-home",
            )

            with self.assertRaises(ValueError):
                converter.convert()


if __name__ == "__main__":
    unittest.main()
