import glob
import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List

from ..canonical import Conversation, Message, utc_timestamp


class ClaudeCodeAdapter:
    """Import/export adapter for Claude Code's project JSONL sessions."""

    _INTERNAL_USER_TAGS = re.compile(
        r"^\s*<(local-command|command-name|command-message|command-stdout|"
        r"local-command-caveat|task-notification)"
    )

    def __init__(self, target_cwd=None):
        self.target_cwd = os.path.abspath(target_cwd or os.getcwd())

    @classmethod
    def clean_user_text(cls, text):
        if not text or not isinstance(text, str):
            return ""
        if cls._INTERNAL_USER_TAGS.match(text):
            return ""
        if "<ide_opened_file>" in text:
            text = text.split("</ide_opened_file>")[-1]
        return text.strip()

    @staticmethod
    def _raw_part(item):
        return {
            "type": "raw",
            "source_type": item.get("type", "unknown"),
            "data": item,
        }

    @classmethod
    def _parts_from_content(cls, content, user_content=False):
        if isinstance(content, str):
            text = cls.clean_user_text(content) if user_content else content.strip()
            if text == "No response requested.":
                return []
            return [{"type": "text", "text": text}] if text else []

        if not isinstance(content, list):
            return []

        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text":
                text = item.get("text", "")
                text = cls.clean_user_text(text) if user_content else text.strip()
                if text and text != "No response requested.":
                    parts.append({"type": "text", "text": text})
            elif item_type == "thinking":
                text = item.get("thinking") or item.get("text") or ""
                if text:
                    parts.append({"type": "thinking", "text": text})
            elif item_type == "tool_use":
                parts.append(
                    {
                        "type": "tool_call",
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "arguments": item.get("input"),
                    }
                )
            elif item_type == "tool_result":
                parts.append(
                    {
                        "type": "tool_result",
                        "tool_call_id": item.get("tool_use_id"),
                        "content": item.get("content"),
                        "is_error": bool(item.get("is_error")),
                    }
                )
            else:
                parts.append(cls._raw_part(item))
        return parts

    @classmethod
    def _messages_from_user_record(cls, data):
        content = data.get("message", {}).get("content")
        if isinstance(content, list):
            text_parts = []
            tool_parts = []
            other_parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_result":
                    tool_parts.extend(cls._parts_from_content([item]))
                elif item.get("type") == "text":
                    text_parts.extend(cls._parts_from_content([item], user_content=True))
                else:
                    other_parts.extend(cls._parts_from_content([item], user_content=True))

            messages = []
            if text_parts or other_parts:
                messages.append(Message(role="user", content=text_parts + other_parts))
            if tool_parts:
                messages.append(Message(role="tool", content=tool_parts))
            return messages

        parts = cls._parts_from_content(content, user_content=True)
        return [Message(role="user", content=parts)] if parts else []

    @classmethod
    def _messages_from_assistant_record(cls, data):
        content = data.get("message", {}).get("content")
        parts = cls._parts_from_content(content)
        return [Message(role="assistant", content=parts)] if parts else []

    def read(self, path):
        source_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(source_path):
            raise FileNotFoundError("Claude JSONL file not found: {}".format(source_path))

        session_id = None
        messages = []
        created_at = None
        updated_at = None
        with open(source_path, "r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                session_id = session_id or data.get("sessionId")
                timestamp = utc_timestamp(data.get("timestamp"))
                created_at = created_at or timestamp
                updated_at = timestamp
                record_type = data.get("type")

                if record_type == "user":
                    record_messages = self._messages_from_user_record(data)
                elif record_type == "assistant":
                    record_messages = self._messages_from_assistant_record(data)
                elif record_type == "system":
                    parts = self._parts_from_content(data.get("message", {}).get("content"))
                    record_messages = [Message(role="system", content=parts)] if parts else []
                else:
                    record_messages = []

                for message in record_messages:
                    message.timestamp = timestamp
                    message.metadata["source_record_type"] = record_type
                    messages.append(message)

        conversation = Conversation(
            source_agent="claude_code",
            cwd=self.target_cwd,
            session_id=session_id,
            created_at=created_at or utc_timestamp(),
            updated_at=updated_at or created_at or utc_timestamp(),
            messages=messages,
            metadata={"source_path": source_path},
        )
        return conversation

    @staticmethod
    def get_project_sessions(target_cwd=None):
        target_cwd = os.path.abspath(target_cwd or os.getcwd())
        sanitized = "-" + target_cwd.strip("/").replace("/", "-")
        projects_dir = os.path.expanduser("~/.claude/projects")
        target_folder = os.path.join(projects_dir, sanitized)
        if not os.path.exists(target_folder):
            return []

        jsonl_files = glob.glob(os.path.join(target_folder, "*.jsonl"))
        jsonl_files.sort(key=os.path.getmtime, reverse=True)
        adapter = ClaudeCodeAdapter(target_cwd=target_cwd)
        sessions = []
        for path in jsonl_files:
            first_prompt = "Unknown prompt"
            try:
                first_prompt = adapter.read(path).first_user_text()
            except (OSError, ValueError, json.JSONDecodeError):
                pass
            sessions.append(
                {
                    "path": path,
                    "mtime": datetime.fromtimestamp(os.path.getmtime(path)).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "first_prompt": first_prompt,
                    "filename": os.path.basename(path),
                }
            )
        return sessions

    def write(self, conversation, target_path, session_id=None):
        """Export canonical text messages to a Claude-compatible JSONL file."""
        target = os.path.abspath(os.path.expanduser(target_path))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        exported_session_id = session_id or conversation.session_id or str(uuid.uuid4())
        parent_uuid = None
        records = []

        for message in conversation.messages:
            text = message.text()
            if not text or message.role not in ("user", "assistant"):
                continue
            record_uuid = str(uuid.uuid4())
            if message.role == "user":
                records.append(
                    {
                        "parentUuid": parent_uuid,
                        "isSidechain": False,
                        "promptId": str(uuid.uuid4()),
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": text}],
                        },
                        "uuid": record_uuid,
                        "timestamp": utc_timestamp(message.timestamp),
                        "userType": "external",
                        "entrypoint": "agent2agents",
                        "cwd": conversation.cwd,
                        "sessionId": exported_session_id,
                        "version": "agent2agents",
                    }
                )
            else:
                records.append(
                    {
                        "parentUuid": parent_uuid,
                        "isSidechain": False,
                        "type": "assistant",
                        "uuid": record_uuid,
                        "timestamp": utc_timestamp(message.timestamp),
                        "message": {
                            "id": str(uuid.uuid4()),
                            "model": "claude-3-5-sonnet",
                            "role": "assistant",
                            "type": "message",
                            "content": [{"type": "text", "text": text}],
                        },
                        "cwd": conversation.cwd,
                        "sessionId": exported_session_id,
                        "version": "agent2agents",
                    }
                )
            parent_uuid = record_uuid

        with open(target, "w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return target


__all__ = ["ClaudeCodeAdapter"]
