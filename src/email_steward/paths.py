"""Portable paths for one operator's local Email Steward data."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    """Paths rooted in a workspace and its ignored, operator-local data folder."""

    root: Path
    local_dir: Path
    config_file: Path
    state_file: Path
    temp_dir: Path
    log_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> "WorkspacePaths":
        root = Path(root)
        local_dir = root / ".email-steward"
        return cls(
            root=root,
            local_dir=local_dir,
            config_file=local_dir / "config" / "config.json",
            state_file=local_dir / "state" / "state.json",
            temp_dir=local_dir / "tmp",
            log_dir=local_dir / "logs",
        )

    def ensure_local_directories(self) -> None:
        """Create the local data directories if needed; safe to call repeatedly."""
        for directory in (
            self.config_file.parent,
            self.state_file.parent,
            self.temp_dir,
            self.log_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
