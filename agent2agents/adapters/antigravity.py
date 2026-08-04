import json
import os

from ..canonical import Conversation, Message, utc_timestamp


class AntigravityTranscriptAdapter:
    """Import Antigravity brain transcripts into canonical conversations."""

    def __init__(self, target_cwd=None, brain_dir=None):
        self.target_cwd = os.path.abspath(target_cwd or os.getcwd())
        self.brain_dir = os.path.abspath(
            os.path.expanduser(brain_dir or "~/.gemini/antigravity-cli/brain")
        )

    def transcript_path(self, session_id):
        return os.path.join(
            self.brain_dir,
            session_id,
            ".system_generated",
            "logs",
            "transcript.jsonl",
        )

    @staticmethod
    def _clean_user_text(content):
        text = content or ""
        if "<USER_REQUEST>" in text:
            text = text.split("<USER_REQUEST>", 1)[1].split("</USER_REQUEST>", 1)[0]
        return text.strip()

    def read(self, session_id):
        path = self.transcript_path(session_id)
        if not os.path.exists(path):
            raise FileNotFoundError("Antigravity transcript not found: {}".format(path))

        messages = []
        created_at = None
        updated_at = None
        with open(path, "r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    step = json.loads(line)
                except json.JSONDecodeError:
                    continue
                timestamp = utc_timestamp(step.get("created_at"))
                created_at = created_at or timestamp
                updated_at = timestamp
                step_type = step.get("type")
                content = step.get("content", "")

                if step_type == "USER_INPUT":
                    text = self._clean_user_text(content)
                    if (
                        not text
                        or "<IMPORTED_CONVERSATION_HISTORY>" in text
                        or "Initializing imported session history." in text
                    ):
                        continue
                    messages.append(
                        Message(
                            role="user",
                            content=[{"type": "text", "text": text}],
                            timestamp=timestamp,
                        )
                    )
                elif step_type == "PLANNER_RESPONSE" and content:
                    text = str(content).strip()
                    if text and text != "No response requested.":
                        messages.append(
                            Message(
                                role="assistant",
                                content=[{"type": "text", "text": text}],
                                timestamp=timestamp,
                            )
                        )

        return Conversation(
            source_agent="antigravity",
            cwd=self.target_cwd,
            session_id=session_id,
            created_at=created_at or utc_timestamp(),
            updated_at=updated_at or created_at or utc_timestamp(),
            messages=messages,
            metadata={"source_path": path},
        )


__all__ = ["AntigravityTranscriptAdapter"]
