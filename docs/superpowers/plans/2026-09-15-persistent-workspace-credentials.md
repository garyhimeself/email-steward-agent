# Persistent Workspace Credentials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** New Codex conversations in an installed workspace reuse the OS-stored mailbox credential without a password prompt.

**Architecture:** The workspace retains only the validated non-secret profile. A runtime session loads it, reads the credential from Windows Credential Manager or macOS Keychain, and returns it only in process memory. A status command proves credential availability without exposing it; Skills require that path before every mailbox operation.

**Tech Stack:** Python 3.11, existing keyring backend, unittest.

## Global Constraints

- Never write or print a third-party client password outside the OS credential store.
- Preserve Windows and macOS support.
- A missing credential does not trigger IMAP login or a chat password request.

### Task 1: Runtime session loader

**Files:** Create `src/email_steward/workspace_session.py`; create `tests/test_workspace_session.py`.

**Interface:** `MailboxSession(profile: OperatorProfile, secret: str)` and `load_workspace_session(workspace, *, credential_store=None) -> MailboxSession`.

- [ ] Write a failing test that saves an `eileen@example.com` profile JSON plus a `test-only-secret` to an injected store, calls `load_workspace_session`, and asserts the returned email and secret.
- [ ] Run `python -m unittest tests.test_workspace_session -v`; expect a missing-module failure.
- [ ] Implement: load `WorkspacePaths.from_root(workspace).config_file`; parse JSON; validate with `validate_profile`; call `(credential_store or CredentialStore()).get(profile.email)`; raise `WorkspaceCredentialMissingError` if empty; otherwise return `MailboxSession`.
- [ ] Run the same test; expect PASS.

### Task 2: New-chat status command and Skill route

**Files:** Create `installer/mail_runtime.py` and `tests/test_mail_runtime.py`; modify `installer/install_agent.py`, `scripts/release_manifest.py`, `.agents/skills/mail-imap-read/SKILL.md`, `.agents/skills/business-email-management/SKILL.md`, and `tests/test_installer.py`.

**Interface:** `python installer/mail_runtime.py credential-status --workspace <folder>` prints JSON status only. Success is `{ "status": "credential_ready", "mailbox": "..." }`; missing is `{ "status": "credential_missing" }` with exit code 3. `--secure-window --repair-credential --workspace <folder>` repairs only the system credential for an existing workspace. Neither path exposes a secret or overwrites project files.

- [ ] Write a failing subprocess test that exercises the status command with an injected test store, expects `credential_ready`, and asserts `test-only-secret` is absent from stdout.
- [ ] Run `python -m unittest tests.test_mail_runtime -v`; expect command/module failure.
- [ ] Implement a direct launcher that adds its sibling `src` to `sys.path`, parses only `credential-status` and `--workspace`, calls `load_workspace_session`, and emits JSON without the secret.
- [ ] Add a secure `--repair-credential` installer request that loads the existing profile, prompts only through `getpass`, saves only to the OS credential store, verifies IMAP read-only, and keeps the existing workspace intact on every outcome.
- [ ] Add the launcher to the explicit release manifest and runtime copy list.
- [ ] Update both Skills: before any mailbox action run credential status; when ready use `load_workspace_session` and never prompt; when missing explain current OS identity cannot access the setup credential and direct only to the secure setup window.
- [ ] Run `python -m unittest tests.test_mail_runtime tests.test_workspace_session tests.test_installer tests.test_documentation -v`; expect PASS.

### Task 3: Release verification

- [ ] Run `python -m unittest discover -s tests -v`; expect PASS.
- [ ] Run `python scripts/build_zip.py --output ../email-steward-agent-v7.zip`; expect built verified public archive.
- [ ] Run `python scripts/verify_release.py ../email-steward-agent-v7.zip`; expect no private or generated files.
- [ ] Commit only source, Skill, test, and plan files, then push `main`.

## Self-review

- Task 1 is the single authoritative system-credential lookup.
- Task 2 makes its availability visible to every new chat, prohibits repeat prompts, and supplies a safe repair route for an existing non-empty workspace.
- Task 3 separately verifies source behavior and public package contents.
