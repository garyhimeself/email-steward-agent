import importlib.util
import os
import stat
import subprocess
import sys
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


def _write_regular(
    handle: zipfile.ZipFile, name: str, contents: str, *, mode: int | None = None
) -> None:
    if mode is None:
        mode = 0o755 if name == "installer/install_agent.command" else 0o644
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | mode) << 16
    handle.writestr(info, contents)


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
                    _write_regular(handle, name, "x")

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
                "UPGRADE.md",
                "UPGRADE.zh-CN.md",
                "src/email_steward/credentials.py",
                ".agents/skills/business-email-managerment/SKILL.md",
            ):
                self.assertIn(required, verified_members)

    def test_build_preserves_the_macos_installer_executable_permission(self):
        build_zip = _load_script("build_zip.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "release.zip"
            build_zip.build_archive(ROOT, archive)
            with zipfile.ZipFile(archive) as handle:
                entry = handle.getinfo("installer/install_agent.command")

        self.assertEqual((entry.external_attr >> 16) & 0o777, 0o755)

    def test_verify_rejects_a_non_executable_macos_installer(self):
        verify_release = _load_script("verify_release.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "non-executable-installer.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                for name in verify_release.REQUIRED_MEMBERS:
                    _write_regular(
                        handle,
                        name,
                        "public",
                        mode=0o644 if name == "installer/install_agent.command" else None,
                    )

            with self.assertRaisesRegex(ValueError, "permission"):
                verify_release.verify_archive(archive)

    def test_build_refuses_an_output_path_inside_the_source_tree(self):
        build_zip = _load_script("build_zip.py")
        with self.assertRaisesRegex(ValueError, "outside the source package"):
            build_zip.build_archive(ROOT, ROOT / "dist" / "release.zip")

    def test_verify_rejects_symlink_and_non_regular_zip_entries(self):
        verify_release = _load_script("verify_release.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "unsafe-entry.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                for name in verify_release.REQUIRED_MEMBERS:
                    _write_regular(handle, name, "public")
                symlink = zipfile.ZipInfo("src/email_steward/linked.py")
                symlink.create_system = 3
                symlink.external_attr = 0o120777 << 16
                handle.writestr(symlink, "target")

            with self.assertRaisesRegex(ValueError, "non-regular"):
                verify_release.verify_archive(archive)

    def test_extracted_release_imports_installer_and_runtime_modules(self):
        build_zip = _load_script("build_zip.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            archive = temporary / "release.zip"
            extraction = temporary / "extracted"
            build_zip.build_archive(ROOT, archive)
            with zipfile.ZipFile(archive) as handle:
                handle.extractall(extraction)
            program = (
                "import sys; "
                "sys.path.insert(0, 'src'); "
                "import installer.install_agent; "
                "import email_steward.credentials, email_steward.imap_read, email_steward.smtp_send"
            )
            completed = subprocess.run(
                (sys.executable, "-c", program),
                cwd=extraction,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_verify_rejects_a_private_key_hidden_inside_a_public_directory(self):
        verify_release = _load_script("verify_release.py")
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive = Path(temporary_directory) / "key.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                for name in verify_release.REQUIRED_MEMBERS:
                    _write_regular(handle, name, "public")
                _write_regular(handle, "src/email_steward/private.key", "private")

            with self.assertRaisesRegex(ValueError, "forbidden"):
                verify_release.verify_archive(archive)


if __name__ == "__main__":
    unittest.main()
