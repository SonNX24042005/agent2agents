#!/usr/bin/env bash
# Agent2Agents One-Line Installer for Linux, macOS, WSL, and Git Bash

set -e

# Detect source repo path or URL
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INSTALL_DIR="$HOME/.agent2agents"
BIN_DIR="$HOME/.local/bin"

echo "Installing Agent2Agents..."

# 1. Check Python installation
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "Error: Python 3 is required but not installed." >&2
    exit 1
fi

# 2. Setup installation directory
mkdir -p "$INSTALL_DIR"

if [ -d "$SCRIPT_DIR/agent2agents" ] && [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    # Running from cloned repo directory
    cp -r "$SCRIPT_DIR/agent2agents" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/tests" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/setup.py" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/run.sh" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/install.sh" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/install.ps1" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || true
    if [ -d "$SCRIPT_DIR/.git" ]; then
        rm -rf "$INSTALL_DIR/.git"
        cp -r "$SCRIPT_DIR/.git" "$INSTALL_DIR/" 2>/dev/null || true
    fi
else
    # Downloading from GitHub repository
    REPO_URL="${AGENT2AGENTS_REPO_URL:-https://github.com/SonNX24042005/agent2agents.git}"
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "Updating existing installation in $INSTALL_DIR..."
        if ! git -C "$INSTALL_DIR" pull --quiet 2>/dev/null; then
            echo "Git pull encountered an issue, fetching and resetting to origin/main..."
            git -C "$INSTALL_DIR" fetch --quiet origin main 2>/dev/null || true
            git -C "$INSTALL_DIR" reset --hard origin/main --quiet 2>/dev/null || true
        fi
    else
        echo "Downloading source code into $INSTALL_DIR..."
        if command -v git &>/dev/null; then
            TEMP_CLONE=$(mktemp -d)
            git clone --depth 1 "$REPO_URL" "$TEMP_CLONE"
            mkdir -p "$INSTALL_DIR"
            cp -r "$TEMP_CLONE/agent2agents" "$INSTALL_DIR/"
            cp -r "$TEMP_CLONE/tests" "$INSTALL_DIR/" 2>/dev/null || true
            cp "$TEMP_CLONE/setup.py" "$INSTALL_DIR/" 2>/dev/null || true
            cp "$TEMP_CLONE/run.sh" "$INSTALL_DIR/" 2>/dev/null || true
            cp "$TEMP_CLONE/install.sh" "$INSTALL_DIR/" 2>/dev/null || true
            cp "$TEMP_CLONE/install.ps1" "$INSTALL_DIR/" 2>/dev/null || true
            cp "$TEMP_CLONE/README.md" "$INSTALL_DIR/" 2>/dev/null || true
            rm -rf "$INSTALL_DIR/.git"
            cp -r "$TEMP_CLONE/.git" "$INSTALL_DIR/" 2>/dev/null || true
            rm -rf "$TEMP_CLONE"
        elif command -v curl &>/dev/null && command -v tar &>/dev/null; then
            curl -fsSL "https://github.com/SonNX24042005/agent2agents/archive/refs/heads/main.tar.gz" | tar -xz -C "$INSTALL_DIR" --strip-components=1
        fi
    fi
fi

# 3. Create bin directory
mkdir -p "$BIN_DIR"

# 4. Create wrapper executable for a2a
cat << 'EOF' > "$BIN_DIR/a2a"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.agent2agents"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
PYTHONPATH="$SCRIPT_DIR" "$PYTHON_CMD" -m agent2agents.cli "$@"
EOF

# Keep the full package name as a compatibility alias.
cp "$BIN_DIR/a2a" "$BIN_DIR/agent2agents"

# 5. Create direct convenience wrappers. They bypass the mode menu.
cat << 'EOF' > "$BIN_DIR/claude2agy"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.agent2agents"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
PYTHONPATH="$SCRIPT_DIR" "$PYTHON_CMD" -m agent2agents.cli --antigravity "$@"
EOF

cat << 'EOF' > "$BIN_DIR/claude2codex"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.agent2agents"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
PYTHONPATH="$SCRIPT_DIR" "$PYTHON_CMD" -m agent2agents.cli --codex "$@"
EOF

cat << 'EOF' > "$BIN_DIR/agy2claude"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.agent2agents"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
PYTHONPATH="$SCRIPT_DIR" "$PYTHON_CMD" -m agent2agents.cli --reverse "$@"
EOF

cat << 'EOF' > "$BIN_DIR/agy2codex"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.agent2agents"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
PYTHONPATH="$SCRIPT_DIR" "$PYTHON_CMD" -m agent2agents.cli --antigravity-to-codex "$@"
EOF

cat << 'EOF' > "$BIN_DIR/codex2claude"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.agent2agents"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
PYTHONPATH="$SCRIPT_DIR" "$PYTHON_CMD" -m agent2agents.cli --codex-to-claude "$@"
EOF

cat << 'EOF' > "$BIN_DIR/codex2agy"
#!/usr/bin/env bash
SCRIPT_DIR="$HOME/.agent2agents"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi
PYTHONPATH="$SCRIPT_DIR" "$PYTHON_CMD" -m agent2agents.cli --codex-to-antigravity "$@"
EOF

chmod +x "$BIN_DIR/a2a" "$BIN_DIR/agent2agents" "$BIN_DIR/claude2agy" "$BIN_DIR/claude2codex" "$BIN_DIR/agy2claude" "$BIN_DIR/agy2codex" "$BIN_DIR/codex2claude" "$BIN_DIR/codex2agy"

# 6. Check PATH
PATH_ADDED=false
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        PATH_ADDED=true
        SHELL_PROFILE=""
        if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
            SHELL_PROFILE="$HOME/.zshrc"
        elif [ -f "$HOME/.bashrc" ]; then
            SHELL_PROFILE="$HOME/.bashrc"
        elif [ -f "$HOME/.profile" ]; then
            SHELL_PROFILE="$HOME/.profile"
        fi

        if [ -n "$SHELL_PROFILE" ]; then
            if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$SHELL_PROFILE"; then
                echo '' >> "$SHELL_PROFILE"
                echo '# Added by Agent2Agents installer' >> "$SHELL_PROFILE"
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_PROFILE"
            fi
        fi
        ;;
esac

echo ""
echo "Installation completed successfully!"
echo "Commands installed:"
echo "  - a2a (primary command)"
echo "  - agent2agents (compatibility alias)"
echo "  - claude2agy (direct Claude Code -> Antigravity)"
echo "  - claude2codex (direct Claude Code -> Codex)"
echo "  - agy2claude (direct Antigravity -> Claude Code)"
echo "  - agy2codex (direct Antigravity -> Codex)"
echo "  - codex2claude (direct Codex -> Claude Code)"
echo "  - codex2agy (direct Codex -> Antigravity)"
echo ""
if [ "$PATH_ADDED" = true ]; then
    echo "Note: Please restart your terminal or run:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi
