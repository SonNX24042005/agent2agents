import argparse
import glob
import os
import platform
import subprocess
import sys

from .adapters.antigravity import AntigravityTranscriptAdapter
from .adapters.codex import CodexRolloutAdapter
from .converters import (
    AntigravityToClaudeConverter,
    ClaudeToAntigravityConverter,
    ClaudeToCodexConverter,
    ConversationToAntigravityConverter,
    ConversationToClaudeConverter,
    ConversationToCodexConverter,
)
from .menu import select_option
from . import __version__


CONVERSION_MODES = (
    ("claude_to_antigravity", "Claude Code  ->  Antigravity"),
    ("claude_to_codex", "Claude Code  ->  Codex"),
    ("antigravity_to_claude", "Antigravity  ->  Claude Code"),
    ("antigravity_to_codex", "Antigravity  ->  Codex"),
    ("codex_to_claude", "Codex  ->  Claude Code"),
    ("codex_to_antigravity", "Codex  ->  Antigravity"),
)


def mode_from_invocation(command_name=None):
    """Return the direct mode requested by a convenience command, if any."""
    command_name = os.path.basename(command_name or sys.argv[0]).lower()
    for suffix in (".cmd", ".exe"):
        if command_name.endswith(suffix):
            command_name = command_name[: -len(suffix)]
            break
    return {
        "claude2agy": "claude_to_antigravity",
        "claude2antigravity": "claude_to_antigravity",
        "claude2codex": "claude_to_codex",
        "agy2claude": "antigravity_to_claude",
        "agy2codex": "antigravity_to_codex",
        "codex2claude": "codex_to_claude",
        "codex2agy": "codex_to_antigravity",
        "codex2antigravity": "codex_to_antigravity",
    }.get(command_name)


def choose_mode(command_name=None):
    """Choose a conversion mode, unless a direct alias already selected it."""
    direct_mode = mode_from_invocation(command_name)
    if direct_mode:
        return direct_mode

    choice = select_option(
        [label for _, label in CONVERSION_MODES],
        title="Select a conversion: source agent -> target agent",
    )
    if choice is None or not 0 <= choice < len(CONVERSION_MODES):
        return None
    return CONVERSION_MODES[choice][0]


def launch_agent(command, cwd, enabled=True):
    """Start the target agent with the newly imported conversation."""
    command_text = " ".join(command)
    if not enabled:
        print(f"⏭️  Auto-start disabled. Run manually: {command_text}")
        return None

    print(f"🚀 Starting the new conversation with: {command_text}")
    try:
        result = subprocess.run(command, cwd=cwd, check=False)
    except FileNotFoundError:
        print(
            f"⚠️ Cannot start '{command[0]}': command not found. "
            f"Run manually: {command_text}",
            file=sys.stderr,
        )
        return None
    except KeyboardInterrupt:
        print("\n⏹️  Target agent stopped by user.")
        return 130

    if result.returncode != 0:
        print(
            f"⚠️ Target agent exited with code {result.returncode}: {command_text}",
            file=sys.stderr,
        )
    return result.returncode


def resolve_claude_session_path(input_val, target_cwd=None):
    """Resolve a user-provided Claude session ID, filename, or filepath to a JSONL path."""
    if not input_val or not str(input_val).strip():
        return None
    input_val = str(input_val).strip()

    # 1. Direct path check
    expanded = os.path.abspath(os.path.expanduser(input_val))
    if os.path.isfile(expanded):
        return expanded

    session_id = input_val[:-6] if input_val.endswith(".jsonl") else input_val

    # 2. Check in current project directory
    if target_cwd:
        sanitized = "-" + os.path.abspath(target_cwd).strip("/").replace("/", "-")
        project_dir = os.path.expanduser(os.path.join("~/.claude/projects", sanitized))
        candidate = os.path.join(project_dir, f"{session_id}.jsonl")
        if os.path.isfile(candidate):
            return candidate

    # 3. Search across all projects in ~/.claude/projects
    claude_projects_dir = os.path.expanduser("~/.claude/projects")
    if os.path.isdir(claude_projects_dir):
        pattern = os.path.join(claude_projects_dir, "*", f"*{session_id}*.jsonl")
        matches = glob.glob(pattern)
        if matches:
            matches.sort(key=os.path.getmtime, reverse=True)
            return matches[0]

    return expanded


