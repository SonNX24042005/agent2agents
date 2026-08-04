import os
import sqlite3

from ..adapters.antigravity import AntigravityTranscriptAdapter
from ..adapters.claude_code import ClaudeCodeAdapter

class AntigravityToClaudeConverter:
    def __init__(self, session_id=None, target_cwd=None):
        self.target_cwd = os.path.abspath(target_cwd or os.getcwd())
        self.session_id = session_id
        self.brain_dir = os.path.expanduser("~/.gemini/antigravity-cli/brain")

    @staticmethod
    def get_agy_sessions(target_cwd=None):
        """List ONLY Antigravity sessions strictly belonging to the target project directory."""
        target_cwd = os.path.abspath(target_cwd or os.getcwd())
        summary_db = os.path.expanduser("~/.gemini/antigravity-cli/conversation_summaries.db")
        sessions = []

        if os.path.exists(summary_db):
            try:
                conn = sqlite3.connect(summary_db)
                cursor = conn.cursor()
                # Strict filter by workspace_uris matching target_cwd
                cursor.execute(
                    "SELECT conversation_id, preview, last_modified_time FROM conversation_summaries WHERE workspace_uris LIKE ? ORDER BY last_modified_time DESC",
                    (f"%{target_cwd}%",)
                )
                rows = cursor.fetchall()
                conn.close()

                for row in rows:
                    sid, preview, mtime = row
                    sessions.append({
                        "id": sid,
                        "preview": preview if preview else "Antigravity Session",
                        "mtime": str(mtime)[:16]
                    })
            except Exception:
                pass

        return sessions

    def convert(self):
        """Convert AGY -> canonical conversation -> Claude Code JSONL."""
        if not self.session_id:
            raise ValueError("Session ID is required for reverse conversion!")

        # Create sanitized project folder name for ~/.claude/projects/
        sanitized_folder = "-" + self.target_cwd.strip("/").replace("/", "-")
        claude_project_dir = os.path.expanduser(f"~/.claude/projects/{sanitized_folder}")
        os.makedirs(claude_project_dir, exist_ok=True)

        target_claude_jsonl = os.path.join(claude_project_dir, f"{self.session_id}.jsonl")

        adapter = AntigravityTranscriptAdapter(
            target_cwd=self.target_cwd,
            brain_dir=self.brain_dir,
        )
        transcript_path = adapter.transcript_path(self.session_id)
        print(f"📖 Reading Antigravity session transcript: {transcript_path}")
        conversation = adapter.read(self.session_id)
        exported_file = ClaudeCodeAdapter(target_cwd=self.target_cwd).write(
            conversation,
            target_claude_jsonl,
            session_id=self.session_id,
        )

        record_count = sum(
            1
            for message in conversation.messages
            if message.role in ("user", "assistant") and message.text()
        )
        print(f"✅ Generated {record_count} Claude JSONL records.")

        print(f"🎉 Exported to Claude session file: {exported_file}")
        return exported_file
