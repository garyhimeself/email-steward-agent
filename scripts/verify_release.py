"""Verify that an Email Steward release archive contains public files only."""

from __future__ import annotations

import argparse
from pathlib import PurePosixPath, Path
import stat
import zipfile

from release_manifest import RELEASE_MEMBERS, release_members

# Compatibility alias used by package-audit tests.  Unlike the former partial
# list, this now means every member that a valid release must contain.
REQUIRED_MEMBERS = RELEASE_MEMBERS


def verify_archive(archive: Path) -> tuple[str, ...]:
    """Return validated archive members or raise ValueError for an unsafe release."""
    archive = Path(archive)
    if not archive.is_file():
        raise ValueError(f"release archive does not exist: {archive}")
    try:
        with zipfile.ZipFile(archive) as handle:
            entries = tuple(handle.infolist())
    except zipfile.BadZipFile as error:
        raise ValueError(f"invalid release archive: {error}") from error
    members = tuple(item.filename for item in entries)
    if len(members) != len(set(members)):
        raise ValueError("forbidden duplicate archive member")
    for entry in entries:
        _validate_regular_file(entry)
        member = entry.filename
        _validate_member(member)
    actual_members = frozenset(members)
    missing = RELEASE_MEMBERS.difference(actual_members)
    unexpected = actual_members.difference(RELEASE_MEMBERS)
    if missing:
        raise ValueError(f"release archive is missing required public files: {', '.join(sorted(missing))}")
    if unexpected:
        raise ValueError(f"forbidden non-manifest archive member: {', '.join(sorted(unexpected))}")
    return release_members()


def _validate_regular_file(entry: zipfile.ZipInfo) -> None:
    """Reject symlinks, directories, devices, and untyped ZIP entries."""
    mode = entry.external_attr >> 16
    if stat.S_IFMT(mode) != stat.S_IFREG:
        raise ValueError(f"forbidden non-regular archive member: {entry.filename!r}")


def _validate_member(member: str) -> None:
    if not member or "\\" in member:
        raise ValueError(f"forbidden archive member path: {member!r}")
    path = PurePosixPath(member)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"forbidden archive member path: {member!r}")
    if member not in RELEASE_MEMBERS:
        raise ValueError(f"forbidden non-manifest archive member: {member}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a safe Email Steward release ZIP.")
    parser.add_argument("archive", nargs="?", default="dist/email-steward-agent-v1.zip")
    args = parser.parse_args()
    members = verify_archive(Path(args.archive))
    print(f"Verified {args.archive}: {len(members)} public files; no private or generated files found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
