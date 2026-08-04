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


if __name__ == "__main__":
    unittest.main()
