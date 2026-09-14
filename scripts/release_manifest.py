"""The single, exact public-file manifest for a distributable Email Steward ZIP."""

from __future__ import annotations


# Adding a source, installer, Skill, or test file to a release is an explicit review
# decision.  Do not replace this list with a directory walk: doing so can silently
# ship local mailbox state, credentials, build products, or an unreviewed file.
RELEASE_MEMBERS = frozenset(
    {
        ".gitignore",
        "AGENTS.md",
        "INSTALL.md",
        "INSTALL.zh-CN.md",
        "README.md",
        "README.zh-CN.md",
        "SPEC.md",
        "TROUBLESHOOTING.md",
        "TROUBLESHOOTING.zh-CN.md",
        "pyproject.toml",
        "config/operator.example.json",
        "installer/install_agent.bat",
        "installer/install_agent.command",
        "installer/install_agent.py",
        "installer/setup_email.py",
        "src/email_steward/__init__.py",
        "src/email_steward/approval.py",
        "src/email_steward/attachments.py",
        "src/email_steward/brief_state.py",
        "src/email_steward/credentials.py",
        "src/email_steward/drafting.py",
        "src/email_steward/imap_flag.py",
        "src/email_steward/imap_read.py",
        "src/email_steward/paths.py",
        "src/email_steward/profile.py",
        "src/email_steward/smtp_send.py",
        ".agents/skills/business-email-management/SKILL.md",
        ".agents/skills/humanizer/SKILL.md",
        ".agents/skills/mail-brief-incremental/SKILL.md",
        ".agents/skills/mail-compose-reply/SKILL.md",
        ".agents/skills/mail-imap-flag/SKILL.md",
        ".agents/skills/mail-imap-read/SKILL.md",
        ".agents/skills/mail-smtp-send/SKILL.md",
        "tests/test_approval.py",
        "tests/test_attachments.py",
        "tests/test_brief_state.py",
        "tests/test_credentials.py",
        "tests/test_documentation.py",
        "tests/test_drafting.py",
        "tests/test_imap_flag.py",
        "tests/test_imap_read.py",
        "tests/test_installer.py",
        "tests/test_paths.py",
        "tests/test_profile.py",
        "tests/test_release.py",
        "tests/test_smtp_send.py",
    }
)


def release_members() -> tuple[str, ...]:
    """Return the stable, reviewed order used by both build and verification."""
    return tuple(sorted(RELEASE_MEMBERS))
