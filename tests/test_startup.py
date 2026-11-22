import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import main


class StartupTests(unittest.TestCase):
    def test_windows_python_redirects_to_project_environment(self):
        root = Path(main.__file__).resolve().parent
        with patch.object(sys, "platform", "win32"), patch.object(sys, "prefix", str(root.parent)), patch.object(Path, "is_file", return_value=True):
            self.assertEqual(main.project_interpreter(), root / ".venv" / "Scripts" / "python.exe")

    def test_project_environment_does_not_redirect_again(self):
        environment = Path(main.__file__).resolve().parent / ".venv"
        with patch.object(sys, "prefix", str(environment)), patch.object(Path, "is_file", return_value=True):
            self.assertIsNone(main.project_interpreter())

    def test_packaged_executable_never_redirects(self):
        with patch.object(sys, "frozen", True, create=True):
            self.assertIsNone(main.project_interpreter())

    def test_redirect_preserves_arguments_and_exit_code(self):
        executable = Path("project-python.exe")
        with patch.object(main, "project_interpreter", return_value=executable), patch.object(sys, "argv", ["main.py", "--check"]), patch.object(main.subprocess, "call", return_value=7) as launch:
            self.assertEqual(main.main(), 7)
        launch.assert_called_once_with([str(executable), str(Path(main.__file__).resolve()), "--check"])


if __name__ == "__main__":
    unittest.main()
