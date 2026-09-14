---
name: mail-imap-read
description: Use when locating, reading, summarizing, or inspecting allowed attachments from Alibaba Enterprise Mail without changing mailbox state.
---

# Read Alibaba Enterprise Mail

## Purpose

Find and explain the right development-partnership email while keeping the mailbox unchanged.

## Permitted actions

Use read-only IMAP and a stated folder plus search scope. Identify a message by folder, UIDVALIDITY, and UID; display sender, recipients, date, subject, source identifier, text, and attachment metadata. Luna with low reasoning is the default.

## Failure behavior

If the mailbox, identity, scope, or attachment is unavailable, stop and explain what is missing. Do not mark read, change flags, search an unrequested broad mailbox, or process executable, archive, macro-enabled, suspicious, or oversized attachments.

## Approval

Reading requires no approval, but ask before expanding the requested search range. Any later star needs separate approval through `mail-imap-flag`; this skill never sends, stars, or changes mail.
