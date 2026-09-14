"""Build a deterministic, public-only Email Steward release archive."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import sys
import zipfile


SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from verify_release import PUBLIC_DIRECTORY_PREFIXES, PUBLIC_ROOT_FILES, verify_archive


FIXED_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def build_archive(source_root: Path, output: Path) -> Path:
    """Assemble a byte-for-byte reproducible ZIP from the approved public files."""
    source_root = Path(source_root).resolve(strict=True)
    output = Path(output)
    members = _public_members(source_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for member in members:
                source = source_root.joinpath(*PurePosixPath(member).parts)
                info = zipfile.ZipInfo(member, date_time=FIXED_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    verify_archive(output)
    return output


def _public_members(source_root: Path) -> tuple[str, ...]:
    members: list[str] = []
    for filename in PUBLIC_ROOT_FILES:
        path = source_root / filename
        _require_regular_file(path, filename)
        members.append(filename)
    for directory in PUBLIC_DIRECTORY_PREFIXES:
        path = source_root / directory
        if not path.is_dir() or path.is_symlink():
            raise ValueError(f"required public directory is missing or unsafe: {directory}")
        members.extend(_files_below(source_root, path))
    return tuple(sorted(members))


def _files_below(source_root: Path, directory: Path) -> list[str]:
    files: list[str] = []
    for current, directory_names, filenames in os.walk(directory, topdown=True, followlinks=False):
        current_path = Path(current)
        directory_names[:] = sorted(name for name in directory_names if not _excluded_component(name))
        for filename in sorted(filenames):
            if _excluded_component(filename):
                continue
            candidate = current_path / filename
            relative = candidate.relative_to(source_root).as_posix()
            _require_regular_file(candidate, relative)
            files.append(relative)
    return files


def _excluded_component(name: str) -> bool:
    lowered = name.casefold()
    return (
        lowered in {".git", ".superpowers", ".email-steward", "__pycache__", "cache", "logs", "tmp", "dist"}
        or lowered.startswith((".env", "tmp", "secret", "password", "credential"))
        or lowered.endswith((
            ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".log",
            ".key", ".pem", ".p12", ".pfx",
        ))
    )


def _require_regular_file(path: Path, display_name: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"required public file is missing or unsafe: {display_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic Email Steward release ZIP.")
    parser.add_argument("--output", default="dist/email-steward-agent-v1.zip")
    args = parser.parse_args()
    archive = build_archive(Path(__file__).resolve().parents[1], Path(args.output))
    print(f"Built verified public release archive: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
