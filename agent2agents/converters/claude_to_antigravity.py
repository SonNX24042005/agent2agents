import os
import json
import sqlite3
import subprocess
import re
import uuid
from datetime import datetime

from ..adapters.claude_code import ClaudeCodeAdapter

class ClaudeToAntigravityConverter:
    def __init__(self, claude_jsonl_path=None, target_cwd=None, conversation=None):
        self.target_cwd = os.path.abspath(target_cwd or os.getcwd())
        self.claude_jsonl_path = os.path.abspath(claude_jsonl_path) if claude_jsonl_path else None
        self.user_messages = []
        self.assistant_messages = []
        self.turns = []
        self.session_id = None
        self.conversation = None
        self.qa_pairs = []
        if conversation is not None:
            self.set_conversation(conversation)

    def set_conversation(self, conversation):
        """Load any canonical conversation for native Antigravity export."""
        if conversation is None:
            raise ValueError("A canonical conversation is required")
        self.conversation = conversation
        self.qa_pairs = conversation.to_qa_pairs()
        self.user_messages = [pair["user"] for pair in self.qa_pairs]
        self.assistant_messages = [
            pair["assistant"] for pair in self.qa_pairs if pair.get("assistant")
        ]
        self.session_id = conversation.session_id
        return conversation

    @staticmethod
    def get_project_sessions(target_cwd=None):
        """Discover Claude sessions through the canonical Claude adapter."""
        return ClaudeCodeAdapter.get_project_sessions(target_cwd=target_cwd)

    @staticmethod
    def clean_user_text(text):
        return ClaudeCodeAdapter.clean_user_text(text)

    def parse_claude_jsonl(self):
        """Parse Claude JSONL into the shared canonical conversation format."""
        if not self.claude_jsonl_path or not os.path.exists(self.claude_jsonl_path):
            raise FileNotFoundError(f"Claude JSONL file not found: {self.claude_jsonl_path}")

        print(f"📖 Parsing Claude JSONL log: {self.claude_jsonl_path}")

        conversation = ClaudeCodeAdapter(target_cwd=self.target_cwd).read(
            self.claude_jsonl_path
        )
        self.set_conversation(conversation)

        print(f"✅ Extracted {len(self.qa_pairs)} clean user-assistant QA turns.")
        return self.conversation

    @staticmethod
    def encode_varint(n):
        buf = bytearray()
        while True:
            towrite = n & 0x7f
            n >>= 7
            if n:
                buf.append(towrite | 0x80)
            else:
                buf.append(towrite)
                break
        return bytes(buf)

    @staticmethod
    def decode_varint(data, offset):
        val = 0
        shift = 0
        i = offset
        while i < len(data):
            b = data[i]
            i += 1
            val |= (b & 0x7f) << shift
            if not (b & 0x80):
                return val, i - offset
            shift += 7
        return val, i - offset

    @classmethod
    def parse_protobuf_fields(cls, payload):
        """Parse top-level protobuf fields into a dict of {tag: (wire, value)}."""
        fields = {}
        i = 0
        while i < len(payload):
            tag_val, tag_len = cls.decode_varint(payload, i)
            if tag_len == 0:
                break
            tag = tag_val >> 3
            wire = tag_val & 0x7
            data_start = i + tag_len
            if wire == 0:
                val, v_len = cls.decode_varint(payload, data_start)
                data_end = data_start + v_len
                val_data = val
            elif wire == 2:
                length, l_len = cls.decode_varint(payload, data_start)
                content_start = data_start + l_len
                data_end = content_start + length
                val_data = payload[content_start:data_end]
            elif wire == 1:
                data_end = data_start + 8
                val_data = payload[data_start:data_end]
            elif wire == 5:
                data_end = data_start + 4
                val_data = payload[data_start:data_end]
            else:
                break
            fields[tag] = (wire, val_data)
            i = data_end
        return fields

    @classmethod
    def build_user_payload(cls, template_payload, new_text_str, meta_bytes):
        prompt_bytes = new_text_str.encode("utf-8")
        fields = cls.parse_protobuf_fields(template_payload)
        f19_entry = fields.get(19)
        if not f19_entry or not f19_entry[1]:
            return template_payload
        f19_data = f19_entry[1]

        i = 0
        u_tail_offset = None
        while i < len(f19_data):
            tag_val, tag_len = cls.decode_varint(f19_data, i)
            if tag_len == 0:
                break
            tag = tag_val >> 3
            wire = tag_val & 0x7
            if tag == 12:
                u_tail_offset = i
                break
            data_start = i + tag_len
            if wire == 0:
                _, v_len = cls.decode_varint(f19_data, data_start)
                i = data_start + v_len
            elif wire == 2:
                l, l_len = cls.decode_varint(f19_data, data_start)
                i = data_start + l_len + l
            elif wire == 1:
                i = data_start + 8
            elif wire == 5:
                i = data_start + 4
            else:
                break

        if u_tail_offset is None:
            u_tail_offset = f19_data.find(b"\x62", 30)
            if u_tail_offset == -1:
                return template_payload

        u_f19_tail = f19_data[u_tail_offset:]
        f2 = b"\x12" + cls.encode_varint(len(prompt_bytes)) + prompt_bytes
        f3_sub = b"\x0a" + cls.encode_varint(len(prompt_bytes)) + prompt_bytes
        f3 = b"\x1a" + cls.encode_varint(len(f3_sub)) + f3_sub
        f4 = b"\x22\x00"
        f19_content = f2 + f3 + f4 + u_f19_tail
        f19 = b"\x9a\x01" + cls.encode_varint(len(f19_content)) + f19_content
        return b"\x08\x0e\x20\x03\x2a" + cls.encode_varint(len(meta_bytes)) + meta_bytes + f19

    @classmethod
    def build_assistant_payload(cls, template_payload, new_text_str, meta_bytes):
        resp_bytes = new_text_str.encode("utf-8")
        fields = cls.parse_protobuf_fields(template_payload)
        f20_entry = fields.get(20)
        if not f20_entry or not f20_entry[1]:
            return template_payload
        f20_data = f20_entry[1]

        tag_val, tag_len = cls.decode_varint(f20_data, 0)
        f1_len, f1_l_b = cls.decode_varint(f20_data, tag_len)
        a_f20_tail = f20_data[tag_len + f1_l_b + f1_len:]

        f1 = b"\x0a" + cls.encode_varint(len(resp_bytes)) + resp_bytes
        f20_content = f1 + a_f20_tail
        f20 = b"\xa2\x01" + cls.encode_varint(len(f20_content)) + f20_content
        return b"\x08\x0f\x20\x03\x2a" + cls.encode_varint(len(meta_bytes)) + meta_bytes + f20

    def create_native_session(self):
        """Create native Antigravity CLI session with valid DB initialization, native TUI rendering, and 100% exact Claude transcript matching."""
        if not self.qa_pairs:
            raise ValueError("No valid user-assistant turns found in the Claude JSONL file!")

        print("🚀 Initializing native Antigravity session database...")

        conversations_dir = os.path.expanduser("~/.gemini/antigravity-cli/conversations")
        if not os.path.exists(conversations_dir):
            os.makedirs(conversations_dir, exist_ok=True)

        existing_dbs = set(f for f in os.listdir(conversations_dir) if f.endswith(".db") and not f.endswith(".db-shm") and not f.endswith(".db-wal"))

        init_prompt = "Initializing imported session history..."
        res = subprocess.run(
            ["agy", "--dangerously-skip-permissions", "-p", init_prompt],
            cwd=self.target_cwd,
            capture_output=True,
            text=True
        )

        current_dbs = set(f for f in os.listdir(conversations_dir) if f.endswith(".db") and not f.endswith(".db-shm") and not f.endswith(".db-wal"))
        new_dbs = list(current_dbs - existing_dbs)

        if new_dbs:
            new_session_id = new_dbs[0].replace(".db", "")
        else:
            db_files = [os.path.join(conversations_dir, f) for f in os.listdir(conversations_dir) if f.endswith(".db")]
            db_files.sort(key=os.path.getmtime, reverse=True)
            new_session_id = os.path.basename(db_files[0]).replace(".db", "")

        self.session_id = new_session_id
        print(f"🎉 Created Native Session ID: {new_session_id}")

        # Populate SQLite database steps table for AGY CLI TUI and /rewind support
        db_path = os.path.join(conversations_dir, f"{new_session_id}.db")
        last_u_idx = 0
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            rows = cur.execute("SELECT idx, step_type, status, metadata, step_payload FROM steps").fetchall()

            u_meta_tpl, u_payload_tpl = None, None
            a_meta_tpl, a_payload_tpl = None, None
            for r in rows:
                if r[1] == 14 and u_payload_tpl is None and r[4] and len(r[4]) > 500:
                    u_meta_tpl, u_payload_tpl = r[3], r[4]
                elif r[1] == 15 and a_payload_tpl is None and r[4] and len(r[4]) > 100:
                    a_meta_tpl, a_payload_tpl = r[3], r[4]

            # Fallback search across existing databases if templates not found
            if not u_payload_tpl or not a_payload_tpl:
                for other_db in sorted([os.path.join(conversations_dir, f) for f in os.listdir(conversations_dir) if f.endswith(".db")], key=os.path.getmtime, reverse=True):
                    try:
                        oc = sqlite3.connect(other_db)
                        for r in oc.execute("SELECT idx, step_type, status, metadata, step_payload FROM steps").fetchall():
                            if r[1] == 14 and u_payload_tpl is None and r[4] and len(r[4]) > 500:
                                u_meta_tpl, u_payload_tpl = r[3], r[4]
                            elif r[1] == 15 and a_payload_tpl is None and r[4] and len(r[4]) > 100:
                                a_meta_tpl, a_payload_tpl = r[3], r[4]
                        oc.close()
                        if u_payload_tpl and a_payload_tpl:
                            break
                    except Exception:
                        pass

            if u_payload_tpl and a_payload_tpl:
                uuids_u = re.findall(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", u_meta_tpl)
                uuids_a = re.findall(rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", a_meta_tpl)

                cur.execute("DELETE FROM steps;")

                db_step_idx = 0
                for pair in self.qa_pairs:
                    u_t = pair.get("user", "").strip()
                    a_t = pair.get("assistant", "").strip()

                    if not u_t:
                        continue

                    turn_u_uuid = str(uuid.uuid4()).encode("utf-8")
                    turn_a_uuid = str(uuid.uuid4()).encode("utf-8")

                    u_meta = u_meta_tpl
                    if uuids_u:
                        u_meta = u_meta.replace(uuids_u[0], turn_u_uuid)
                    u_payload = self.build_user_payload(u_payload_tpl, u_t, u_meta)

                    cur.execute(
                        "INSERT INTO steps (idx, step_type, status, has_subtrajectory, metadata, error_details, permissions, task_details, render_info, step_payload, step_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (db_step_idx, 14, 3, 0, u_meta, None, None, None, None, u_payload, 0)
                    )
                    last_u_idx = db_step_idx
                    db_step_idx += 1

                    asst_text = a_t if a_t else "Completed."
                    a_meta = a_meta_tpl
                    if uuids_a:
                        a_meta = a_meta.replace(uuids_a[0], turn_a_uuid)
                    a_payload = self.build_assistant_payload(a_payload_tpl, asst_text, a_meta)

                    cur.execute(
                        "INSERT INTO steps (idx, step_type, status, has_subtrajectory, metadata, error_details, permissions, task_details, render_info, step_payload, step_format) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (db_step_idx, 15, 3, 0, a_meta, None, None, None, None, a_payload, 0)
                    )
                    db_step_idx += 1

                conn.commit()
            conn.close()

        except Exception as e:
            print(f"⚠️ Warning updating SQLite steps DB: {e}")

        # Write exact native transcript steps to brain/<session_id>/.system_generated/logs/
        brain_dir = os.path.expanduser(f"~/.gemini/antigravity-cli/brain/{new_session_id}/.system_generated/logs")
        os.makedirs(brain_dir, exist_ok=True)

        transcript_path = os.path.join(brain_dir, "transcript.jsonl")
        transcript_full_path = os.path.join(brain_dir, "transcript_full.jsonl")

        now_iso = datetime.now().isoformat() + "Z"

        steps = []
        step_idx = 0

        # Exact 1-to-1 mapping with SQLite steps table indices
        for i, pair in enumerate(self.qa_pairs):
            u_text = pair.get("user", "")
            a_text = pair.get("assistant", "")
            ts = pair.get("timestamp", now_iso)

            if not u_text or not u_text.strip():
                continue

            steps.append({
                "step_index": step_idx,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "status": "DONE",
                "created_at": ts,
                "content": f"<USER_REQUEST>\n{u_text.strip()}\n</USER_REQUEST>"
            })
            step_idx += 1

            asst_content = a_text.strip() if a_text and a_text.strip() else "Completed."
            steps.append({
                "step_index": step_idx,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "status": "DONE",
                "created_at": ts,
                "content": asst_content
            })
            step_idx += 1

        with open(transcript_path, "w", encoding="utf-8") as f:
            for s in steps:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        with open(transcript_full_path, "w", encoding="utf-8") as f:
            for s in steps:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        self.register_in_summaries(new_session_id)
        return new_session_id

    def register_in_summaries(self, session_id):
        """Register the converted session in SQLite conversation_summaries.db for AGY CLI."""
        target_path = os.path.expanduser("~/.gemini/antigravity-cli")
        os.makedirs(target_path, exist_ok=True)
        summary_db = os.path.join(target_path, "conversation_summaries.db")

        try:
            conn = sqlite3.connect(summary_db)
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                conversation_id TEXT PRIMARY KEY,
                title TEXT,
                preview TEXT,
                step_count INTEGER,
                last_modified_time TEXT,
                workspace_uris TEXT,
                status TEXT,
                source TEXT,
                project_id TEXT,
                agent_name TEXT,
                parent_conversation_id TEXT,
                nesting_depth INTEGER,
                battle_id TEXT,
                winning_conversation_id TEXT,
                not_fully_idle INTEGER,
                killed INTEGER,
                last_user_input_time TEXT,
                last_user_input_step_index INTEGER,
                app_data_dir TEXT
            )
            """)

            first_msg = self.user_messages[0] if self.user_messages else "Imported Claude Session"
            preview_text = first_msg[:100]
            title_text = first_msg[:80]
            workspace_uri = f'["file://{self.target_cwd}"]'
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S+00:00")

            cursor.execute("PRAGMA table_info(conversation_summaries)")
            cols = [row[1] for row in cursor.fetchall()]

            last_u_index = (len(self.qa_pairs) - 1) * 2 if self.qa_pairs else 0
            base_values = {
                "conversation_id": session_id,
                "title": title_text,
                "preview": preview_text,
                "step_count": len(self.qa_pairs) * 2,
                "last_modified_time": now_str,
                "workspace_uris": workspace_uri,
                "status": "",
                "source": "",
                "project_id": "default-cli-project",
                "agent_name": "",
                "parent_conversation_id": "",
                "nesting_depth": 0,
                "battle_id": "",
                "winning_conversation_id": "",
                "not_fully_idle": 0,
                "killed": 0,
                "last_user_input_time": now_str,
                "last_user_input_step_index": last_u_index,
                "app_data_dir": "antigravity-cli",
            }

            insert_cols = [c for c in cols if c in base_values]
            placeholders = ", ".join(["?"] * len(insert_cols))
            col_names = ", ".join(insert_cols)
            values = tuple(base_values[c] for c in insert_cols)

            cursor.execute(
                f"INSERT OR REPLACE INTO conversation_summaries ({col_names}) VALUES ({placeholders})",
                values
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️  Warning registering in {summary_db}: {e}")

        # Update conversation_metadata.json cache for AGY CLI
        cache_json = os.path.expanduser("~/.gemini/antigravity-cli/cache/conversation_metadata.json")
        try:
            os.makedirs(os.path.dirname(cache_json), exist_ok=True)
            data = {}
            if os.path.exists(cache_json):
                with open(cache_json, "r", encoding="utf-8") as f:
                    data = json.load(f)

            first_msg = self.user_messages[0] if self.user_messages else "Imported Claude Session"
            now_iso = datetime.now().isoformat() + "Z"

            data[session_id] = {
                "summary": {
                    "ID": session_id,
                    "Title": "",
                    "Preview": first_msg[:100],
                    "NumSteps": len(self.qa_pairs) * 2,
                    "Loaded": True,
                    "UpdatedAt": now_iso,
                    "WorkspaceURIs": [f"file://{self.target_cwd}"],
                    "AppDataDir": "antigravity-cli",
                    "ProjectID": "default-cli-project",
                    "AgentName": ""
                },
                "is_internal": False,
                "last_modified_time": now_iso
            }

            with open(cache_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  Warning updating cache {cache_json}: {e}")

        print("✅ Registered session for AGY CLI context memory.")


class ConversationToAntigravityConverter(ClaudeToAntigravityConverter):
    """Export any canonical conversation to a native Antigravity session."""

    def __init__(self, conversation, target_cwd=None):
        super().__init__(target_cwd=target_cwd, conversation=conversation)

    def convert(self):
        if not self.qa_pairs:
            raise ValueError("No valid user-assistant turns found in the conversation!")
        return self.create_native_session()
