"""Verify that an Email Steward release archive contains public files only."""

from __future__ import annotations

import argparse
from pathlib import PurePosixPath, Path
import zipfile


PUBLIC_ROOT_FILES = frozenset(
    {
        "AGENTS.md", ".gitignore", "pyproject.toml", "README.md", "README.zh-CN.md",
        "INSTALL.md", "INSTALL.zh-CN.md", "TROUBLESHOOTING.md",
        "TROUBLESHOOTING.zh-CN.md", "SPEC.md",
    }
)
PUBLIC_DIRECTORY_PREFIXES = ("src", "installer", ".agents", "config", "tests")
REQUIRED_MEMBERS = frozenset(
    {
        "AGENTS.md", "src/email_steward/__init__.py", "installer/install_agent.py",
        "installer/install_agent.bat", "installer/install_agent.command", "config/operator.example.json",
        "tests/test_release.py", "README.md", "README.zh-CN.md", "INSTALL.md",
        "INSTALL.zh-CN.md", "TROUBLESHOOTING.md", "TROUBLESHOOTING.zh-CN.md", "SPEC.md",
    }
)
FORBIDDEN_DIRECTORY_NAMES = frozenset(
    {".email-steward", ".git", ".superpowers", "__pycache__", "cache", "logs", "tmp", "dist"}
)
FORBIDDEN_SUFFIXES = (
    ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log",
    ".key", ".pem", ".p12", ".pfx",
)


def verify_archive(archive: Path) -> tuple[str, ...]:
    """Return validated archive members or raise ValueError for an unsafe release."""
    archive = Path(archive)
    if not archive.is_file():
        raise ValueError(f"release archive does not exist: {archive}")
    try:
        with zipfile.ZipFile(archive) as handle:
            members = tuple(item.filename for item in handle.infolist() if not item.is_dir())
    except zipfile.BadZipFile as error:
        raise ValueError(f"invalid release archive: {error}") from error
    if len(members) != len(set(members)):
        raise ValueError("forbidden duplicate archive member")
    for member in members:
        _validate_member(member)
    missing = REQUIRED_MEMBERS.difference(members)
    if missing:
        raise ValueError(f"release archive is missing required public files: {', '.join(sorted(missing))}")
    if not any(member.startswith(".agents/skills/") and member.endswith("/SKILL.md") for member in members):
        raise ValueError("release archive is missing local Skills")
    return tuple(sorted(members))


def _validate_member(member: str) -> None:
    if not member or "\\" in member:
        raise ValueError(f"forbidden archive member path: {member!r}")
    path = PurePosixPath(member)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"forbidden archive member path: {member!r}")
    lowered_parts = tuple(part.casefold() for part in path.parts)
    if any(part in FORBIDDEN_DIRECTORY_NAMES or part.startswith(".env") or part.startswith("tmp") for part in lowered_parts):
        raise ValueError(f"forbidden private or generated archive member: {member}")
    filename = lowered_parts[-1]
    if filename.endswith(FORBIDDEN_SUFFIXES) or filename.startswith((".env", "secret", "password", "credential")):
        raise ValueError(f"forbidden private or generated archive member: {member}")
    if len(path.parts) == 1:
        if member not in PUBLIC_ROOT_FILES:
            raise ValueError(f"forbidden non-public archive member: {member}")
        return
    if path.parts[0] not in PUBLIC_DIRECTORY_PREFIXES:
        raise ValueError(f"forbidden non-public archive member: {member}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a safe Email Steward release ZIP.")
    parser.add_argument("archive", nargs="?", default="dist/email-steward-agent-v1.zip")
    args = parser.parse_args()
    members = verify_archive(Path(args.archive))
    print(f"Verified {args.archive}: {len(members)} public files; no private or generated files found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
