"""Build a deterministic, public-only Email Steward release archive."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import sys
import zipfile


SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from release_manifest import release_members, release_mode
from verify_release import verify_archive


FIXED_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def build_archive(source_root: Path, output: Path) -> Path:
    """Assemble a byte-for-byte reproducible ZIP from the approved public files."""
    source_root = Path(source_root).resolve(strict=True)
    output = Path(output).resolve(strict=False)
    try:
        output.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ValueError("release output must be outside the source package")
    members = _public_members(source_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for member in members:
                source = source_root.joinpath(*PurePosixPath(member).parts)
                info = zipfile.ZipInfo(member, date_time=FIXED_TIMESTAMP)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100000 | release_mode(member)) << 16
                archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    verify_archive(output)
    return output


def _public_members(source_root: Path) -> tuple[str, ...]:
    members = release_members()
    for member in members:
        _require_regular_file(source_root.joinpath(*PurePosixPath(member).parts), member)
    return members


def _require_regular_file(path: Path, display_name: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"required public file is missing or unsafe: {display_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic Email Steward release ZIP.")
    parser.add_argument("--output", default="../email-steward-agent-v1.zip")
    args = parser.parse_args()
    archive = build_archive(Path(__file__).resolve().parents[1], Path(args.output))
    print(f"Built verified public release archive: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