def resolve_antigravity_session_id(input_val):
    """Clean and return an Antigravity session ID from input string or file path."""
    if not input_val or not str(input_val).strip():
        return None
    cleaned = str(input_val).strip()
    cleaned = os.path.basename(cleaned)
    if cleaned.endswith(".db"):
        cleaned = cleaned[:-3]
    return cleaned


def resolve_codex_session_path(input_val, codex_home=None):
    """Resolve a user-provided Codex session ID, filename, or filepath to a rollout JSONL path."""
    if not input_val or not str(input_val).strip():
        return None
    input_val = str(input_val).strip()

    # 1. Direct path check
    expanded = os.path.abspath(os.path.expanduser(input_val))
    if os.path.isfile(expanded):
        return expanded

    home = codex_home or os.environ.get("CODEX_HOME") or "~/.codex"
    home = os.path.abspath(os.path.expanduser(home))

    # 2. Search by session ID in ~/.codex/sessions/**/rollout-*.jsonl
    session_id = input_val
    if session_id.endswith(".jsonl"):
        session_id = session_id[:-6]
    if session_id.startswith("rollout-"):
        session_id = session_id[8:]

    pattern = os.path.join(home, "sessions", "*", "*", "*", f"*{session_id}*.jsonl")
    matches = glob.glob(pattern)
    if matches:
        matches.sort(key=os.path.getmtime, reverse=True)
        return matches[0]

    pattern_recursive = os.path.join(home, "sessions", "**", f"*{session_id}*.jsonl")
    matches = glob.glob(pattern_recursive, recursive=True)
    if matches:
        matches.sort(key=os.path.getmtime, reverse=True)
        return matches[0]

    return expanded


def select_claude_session(selected_file, target_cwd, purpose):
    """Return a Claude JSONL path selected within the current project or entered manually."""
    if selected_file:
        resolved = resolve_claude_session_path(selected_file, target_cwd)
        if resolved and os.path.isfile(resolved):
            return resolved
        return selected_file

    project_name = os.path.basename(target_cwd)
    sessions = ClaudeToAntigravityConverter.get_project_sessions(target_cwd=target_cwd)

    manual_label = "✍️  Enter Claude session ID or path manually"
    options_display = [manual_label]
    for session in sessions:
        prompt_snippet = session["first_prompt"][:75].replace("\n", " ")
        if len(session["first_prompt"]) > 75:
            prompt_snippet += "..."
        options_display.append(f"{session['mtime']} | {prompt_snippet}")

    choice_idx = select_option(
        options_display,
        title=f"🔍 Select a Claude Code session for {purpose} [{project_name}]:",
    )
    if choice_idx is None:
        print("❌ Selection cancelled by user.")
        sys.exit(0)

    if choice_idx == 0:
        manual_input = input("Enter Claude session ID or JSONL path: ").strip()
        if not manual_input:
            print("❌ No session ID or path provided.", file=sys.stderr)
            sys.exit(1)
        resolved_path = resolve_claude_session_path(manual_input, target_cwd)
        if not resolved_path or not os.path.isfile(resolved_path):
            print(f"❌ Claude session file not found: {manual_input}", file=sys.stderr)
            sys.exit(1)
        print(f"✅ Selected session: {os.path.basename(resolved_path)}\n")
        return resolved_path

    selected_session = sessions[choice_idx - 1]
    print(f"✅ Selected session: {selected_session['filename']}\n")
    return selected_session["path"]


