import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReleasePackageTests(unittest.TestCase):
    def test_verify_rejects_private_or_generated_zip_members(self):
        verify_release = _load_script("verify_release.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                for name in (
                    "src/email_steward/__init__.py",
                    "installer/install_agent.py",
                    "tests/test_release.py",
                    ".agents/skills/humanizer/SKILL.md",
                    "README.md",
                    ".email-steward/config/config.json",
                    ".env",
                    "logs/operator.log",
                    "tmp/mail.txt",
                    "src/email_steward/__pycache__/paths.pyc",
                    "state.sqlite3",
                    "dist/email-steward-agent-v1.zip",
                ):
                    handle.writestr(name, "x")

            with self.assertRaisesRegex(ValueError, "forbidden"):
                verify_release.verify_archive(archive)

    def test_build_is_deterministic_and_contains_required_public_files_only(self):
        build_zip = _load_script("build_zip.py")
        verify_release = _load_script("verify_release.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            first = Path(temporary_directory) / "first.zip"
            second = Path(temporary_directory) / "second.zip"

            build_zip.build_archive(ROOT, first)
            build_zip.build_archive(ROOT, second)
            verified_members = verify_release.verify_archive(first)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(verified_members, tuple(sorted(verified_members)))
            for required in (
                "src/email_steward/imap_read.py",
                "installer/install_agent.py",
                "installer/install_agent.bat",
                "installer/install_agent.command",
                "AGENTS.md",
                ".agents/skills/humanizer/SKILL.md",
                "config/operator.example.json",
                "SPEC.md",
                "tests/test_release.py",
                "README.md",
                "README.zh-CN.md",
                "INSTALL.md",
                "INSTALL.zh-CN.md",
                "TROUBLESHOOTING.md",
                "TROUBLESHOOTING.zh-CN.md",
            ):
                self.assertIn(required, verified_members)

    def test_verify_rejects_a_private_key_hidden_inside_a_public_directory(self):
        verify_release = _load_script("verify_release.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "key.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                for name in verify_release.REQUIRED_MEMBERS:
                    handle.writestr(name, "public")
                handle.writestr(".agents/skills/humanizer/SKILL.md", "public")
                handle.writestr("src/email_steward/private.key", "private")

            with self.assertRaisesRegex(ValueError, "forbidden"):
                verify_release.verify_archive(archive)


if __name__ == "__main__":
    unittest.main()
