---
name: mail-imap-read
description: Use when locating, reading, summarizing, or inspecting allowed attachments from Alibaba Enterprise Mail without changing mailbox state.
---

# Read Alibaba Enterprise Mail

## Purpose

Find and explain the right development-partnership email while keeping the mailbox unchanged.

## Permitted actions

Use read-only IMAP and a stated folder plus search scope. Identify a message by folder, UIDVALIDITY, and UID; display sender, recipients, date, subject, source identifier, text, and attachment metadata. Luna with low reasoning is the default.

## Existing workspace credential

Before opening IMAP, run `python installer/mail_runtime.py credential-status --workspace .`. When it returns `credential_ready`, use `load_workspace_session` to retrieve the existing system credential in process memory and open the read-only IMAP client. Never ask for a third-party client password in chat or the integrated terminal.

When it returns `credential_missing`, do not attempt a login and do not request a password. On Windows, use `installer/install_agent.bat --secure-window --repair-credential --workspace "."` to open the dedicated hidden local prompt. It repairs only the system credential and preserves the workspace.

## Failure behavior

If the mailbox, identity, scope, or attachment is unavailable, stop and explain what is missing. Do not mark read, change flags, search an unrequested broad mailbox, or process executable, archive, macro-enabled, suspicious, or oversized attachments.

## Approval

Reading requires no approval, but ask before expanding the requested search range. Any later star needs separate approval through `mail-imap-flag`; this skill never sends, stars, or changes mail.
