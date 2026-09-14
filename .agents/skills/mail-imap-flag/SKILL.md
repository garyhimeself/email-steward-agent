---
name: mail-imap-flag
description: Use when proposing or applying a visible follow-up star to one exact Alibaba Enterprise Mail message.
---

# Star One Mail

## Purpose

Let an operator mark one exact follow-up email without other mailbox changes.

## Permitted actions

Show exact folder, UIDVALIDITY, UID, subject, and reason; then apply only the standard IMAP `Flagged` marker to the approved message.

## Failure behavior

If the identity changed, selection fails, or the result is uncertain, stop and report it. Do not create labels, move, delete, copy, mark read, or retry an uncertain operation.

## Approval

Require explicit current-chat approval for each individual mail. A proposal, a list of mails, or an older confirmation is not approval.
