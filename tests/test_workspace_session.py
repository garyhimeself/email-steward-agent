from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.paths import WorkspacePaths


class MemoryCredentialStore:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}

    def get(self, email: str) -> str | None:
        return self.values.get(email)

    def set(self, email: str, secret: str) -> None:
        self.values[email] = secret

    def delete(self, email: str) -> None:
        self.values.pop(email, None)


class WorkspaceSessionTests(unittest.TestCase):
    def test_load_workspace_session_uses_saved_system_credential_without_prompt(self):
        from email_steward.workspace_session import load_workspace_session

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            paths = WorkspacePaths.from_root(workspace)
            paths.ensure_local_directories()
            paths.config_file.write_text(
                json.dumps(
                    {
                        "name": "Eileen",
                        "email": "eileen@example.com",
                        "preferred_language": "Chinese",
                        "reply_language": "English",
                        "reply_tone": "professional and friendly",
                    }
                ),
                encoding="utf-8",
            )

            session = load_workspace_session(
                workspace,
                credential_store=MemoryCredentialStore({"eileen@example.com": "test-only-secret"}),
            )

            self.assertEqual(session.profile.email, "eileen@example.com")
            self.assertEqual(session.secret, "test-only-secret")


if __name__ == "__main__":
    unittest.main()