def select_antigravity_session(selected_session, target_cwd, purpose):
    """Return an Antigravity session ID selected within the current project or entered manually."""
    if selected_session:
        return resolve_antigravity_session_id(selected_session)

    sessions = AntigravityToClaudeConverter.get_agy_sessions(target_cwd=target_cwd)

    manual_label = "✍️  Enter Antigravity session ID manually"
    options_display = [manual_label]
    for session in sessions:
        options_display.append(
            f"{session['mtime']} | [{session['id'][:8]}] {session['preview'][:60]}"
        )

    choice_idx = select_option(
        options_display,
        title=f"🔍 Select an Antigravity session for {purpose}:",
    )
    if choice_idx is None:
        print("❌ Selection cancelled by user.")
        sys.exit(0)

    if choice_idx == 0:
        manual_input = input("Enter Antigravity session ID: ").strip()
        if not manual_input:
            print("❌ No session ID provided.", file=sys.stderr)
            sys.exit(1)
        cleaned_id = resolve_antigravity_session_id(manual_input)
        print(f"✅ Selected session: {cleaned_id}\n")
        return cleaned_id

    selected = sessions[choice_idx - 1]
    print(f"✅ Selected session: {selected['id']}\n")
    return selected["id"]


def select_codex_session(selected_file, target_cwd, purpose):
    """Return a Codex rollout path selected within the current project or entered manually."""
    if selected_file:
        resolved = resolve_codex_session_path(selected_file)
        if resolved and os.path.isfile(resolved):
            return resolved
        return selected_file

    adapter = CodexRolloutAdapter()
    sessions = adapter.get_project_sessions(target_cwd=target_cwd)

    manual_label = "✍️  Enter Codex session ID or path manually"
    options_display = [manual_label]
    for session in sessions:
        session_id = session.get("id") or "unknown"
        prompt = session.get("first_prompt", "Imported conversation")
        prompt_snippet = prompt[:75].replace("\n", " ")
        if len(prompt) > 75:
            prompt_snippet += "..."
        options_display.append(
            f"{session['mtime']} | [{session_id[:8]}] {prompt_snippet}"
        )

    choice_idx = select_option(
        options_display,
        title=f"🔍 Select a Codex session for {purpose}:",
    )
    if choice_idx is None:
        print("❌ Selection cancelled by user.")
        sys.exit(0)

    if choice_idx == 0:
        manual_input = input("Enter Codex session ID or rollout JSONL path: ").strip()
        if not manual_input:
            print("❌ No session ID or path provided.", file=sys.stderr)
            sys.exit(1)
        resolved_path = resolve_codex_session_path(manual_input)
        if not resolved_path or not os.path.isfile(resolved_path):
            print(f"❌ Codex rollout file not found for: {manual_input}", file=sys.stderr)
            sys.exit(1)
        print(f"✅ Selected session: {os.path.basename(resolved_path)}\n")
        return resolved_path

    selected_session = sessions[choice_idx - 1]
    print(f"✅ Selected session: {os.path.basename(selected_session['path'])}\n")
    return selected_session["path"]


