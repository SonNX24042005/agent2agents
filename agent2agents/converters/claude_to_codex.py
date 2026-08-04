import os

from ..adapters.claude_code import ClaudeCodeAdapter
from ..adapters.codex import CodexRolloutAdapter


class ClaudeToCodexConverter:
    """Convert a Claude Code session through canonical format into Codex."""

    def __init__(self, claude_jsonl_path=None, target_cwd=None, codex_home=None, output_path=None):
        self.target_cwd = os.path.abspath(target_cwd or os.getcwd())
        self.claude_jsonl_path = (
            os.path.abspath(claude_jsonl_path) if claude_jsonl_path else None
        )
        self.codex_home = codex_home
        self.output_path = output_path
        self.codex_session_id = None
        self.session_id = None
        self.conversation = None
        self.qa_pairs = []
        self.user_messages = []
        self.assistant_messages = []

    @staticmethod
    def clean_user_text(text):
        return ClaudeCodeAdapter.clean_user_text(text)

    @staticmethod
    def get_project_sessions(target_cwd=None):
        return ClaudeCodeAdapter.get_project_sessions(target_cwd=target_cwd)

    def parse_claude_jsonl(self):
        if not self.claude_jsonl_path:
            raise FileNotFoundError("Claude JSONL file path is required")
        print("📖 Parsing Claude JSONL log: {}".format(self.claude_jsonl_path))
        self.conversation = ClaudeCodeAdapter(target_cwd=self.target_cwd).read(
            self.claude_jsonl_path
        )
        self.qa_pairs = self.conversation.to_qa_pairs()
        self.user_messages = [pair["user"] for pair in self.qa_pairs]
        self.assistant_messages = [
            pair["assistant"] for pair in self.qa_pairs if pair.get("assistant")
        ]
        self.session_id = self.conversation.session_id
        print("✅ Extracted {} clean user-assistant QA turns.".format(len(self.qa_pairs)))
        return self.conversation

    def convert(self):
        if self.conversation is None:
            self.parse_claude_jsonl()
        if not self.qa_pairs:
            raise ValueError("No valid user-assistant turns found in the Claude JSONL file!")

        print("📝 Writing Codex rollout session...")
        exporter = CodexRolloutAdapter(codex_home=self.codex_home)
        output_path, session_id = exporter.write(
            self.conversation,
            output_path=self.output_path,
        )
        self.codex_session_id = session_id
        self.session_id = session_id
        print("✅ Imported {} Claude turns into Codex.".format(len(self.qa_pairs)))
        print("🎉 Codex session ID: {}".format(session_id))
        print("📄 Rollout file: {}".format(output_path))
        return output_path
