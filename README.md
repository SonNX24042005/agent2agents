# Agent2Agents

Bộ công cụ chuyển đổi lịch sử hội thoại giữa **Claude Code (`.jsonl`)**, **Antigravity CLI (`agy`)** và **Codex**, hỗ trợ tự động lọc session theo từng dự án (Strict Project Scope).

---

## Giới thiệu

Khi chạy `a2a`, menu sẽ cho chọn agent nguồn và agent đích:

- **Claude Code -> Antigravity**: Chuyển các phiên làm việc từ Claude Code sang Antigravity để tiếp tục đoạn chat.
- **Claude Code -> Codex**: Tạo local Codex rollout từ phiên Claude để tiếp tục bằng lệnh `codex resume`.
- **Antigravity -> Claude Code**: Xuất phiên làm việc từ Antigravity về định dạng Claude Code `.jsonl`.
- **Antigravity -> Codex**: Tạo local Codex rollout từ phiên Antigravity.
- **Codex -> Claude Code**: Xuất rollout Codex thành session Claude Code.
- **Codex -> Antigravity**: Tạo native Antigravity session từ rollout Codex.
- **Lọc theo dự án**: Tự động nhận diện thư mục hiện tại để chỉ hiển thị các phiên chat thuộc đúng dự án đó.

`agent2agents` là alias tương thích của `a2a`. Các alias trực tiếp bỏ qua menu luồng, đi thẳng tới menu chọn session phù hợp. Sau khi chuyển xong, agent đích sẽ tự động được mở với session mới. Chúng chỉ là entrypoint tiện dụng, không phải package riêng.

## Kiến trúc chuyển đổi

Dự án dùng mô hình trung tâm:

```text
Claude Code ─┐
Antigravity ─┼─> agent2agents.conversation v1 ─> agent mong muốn
Codex ───────┘
```

Cấu trúc chính:

```text
agent2agents/
├── canonical.py              # Định dạng hội thoại trung gian, versioned
├── adapters/
│   ├── claude_code.py                    # Claude Code ↔ canonical
│   ├── antigravity.py                    # Transcript Antigravity → canonical
│   ├── antigravity_session_writer.py     # Canonical → session Antigravity
│   └── codex.py                          # Codex rollout ↔ canonical
├── codecs/
│   └── antigravity_payload_codec.py      # Mã hóa payload protobuf Antigravity
├── converters/
│   ├── claude_to_antigravity.py          # Workflow Claude → Antigravity
│   ├── claude_to_codex.py                # Workflow Claude → Codex
│   ├── antigravity_to_claude.py          # Workflow Antigravity → Claude
│   ├── conversation_to_antigravity.py    # Canonical → Antigravity
│   ├── conversation_to_claude.py         # Canonical → Claude
│   ├── conversation_to_codex.py          # Canonical → Codex
│   └── conversation_to_agent.py          # Shim tương thích cho import cũ
└── cli.py                                # Entry point duy nhất
```

Cách này giảm số adapter cần viết từ O(n²) xuống O(n), dễ thêm agent mới và cho phép kiểm thử từng adapter độc lập. Định dạng trung gian vẫn giữ các content part mở rộng như tool call/tool result; adapter đích có thể bỏ qua những phần mà agent đó không hỗ trợ. Các route hiện tại giữ lại lịch sử user/assistant dạng văn bản; tool đang chạy, thinking nội bộ và kết quả tool cũ không được replay.

---

## Cài đặt nhanh bằng 1 câu lệnh (One-Line Install)

### 1. Trên Linux, macOS, WSL hoặc Git Bash (Windows)

Mở Terminal và dán câu lệnh sau:

```bash
curl -fsSL https://raw.githubusercontent.com/SonNX24042005/agent2agents/main/install.sh | bash
```

---

### 2. Trên Windows (PowerShell)

Mở PowerShell và dán câu lệnh sau:

```powershell
iwr -useb https://raw.githubusercontent.com/SonNX24042005/agent2agents/main/install.ps1 | iex
```

*Lưu ý: Sau khi cài đặt xong, hãy khởi động lại Terminal để hệ thống nhận các lệnh `a2a`, `agent2agents`, `claude2agy`, `claude2codex`, `agy2claude`, `agy2codex`, `codex2claude` và `codex2agy`.*

---

## Hướng dẫn sử dụng

Sau khi cài đặt, bạn di chuyển vào **thư mục dự án bất kỳ** và chạy lệnh:

### 1. Chọn agent nguồn và agent đích

```bash
cd /path/to/your-project
a2a
```
1. Chọn luồng chuyển đổi trong menu.
2. Chọn session tương ứng với luồng đã chọn.
3. Công cụ tự động chạy agent đích và mở cuộc hội thoại vừa chuyển.

---

### 2. Dùng alias để bỏ qua menu agent