def update_tool():
    """Update the Agent2Agents installation."""
    print("🔄 Checking for updates and updating Agent2Agents...")
    
    current_script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    install_dirs = [
        os.path.expanduser("~/.agent2agents"),
    ]
    
    target_git_dir = None
    if os.path.exists(os.path.join(current_script_dir, ".git")):
        target_git_dir = current_script_dir
    else:
        for install_dir in install_dirs:
            if os.path.exists(os.path.join(install_dir, ".git")):
                target_git_dir = install_dir
                break

    if target_git_dir:
        print(f"📦 Git repository detected at: {target_git_dir}")
        print("🔄 Pulling latest changes from GitHub...")
        try:
            res = subprocess.run(["git", "-C", target_git_dir, "pull"], capture_output=True, text=True)
            if res.returncode == 0:
                print("✨ Update completed successfully!")
                print(res.stdout.strip())
                return True
            else:
                print(f"⚠️ Git pull notice: {res.stderr.strip()}")
        except Exception as e:
            print(f"⚠️ Git pull failed: {e}")

    # Fallback to online installer script
    print("📥 Running installer script to update...")
    is_windows = platform.system() == "Windows"
    
    local_installer_sh = os.path.join(current_script_dir, "install.sh")
    local_installer_ps = os.path.join(current_script_dir, "install.ps1")
    
    if not is_windows and os.path.exists(local_installer_sh):
        cmd = ["bash", local_installer_sh]
    elif is_windows and os.path.exists(local_installer_ps):
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", local_installer_ps]
    else:
        if is_windows:
            cmd = ["powershell", "-Command", "iwr -useb https://raw.githubusercontent.com/SonNX24042005/agent2agents/main/install.ps1 | iex"]
        else:
            cmd = ["bash", "-c", "curl -fsSL https://raw.githubusercontent.com/SonNX24042005/agent2agents/main/install.sh | bash"]

    try:
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print("\n✨ Agent2Agents updated successfully to the latest version!")
            return True
        else:
            print("\n❌ Update failed. Please check your network connection or try running the installer manually.")
            return False
    except Exception as e:
        print(f"\n❌ Error during update: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Agent2Agents: Convert conversations between Claude Code, Antigravity CLI, and Codex."
    )
    parser.add_argument(
        "--file", "-f",
        default=None,
        help="Source session file (.jsonl); Claude or Codex depending on the route.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--antigravity",
        action="store_true",
        help="Claude Code -> Antigravity without the route menu.",
    )
    mode_group.add_argument(
        "--reverse", "-r",
        action="store_true",
        help="Antigravity -> Claude Code without the route menu.",
    )
    mode_group.add_argument(
        "--codex",
        action="store_true",
        help="Claude Code -> Codex without the route menu.",
    )
    mode_group.add_argument(
        "--antigravity-to-codex", "--agy-to-codex",
        dest="antigravity_to_codex",
        action="store_true",
        help="Antigravity -> Codex without the route menu.",
    )
    mode_group.add_argument(
        "--codex-to-claude",
        dest="codex_to_claude",
        action="store_true",
        help="Codex -> Claude Code without the route menu.",
    )
    mode_group.add_argument(
        "--codex-to-antigravity", "--codex-to-agy",
        dest="codex_to_antigravity",
        action="store_true",
        help="Codex -> Antigravity without the route menu.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Optional destination path for a Codex rollout or Claude JSONL export.",
    )
    parser.add_argument(
        "--session", "-s",
        default=None,
        help="Antigravity Session ID for an Antigravity source route.",
    )
    parser.add_argument(
        "--cwd", "-c",
        default=os.getcwd(),
        help="Working directory path for the project (defaults to current directory).",
    )
    parser.add_argument(
        "--update", "-u",
        action="store_true",
        help="Update Agent2Agents from GitHub.",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version information.",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Convert the session but do not automatically start the target agent.",
    )

    args = parser.parse_args()

    if args.version:
        print(f"Agent2Agents v{__version__}")
        sys.exit(0)

    if args.update:
        success = update_tool()
        sys.exit(0 if success else 1)

    try:
        if args.antigravity:
            mode = "claude_to_antigravity"
        elif args.codex:
            mode = "claude_to_codex"
        elif args.reverse:
            mode = "antigravity_to_claude"
        elif args.antigravity_to_codex:
            mode = "antigravity_to_codex"
        elif args.codex_to_claude:
            mode = "codex_to_claude"
        elif args.codex_to_antigravity:
            mode = "codex_to_antigravity"
        else:
            mode = choose_mode()
            if mode is None:
                print("❌ Selection cancelled by user.")
                return

        if mode == "claude_to_codex":
            print("🔄 Claude Code -> Codex: converting session to Codex rollout JSONL...")
            selected_file = select_claude_session(args.file or args.session, args.cwd, "Codex")
            converter = ClaudeToCodexConverter(
                claude_jsonl_path=selected_file,
                target_cwd=args.cwd,
                output_path=args.output,
            )
            exported_file = converter.convert()
            session_id = converter.codex_session_id

            print("\n" + "=" * 60)
            print("✨ CLAUDE → CODEX CONVERSION COMPLETED SUCCESSFULLY!")
            print(f"📌 Codex Session ID: {session_id}")
            print(f"📄 Rollout JSONL: {exported_file}")
            print(f"\n   codex resume {session_id}\n")
            print("=" * 60)
            launch_agent(["codex", "resume", str(session_id)], args.cwd, not args.no_launch)

        elif mode == "claude_to_antigravity":
            print("🔄 Claude Code -> Antigravity: converting session...")
            selected_file = select_claude_session(args.file or args.session, args.cwd, "Antigravity")
            converter = ClaudeToAntigravityConverter(
                claude_jsonl_path=selected_file,
                target_cwd=args.cwd,
            )
            converter.parse_claude_jsonl()
            session_id = converter.create_native_session()

            print("\n" + "=" * 60)
            print("✨ CLAUDE → ANTIGRAVITY CONVERSION COMPLETED SUCCESSFULLY!")
            print(f"📌 Session ID: {session_id}")
            print(f"\n   agy --conversation {session_id}\n")
            print("=" * 60)
            launch_agent(["agy", "--conversation", str(session_id)], args.cwd, not args.no_launch)

        elif mode == "antigravity_to_claude":
            print("🔄 Antigravity -> Claude Code: converting session...")
            selected_session = select_antigravity_session(
                args.session or args.file, args.cwd, "Claude Code"
            )
            converter = AntigravityToClaudeConverter(
                session_id=selected_session,
                target_cwd=args.cwd,
            )
            exported_file = converter.convert()

            print("\n" + "=" * 60)
            print("✨ ANTIGRAVITY → CLAUDE CONVERSION COMPLETED SUCCESSFULLY!")
            print(f"📄 Exported Claude JSONL: {exported_file}")
            print(f"\n   claude --resume {selected_session}\n")
            print("=" * 60)
            launch_agent(["claude", "--resume", str(selected_session)], args.cwd, not args.no_launch)

        elif mode == "antigravity_to_codex":
            print("🔄 Antigravity -> Codex: converting session...")
            selected_session = select_antigravity_session(
                args.session or args.file, args.cwd, "Codex"
            )
            conversation = AntigravityTranscriptAdapter(target_cwd=args.cwd).read(
                selected_session
            )
            converter = ConversationToCodexConverter(
                conversation,
                output_path=args.output,
            )
            exported_file = converter.convert()
            session_id = converter.session_id

            print("\n" + "=" * 60)
            print("✨ ANTIGRAVITY → CODEX CONVERSION COMPLETED SUCCESSFULLY!")
            print(f"📌 Codex Session ID: {session_id}")
            print(f"📄 Rollout JSONL: {exported_file}")
            print(f"\n   codex resume {session_id}\n")
            print("=" * 60)
            launch_agent(["codex", "resume", str(session_id)], args.cwd, not args.no_launch)

        elif mode == "codex_to_claude":
            print("🔄 Codex -> Claude Code: converting session...")
            selected_file = select_codex_session(args.file or args.session, args.cwd, "Claude Code")
            conversation = CodexRolloutAdapter().read(
                selected_file,
                target_cwd=args.cwd,
            )
            converter = ConversationToClaudeConverter(
                conversation,
                target_cwd=args.cwd,
                output_path=args.output,
            )
            exported_file = converter.convert()
            session_id = converter.session_id

            print("\n" + "=" * 60)
            print("✨ CODEX → CLAUDE CONVERSION COMPLETED SUCCESSFULLY!")
            print(f"📌 Claude Session ID: {session_id}")
            print(f"📄 Exported Claude JSONL: {exported_file}")
            print(f"\n   claude --resume {session_id}\n")
            print("=" * 60)
            launch_agent(["claude", "--resume", str(session_id)], args.cwd, not args.no_launch)

        elif mode == "codex_to_antigravity":
            print("🔄 Codex -> Antigravity: converting session...")
            selected_file = select_codex_session(args.file or args.session, args.cwd, "Antigravity")
            conversation = CodexRolloutAdapter().read(
                selected_file,
                target_cwd=args.cwd,
            )
            converter = ConversationToAntigravityConverter(
                conversation,
                target_cwd=args.cwd,
            )
            session_id = converter.convert()

            print("\n" + "=" * 60)
            print("✨ CODEX → ANTIGRAVITY CONVERSION COMPLETED SUCCESSFULLY!")
            print(f"📌 Antigravity Session ID: {session_id}")
            print(f"\n   agy --conversation {session_id}\n")
            print("=" * 60)
            launch_agent(["agy", "--conversation", str(session_id)], args.cwd, not args.no_launch)

        else:
            raise ValueError(f"Unsupported conversion mode: {mode}")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
