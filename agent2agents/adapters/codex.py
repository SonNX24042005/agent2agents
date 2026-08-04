import json
import glob
import os
import subprocess
import uuid
from datetime import datetime

from ..canonical import Conversation, Message, utc_timestamp


class CodexRolloutAdapter:
    """Import/export adapter for Codex's local rollout JSONL format."""

    def __init__(self, codex_home=None):
        configured_home = codex_home or os.environ.get("CODEX_HOME") or "~/.codex"
        self.codex_home = os.path.abspath(os.path.expanduser(configured_home))

    @staticmethod
    def _codex_cli_version():
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            version = (result.stdout or result.stderr).strip()
            if version:
                return version[:120]
        except (OSError, subprocess.SubprocessError):
            pass
        return "agent2agents"

    @staticmethod
    def _line(timestamp, record_type, payload):
        return {"timestamp": timestamp, "type": record_type, "payload": payload}

    @staticmethod
    def _message_id():
        return "msg_{}".format(uuid.uuid4().hex)

    def _metadata(self, session_id, timestamp, conversation):
        return self._line(
            timestamp,
            "session_meta",
            {
                "session_id": session_id,
                "id": session_id,
                "timestamp": timestamp,
                "cwd": conversation.cwd,
                "originator": "agent2agents",
                "cli_version": self._codex_cli_version(),
                "source": "cli",
                "thread_source": "user",
                "model_provider": "openai",
                "base_instructions": None,
                "context_window": None,
                "history_mode": "legacy",
                "git": None,
            },
        )

    def _user_response_item(self, text, timestamp):
        return self._line(
            timestamp,
            "response_item",
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
                "id": self._message_id(),
                "phase": None,
                "internal_chat_message_metadata_passthrough": None,
            },
        )

    def _user_event(self, text, timestamp):
        return self._line(
            timestamp,
            "event_msg",
            {
                "type": "user_message",
                "message": text,
                "images": [],
                "local_images": [],
                "audio": [],
                "local_audio": [],
                "text_elements": [],
            },
        )

    def _assistant_event(self, text, timestamp):
        return self._line(
            timestamp,
            "event_msg",
            {
                "type": "agent_message",
                "message": text,
                "phase": "final",
                "memory_citation": None,
            },
        )

    def _assistant_response_item(self, text, timestamp):
        return self._line(
            timestamp,
            "response_item",
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
                "id": self._message_id(),
                "phase": "final",
                "internal_chat_message_metadata_passthrough": None,
            },
        )

    def _default_output_path(self, session_id, timestamp):
        current = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        session_dir = os.path.join(
            self.codex_home,
            "sessions",
            current.strftime("%Y"),
            current.strftime("%m"),
            current.strftime("%d"),
        )
        filename = "rollout-{}-{}.jsonl".format(
            current.strftime("%Y-%m-%dT%H-%M-%S"), session_id
        )
        return os.path.join(session_dir, filename)

    def get_project_sessions(self, target_cwd=None):
        """List Codex rollouts whose recorded working directory matches a project."""
        target_cwd = os.path.abspath(target_cwd or os.getcwd())
        pattern = os.path.join(
            self.codex_home,
            "sessions",
            "*",
            "*",
            "*",
            "rollout-*.jsonl",
        )
        paths = glob.glob(pattern)
        paths.sort(key=os.path.getmtime, reverse=True)

        sessions = []
        for path in paths:
            try:
                conversation = self.read(path, target_cwd=target_cwd)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if os.path.abspath(conversation.cwd) != target_cwd:
                continue
            sessions.append(
                {
                    "path": path,
                    "id": conversation.session_id,
                    "mtime": datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "first_prompt": conversation.first_user_text(),
                }
            )
        return sessions

    def write(self, conversation, output_path=None):
        """Write a canonical conversation as a Codex rollout.

        Returns ``(path, session_id)``. The created ID is local to this
        rollout; it does not create a remote OpenAI conversation.
        """
        session_id = str(uuid.uuid4())
        session_timestamp = utc_timestamp()
        target = os.path.abspath(os.path.expanduser(output_path)) if output_path else None
        target = target or self._default_output_path(session_id, session_timestamp)
        os.makedirs(os.path.dirname(target), exist_ok=True)

        records = [self._metadata(session_id, session_timestamp, conversation)]
        for message in conversation.messages:
            if message.role not in ("user", "assistant"):
                continue
            text = message.text()
            if not text:
                continue
            timestamp = utc_timestamp(message.timestamp)
            if message.role == "user":
                records.append(self._user_response_item(text, timestamp))
                records.append(self._user_event(text, timestamp))
            else:
                records.append(self._assistant_event(text, timestamp))
                records.append(self._assistant_response_item(text, timestamp))

        created = False
        try:
            with open(target, "x", encoding="utf-8") as stream:
                created = True
                for record in records:
                    stream.write(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
        except Exception:
            if created:
                try:
                    os.unlink(target)
                except OSError:
                    pass
            raise

        return target, session_id

    def read(self, path, target_cwd=None):
        """Read text message items from a Codex rollout into canonical form."""
        source_path = os.path.abspath(os.path.expanduser(path))
        session = {}
        messages = []
        event_messages = []
        with open(source_path, "r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                # Codex has used both a nested ``payload`` envelope and a
                # flattened rollout line across releases. Accept both so
                # the adapter can import old and newer local sessions.
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    payload = record
                record_type = record.get("type")
                if record_type == "session_meta":
                    session = payload
                elif record_type == "response_item":
                    # Some exporters flatten the response item one level
                    # further and omit its inner ``type: message`` tag.
                    if payload.get("type") != "message" and payload.get("role") in (
                        "user",
                        "assistant",
                    ):
                        payload = dict(payload)
                        payload["type"] = "message"
                    if payload.get("type") != "message":
                        continue
                    role = payload.get("role")
                    if role not in ("user", "assistant"):
                        continue
                    content = payload.get("content") or []
                    text = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") in (
                            "input_text",
                            "output_text",
                        ):
                            if part.get("text"):
                                text.append(part["text"])
                    if text:
                        messages.append(
                            Message(
                                role=role,
                                content=[{"type": "text", "text": "\n\n".join(text)}],
                                timestamp=utc_timestamp(record.get("timestamp")),
                            )
                        )
                elif record_type == "event_msg":
                    event_type = payload.get("type")
                    role = {
                        "user_message": "user",
                        "agent_message": "assistant",
                    }.get(event_type)
                    text = payload.get("message")
                    if role and isinstance(text, str) and text.strip():
                        event_messages.append(
                            Message(
                                role=role,
                                content=[{"type": "text", "text": text}],
                                timestamp=utc_timestamp(record.get("timestamp")),
                            )
                        )

        # Prefer the rollout's recorded project. ``target_cwd`` is only a
        # fallback for older files that did not store a session directory.
        cwd = session.get("cwd") or target_cwd or os.getcwd()
        if not messages:
            messages = event_messages
        return Conversation(
            source_agent="codex",
            cwd=os.path.abspath(cwd),
            session_id=session.get("id") or session.get("session_id"),
            created_at=utc_timestamp(session.get("timestamp")),
            updated_at=utc_timestamp(),
            messages=messages,
            metadata={"source_path": source_path},
        )


__all__ = ["CodexRolloutAdapter"]
