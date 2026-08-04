#!/usr/bin/env bash
# Quick runner for Agent2Agents without requiring global pip installation

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PYTHONPATH="$SCRIPT_DIR" python3 -m agent2agents.cli "$@"
