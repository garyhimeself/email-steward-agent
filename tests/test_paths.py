import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from email_steward.paths import WorkspacePaths


class WorkspacePathsTests(unittest.TestCase):
    def test_paths_are_derived_from_the_supplied_workspace_root(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary_directory:
            root = Path(temporary_directory) / "arbitrary" / "workspace"
            paths = WorkspacePaths.from_root(root)

            self.assertEqual(paths.root, root)
            self.assertEqual(paths.local_dir, root / ".email-steward")
            self.assertEqual(paths.config_file, root / ".email-steward" / "config" / "config.json")
            self.assertEqual(paths.state_file, root / ".email-steward" / "state" / "state.json")
            self.assertEqual(paths.temp_dir, root / ".email-steward" / "tmp")
            self.assertEqual(paths.log_dir, root / ".email-steward" / "logs")

            self.assertTrue(paths.root.is_relative_to(Path(temporary_directory)))
            self.assertTrue(paths.local_dir.is_relative_to(paths.root))

    def test_ensure_local_directories_creates_expected_directories_idempotently(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary_directory:
            paths = WorkspacePaths.from_root(Path(temporary_directory) / "workspace")

            paths.ensure_local_directories()
            paths.ensure_local_directories()

            for directory in (
                paths.local_dir / "config",
                paths.local_dir / "state",
                paths.temp_dir,
                paths.log_dir,
            ):
                with self.subTest(directory=directory):
                    self.assertTrue(directory.is_dir())


if __name__ == "__main__":
    unittest.main()
