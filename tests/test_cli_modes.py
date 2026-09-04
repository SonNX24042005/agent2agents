import unittest
from unittest import mock

from agent2agents.cli import CONVERSION_MODES, choose_mode, launch_agent, mode_from_invocation


class CliModeTests(unittest.TestCase):
    def test_direct_aliases_skip_the_mode_menu(self):
        self.assertEqual(mode_from_invocation("claude2agy"), "claude_to_antigravity")
        self.assertEqual(mode_from_invocation("claude2codex.cmd"), "claude_to_codex")
        self.assertEqual(mode_from_invocation("claude2codex"), "claude_to_codex")
        self.assertEqual(mode_from_invocation("agy2claude"), "antigravity_to_claude")
        self.assertEqual(mode_from_invocation("agy2codex"), "antigravity_to_codex")
        self.assertEqual(mode_from_invocation("codex2claude"), "codex_to_claude")
        self.assertEqual(mode_from_invocation("codex2agy"), "codex_to_antigravity")

        with mock.patch("agent2agents.cli.select_option") as select_option:
            self.assertEqual(choose_mode("claude2codex"), "claude_to_codex")
            select_option.assert_not_called()

    def test_generic_command_uses_the_conversion_menu(self):
        with mock.patch("agent2agents.cli.select_option", return_value=1) as select_option:
            self.assertEqual(choose_mode("a2a"), "claude_to_codex")
            select_option.assert_called_once()

    def test_generic_menu_exposes_all_six_routes(self):
        for index, (mode, _label) in enumerate(CONVERSION_MODES):
            with self.subTest(mode=mode), mock.patch(
                "agent2agents.cli.select_option", return_value=index
            ):
                self.assertEqual(choose_mode("a2a"), mode)

    def test_cancelled_conversion_menu_returns_no_mode(self):
        with mock.patch("agent2agents.cli.select_option", return_value=None):
            self.assertIsNone(choose_mode("a2a"))

    @mock.patch("agent2agents.cli.subprocess.run")
    def test_launch_agent_starts_the_target_session(self, run):
        run.return_value.returncode = 0

        self.assertEqual(
            launch_agent(["codex", "resume", "session-123"], "/tmp/project"),
            0,
        )
        run.assert_called_once_with(
            ["codex", "resume", "session-123"],
            cwd="/tmp/project",
            check=False,
        )

    @mock.patch("agent2agents.cli.subprocess.run")
    def test_no_launch_keeps_the_target_agent_closed(self, run):
        self.assertIsNone(
            launch_agent(["agy", "--conversation", "session-123"], "/tmp/project", enabled=False)
        )
        run.assert_not_called()

    def test_select_claude_session_with_manual_input(self):
        from agent2agents.cli import select_claude_session
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test-session.jsonl"
            file_path.write_text("{}", encoding="utf-8")

            with mock.patch("agent2agents.converters.ClaudeToAntigravityConverter.get_project_sessions", return_value=[]), \
                 mock.patch("agent2agents.cli.select_option", return_value=0) as select_option, \
                 mock.patch("builtins.input", return_value=str(file_path)):
                result = select_claude_session(None, temp_dir, "Antigravity")
                select_option.assert_called_once()
                self.assertEqual(result, str(file_path.resolve()))

    def test_select_antigravity_session_with_manual_input(self):
        from agent2agents.cli import select_antigravity_session

        with mock.patch("agent2agents.converters.AntigravityToClaudeConverter.get_agy_sessions", return_value=[]), \
             mock.patch("agent2agents.cli.select_option", return_value=0) as select_option, \
             mock.patch("builtins.input", return_value="custom-agy-session-id"):
            result = select_antigravity_session(None, "/tmp/project", "Claude Code")
            select_option.assert_called_once()
            self.assertEqual(result, "custom-agy-session-id")

    def test_select_codex_session_with_manual_input(self):
        from agent2agents.cli import select_codex_session
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            rollout_path = Path(temp_dir) / "rollout-custom.jsonl"
            rollout_path.write_text("{}", encoding="utf-8")

            with mock.patch("agent2agents.adapters.codex.CodexRolloutAdapter.get_project_sessions", return_value=[]), \
                 mock.patch("agent2agents.cli.select_option", return_value=0) as select_option, \
                 mock.patch("builtins.input", return_value=str(rollout_path)):
                result = select_codex_session(None, temp_dir, "Antigravity")
                select_option.assert_called_once()
                self.assertEqual(result, str(rollout_path.resolve()))

    def test_select_session_first_option_is_manual_entry(self):
        from agent2agents.cli import select_claude_session, select_antigravity_session, select_codex_session

        fake_claude_sessions = [{"filename": "s1.jsonl", "path": "/p/s1.jsonl", "mtime": "2026-01-01", "first_prompt": "hello"}]
        with mock.patch("agent2agents.converters.ClaudeToAntigravityConverter.get_project_sessions", return_value=fake_claude_sessions), \
             mock.patch("agent2agents.cli.select_option", return_value=1) as select_option:
            result = select_claude_session(None, "/p", "Antigravity")
            options = select_option.call_args[0][0]
            self.assertTrue(options[0].startswith("✍️"))
            self.assertEqual(result, "/p/s1.jsonl")

        fake_agy_sessions = [{"id": "agy-1", "preview": "hello", "mtime": "2026-01-01"}]
        with mock.patch("agent2agents.converters.AntigravityToClaudeConverter.get_agy_sessions", return_value=fake_agy_sessions), \
             mock.patch("agent2agents.cli.select_option", return_value=1) as select_option:
            result = select_antigravity_session(None, "/p", "Claude Code")
            options = select_option.call_args[0][0]
            self.assertTrue(options[0].startswith("✍️"))
            self.assertEqual(result, "agy-1")

        fake_codex_sessions = [{"id": "codex-1", "path": "/p/rollout-1.jsonl", "mtime": "2026-01-01", "first_prompt": "hello"}]
        with mock.patch("agent2agents.adapters.codex.CodexRolloutAdapter.get_project_sessions", return_value=fake_codex_sessions), \
             mock.patch("agent2agents.cli.select_option", return_value=1) as select_option:
            result = select_codex_session(None, "/p", "Antigravity")
            options = select_option.call_args[0][0]
            self.assertTrue(options[0].startswith("✍️"))
            self.assertEqual(result, "/p/rollout-1.jsonl")

    def test_update_flags_trigger_update_tool(self):
        from agent2agents.cli import main
        import sys

        for flag in ["-u", "--update", "--upgrade", "--pull"]:
            with self.subTest(flag=flag), \
                 mock.patch.object(sys, "argv", ["a2a", flag]), \
                 mock.patch("agent2agents.cli.update_tool", return_value=True) as mock_update, \
                 mock.patch("sys.exit", side_effect=SystemExit) as mock_exit:
                with self.assertRaises(SystemExit):
                    main()
                mock_update.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_version_flags_display_version(self):
        from agent2agents.cli import main
        from agent2agents import __version__
        import sys
        import io

        for flag in ["-v", "--version"]:
            with self.subTest(flag=flag), \
                 mock.patch.object(sys, "argv", ["a2a", flag]), \
                 mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout, \
                 mock.patch("sys.exit", side_effect=SystemExit) as mock_exit:
                with self.assertRaises(SystemExit):
                    main()
                self.assertIn(f"Agent2Agents v{__version__}", mock_stdout.getvalue())
                mock_exit.assert_called_once_with(0)

    def test_update_tool_git_pull_success(self):
        from agent2agents.cli import update_tool
        with mock.patch("os.path.exists", return_value=True), \
             mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="Already up to date.")
            res = update_tool()
            self.assertTrue(res)

    def test_update_tool_git_pull_fallback_reset(self):
        from agent2agents.cli import update_tool
        with mock.patch("os.path.exists", return_value=True), \
             mock.patch("subprocess.run") as mock_run:
            def run_mock(cmd, *args, **kwargs):
                if isinstance(cmd, list) and "pull" in cmd:
                    return mock.Mock(returncode=1, stderr="conflict")
                return mock.Mock(returncode=0, stdout="success")
            mock_run.side_effect = run_mock
            res = update_tool()
            self.assertTrue(res)


if __name__ == "__main__":
    unittest.main()

