import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


CANONICAL_FORMAT = "agent2agents.conversation"
CANONICAL_VERSION = 1


def utc_timestamp(value=None):
    """Normalize a timestamp to the RFC3339 UTC form used by adapters."""
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z")
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _text_from_content(content: Iterable[Dict[str, Any]]) -> str:
    text_parts = []
    for part in content or []:
        if not isinstance(part, dict):
            continue
        if part.get("type") in ("text", "input_text", "output_text"):
            text = part.get("text")
            if isinstance(text, str) and text:
                text_parts.append(text)
    return "\n\n".join(text_parts).strip()


@dataclass
class Message:
    """A provider-neutral conversation message.

    ``content`` deliberately remains a list of dictionaries. This keeps the
    canonical format extensible for tool calls, tool results, images, and
    provider-specific records without making every adapter understand every
    provider's schema.
    """

    role: str
    content: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_timestamp)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        return _text_from_content(self.content)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.message_id,
            "role": self.role,
            "timestamp": utc_timestamp(self.timestamp),
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Message":
        return cls(
            role=value.get("role", "unknown"),
            content=value.get("content") or [],
            timestamp=utc_timestamp(value.get("timestamp")),
            message_id=value.get("id") or str(uuid.uuid4()),
            metadata=value.get("metadata") or {},
        )


@dataclass
class Conversation:
    """The hub format shared by every source and destination adapter."""

    source_agent: str
    cwd: str
    session_id: Optional[str] = None
    created_at: str = field(default_factory=utc_timestamp)
    updated_at: str = field(default_factory=utc_timestamp)
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.updated_at = message.timestamp

    def first_user_text(self) -> str:
        for message in self.messages:
            if message.role == "user" and message.text():
                return message.text()
        return "Imported conversation"

    def to_qa_pairs(self) -> List[Dict[str, str]]:
        """Project the rich format to the user/assistant turns older adapters need."""
        pairs = []
        current_user = None
        current_timestamp = None
        assistant_parts = []

        def flush_current():
            if current_user is not None:
                pairs.append(
                    {
                        "user": current_user,
                        "assistant": "\n\n".join(assistant_parts).strip(),
                        "timestamp": current_timestamp or utc_timestamp(),
                    }
                )

        for message in self.messages:
            if message.role == "user":
                text = message.text()
                if not text:
                    continue
                flush_current()
                current_user = text
                current_timestamp = message.timestamp
                assistant_parts = []
            elif message.role == "assistant" and current_user is not None:
                text = message.text()
                if text:
                    assistant_parts.append(text)

        flush_current()
        return pairs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": CANONICAL_FORMAT,
            "version": CANONICAL_VERSION,
            "session": {
                "id": self.session_id,
                "source_agent": self.source_agent,
                "cwd": self.cwd,
                "created_at": utc_timestamp(self.created_at),
                "updated_at": utc_timestamp(self.updated_at),
                "metadata": self.metadata,
            },
            "messages": [message.to_dict() for message in self.messages],
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Conversation":
        session = value.get("session") or {}
        if value.get("format") not in (None, CANONICAL_FORMAT):
            raise ValueError("Unsupported canonical conversation format")
        version = value.get("version", CANONICAL_VERSION)
        if version != CANONICAL_VERSION:
            raise ValueError("Unsupported canonical conversation version: {}".format(version))

        return cls(
            source_agent=session.get("source_agent", "unknown"),
            cwd=os.path.abspath(session.get("cwd") or os.getcwd()),
            session_id=session.get("id"),
            created_at=utc_timestamp(session.get("created_at")),
            updated_at=utc_timestamp(session.get("updated_at")),
            messages=[Message.from_dict(item) for item in value.get("messages", [])],
            metadata=session.get("metadata") or {},
        )

    def write_jsonl(self, path: str) -> str:
        """Persist the hub representation for inspection or future re-routing."""
        target = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "format": CANONICAL_FORMAT,
                        "version": CANONICAL_VERSION,
                        "type": "session",
                        "session": self.to_dict()["session"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            for message in self.messages:
                stream.write(
                    json.dumps(
                        {"type": "message", "message": message.to_dict()},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        return target

    @classmethod
    def read_jsonl(cls, path: str) -> "Conversation":
        session = None
        messages = []
        with open(path, "r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("type") == "session":
                    session = record
                elif record.get("type") == "message":
                    messages.append(Message.from_dict(record.get("message") or {}))
        if session is None:
            raise ValueError("Canonical conversation is missing its session record")
        payload = {
            "format": session.get("format"),
            "version": session.get("version"),
            "session": session.get("session"),
            "messages": [message.to_dict() for message in messages],
        }
        return cls.from_dict(payload)


__all__ = [
    "CANONICAL_FORMAT",
    "CANONICAL_VERSION",
    "Conversation",
    "Message",
    "utc_timestamp",
]