```bash
claude2agy       # Claude Code -> Antigravity, chọn session Claude
claude2codex     # Claude Code -> Codex, chọn session Claude
agy2claude       # Antigravity -> Claude Code, chọn session Antigravity
agy2codex        # Antigravity -> Codex, chọn session Antigravity
codex2claude     # Codex -> Claude Code, chọn rollout Codex
codex2agy        # Codex -> Antigravity, chọn rollout Codex
```

### 3. Chuyển từ Antigravity sang Claude Code bằng cờ

```bash
cd /path/to/your-project
a2a --reverse
```
1. Chọn phiên chat Antigravity muốn chuyển đổi từ menu.
2. File `.jsonl` sẽ tự động xuất vào thư mục của Claude Code (`~/.claude/projects/`), sau đó Claude Code sẽ được mở bằng session vừa tạo.

### 4. Chuyển từ Claude Code sang Codex bằng cờ

```bash
cd /path/to/your-project
a2a --codex
```

Rollout sẽ được ghi vào `~/.codex/sessions/YYYY/MM/DD/`, sau đó `codex resume <SESSION_ID>` sẽ tự động được chạy.

Codex chỉ nhận lại phần văn bản user/assistant. Tool call, tool result và trạng thái chạy của Claude không thể replay nên được bỏ qua.

---

## Cài đặt thủ công (Manual Installation)

Nếu không dùng 1-line install, bạn có thể clone dự án thủ công:

```bash
git clone https://github.com/SonNX24042005/agent2agents.git agent2agents
cd agent2agents

# Cách A: Dùng ngay bằng script
chmod +x run.sh
./run.sh                  # Claude Code -> Antigravity
./run.sh --reverse        # Antigravity -> Claude Code
./run.sh --codex          # Claude Code -> Codex
./run.sh --agy-to-codex   # Antigravity -> Codex
./run.sh --codex-to-claude
./run.sh --codex-to-agy   # Codex -> Antigravity

# Cách B: Cài đặt lệnh vào hệ thống bằng pip
pip install -e .
```

---

## Các tùy chọn dòng lệnh (Command-line Arguments)

| Tham số | Ý nghĩa | Ví dụ |
| :--- | :--- | :--- |
| `-f`, `--file` | Chỉ định file session nguồn `.jsonl` của Claude hoặc Codex | `a2a --codex-to-claude -f /path/to/rollout.jsonl` |
| `--antigravity` | Claude Code -> Antigravity, bỏ qua menu agent | `a2a --antigravity` |
| `--reverse` | Chuyển Antigravity sang Claude Code | `a2a --reverse` |
| `--codex` | Chuyển file Claude Code sang Codex rollout | `a2a --codex -f /path/to/session.jsonl` |
| `--agy-to-codex` | Antigravity -> Codex | `a2a --agy-to-codex` |
| `--codex-to-claude` | Codex -> Claude Code | `a2a --codex-to-claude` |
| `--codex-to-agy` | Codex -> Antigravity | `a2a --codex-to-agy` |
| `-o`, `--output` | Ghi file đích vào đường dẫn chỉ định | `a2a --codex -o /tmp/import.jsonl` |
| `-s`, `--session` | Chỉ định Antigravity Session ID | `a2a --reverse -s 2c3ed564-11bb-435c-b8f5` |
| `-c`, `--cwd` | Chỉ định đường dẫn dự án đích | `a2a -c /path/to/target/project` |
| `-u`, `--update`, `--upgrade`, `--pull` | Cập nhật công cụ lên phiên bản mới nhất từ GitHub | `a2a --update` hoặc `a2a --upgrade` |
| `-v`, `--version` | Hiển thị thông tin phiên bản hiện tại | `a2a --version` |
| `--no-launch` | Chỉ chuyển đổi, không tự động mở agent đích | `a2a --codex --no-launch` |

Các alias tương đương:

```text
agent2agents  = a2a
claude2agy    = a2a --antigravity
claude2codex  = a2a --codex
agy2claude    = a2a --reverse
agy2codex     = a2a --agy-to-codex
codex2claude  = a2a --codex-to-claude
codex2agy     = a2a --codex-to-agy
```

---

## Xử lý sự cố thường gặp

### 1. Lỗi "No Claude session logs (.jsonl) found..."
- **Nguyên nhân**: Thư mục hiện tại chưa từng được sử dụng với Claude Code hoặc chưa có file log trong `~/.claude/projects/`.
- **Khắc phục**: Di chuyển (`cd`) chính xác vào thư mục dự án mà bạn đã chạy Claude Code trước đó.

### 2. Lỗi "command not found: a2a" sau khi cài đặt
- **Khắc phục**: 
  - Khởi động lại Terminal.
  - Hoặc thêm `export PATH="$HOME/.local/bin:$PATH"` vào file `~/.bashrc` (hoặc `~/.zshrc`).
