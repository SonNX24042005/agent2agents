import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from agent2agents.adapters.antigravity_session_writer import AntigravitySessionWriter
from agent2agents.canonical import Conversation, Message


class AntigravitySessionWriterTests(unittest.TestCase):
    def test_creates_native_session_files_and_database_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            session_id = "new-antigravity-session"
            conversation = Conversation(
                source_agent="test",
                cwd=str(home / "project"),
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
            writer = AntigravitySessionWriter(
                target_cwd=conversation.cwd,
                conversation=conversation,
            )

            def initialize_native_database(*_args, **_kwargs):
                conversations_dir = (
                    home / ".gemini" / "antigravity-cli" / "conversations"
                )
                database_path = conversations_dir / f"{session_id}.db"
                user_inner = b"\x12\x04orig\x60\x01" + (b"u" * 520)
                user_payload = (
                    b"\x9a\x01"
                    + writer.encode_varint(len(user_inner))
                    + user_inner
                )
                assistant_inner = b"\x0a\x04orig\x10\x02" + (b"a" * 120)
                assistant_payload = (
                    b"\xa2\x01"
                    + writer.encode_varint(len(assistant_inner))
                    + assistant_inner
                )
                metadata = b"00000000-0000-0000-0000-000000000000"

                connection = sqlite3.connect(database_path)
                connection.execute(
                    """
                    CREATE TABLE steps (
                        idx INTEGER,
                        step_type INTEGER,
                        status INTEGER,
                        has_subtrajectory INTEGER,
                        metadata BLOB,
                        error_details BLOB,
                        permissions BLOB,
                        task_details BLOB,
                        render_info BLOB,
                        step_payload BLOB,
                        step_format INTEGER
                    )
                    """
                )
                connection.executemany(
                    """
                    INSERT INTO steps (
                        idx, step_type, status, has_subtrajectory, metadata,
                        error_details, permissions, task_details, render_info,
                        step_payload, step_format
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            0,
                            14,
                            3,
                            0,
                            metadata,
                            None,
                            None,
                            None,
                            None,
                            user_payload,
                            0,
                        ),
                        (
                            1,
                            15,
                            3,
                            0,
                            metadata,
                            None,
                            None,
                            None,
                            None,
                            assistant_payload,
                            0,
                        ),
                    ],
                )
                connection.commit()
                connection.close()
                return SimpleNamespace(returncode=0)

            with mock.patch.dict(os.environ, {"HOME": str(home)}), mock.patch(
                "agent2agents.adapters.antigravity_session_writer.subprocess.run",
                side_effect=initialize_native_database,
            ):
                created_session_id = writer.create_native_session()

            self.assertEqual(created_session_id, session_id)

            database_path = (
                home
                / ".gemini"
                / "antigravity-cli"
                / "conversations"
                / f"{session_id}.db"
            )
            connection = sqlite3.connect(database_path)
            rows = connection.execute(
                "SELECT step_type, step_payload FROM steps ORDER BY idx"
            ).fetchall()
            connection.close()
            self.assertEqual([row[0] for row in rows], [14, 15])
            self.assertIn(b"Question", rows[0][1])
            self.assertIn(b"Answer", rows[1][1])

            transcript_path = (
                home
                / ".gemini"
                / "antigravity-cli"
                / "brain"
                / session_id
                / ".system_generated"
                / "logs"
                / "transcript.jsonl"
            )
            transcript = [
                json.loads(line)
                for line in transcript_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [step["type"] for step in transcript],
                ["USER_INPUT", "PLANNER_RESPONSE"],
            )
            self.assertIn("Question", transcript[0]["content"])
            self.assertEqual(transcript[1]["content"], "Answer")

            summary_database = (
                home / ".gemini" / "antigravity-cli" / "conversation_summaries.db"
            )
            connection = sqlite3.connect(summary_database)
            summary = connection.execute(
                "SELECT conversation_id, step_count FROM conversation_summaries"
            ).fetchone()
            connection.close()
            self.assertEqual(summary, (session_id, 2))


if __name__ == "__main__":
    unittest.main()
