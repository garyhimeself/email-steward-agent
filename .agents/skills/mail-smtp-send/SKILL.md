---
name: mail-smtp-send
description: Use when an operator asks to send one exact, previously displayed enterprise email or reply through SMTP.
---

# Send One Email

## Purpose

Send exactly one reviewed message without exposing Bcc recipients or creating unapproved delivery attempts.

## Permitted actions

Use SMTP only after displaying sender, To, Cc, Bcc, subject, body, message type, and source identifier. Send one exact draft with its one-time current-chat approval token. Keep Bcc out of message headers while including it in SMTP envelope recipients.

## Failure behavior

Report only sent, definitely not sent, or uncertain. For timeout, refusal, or uncertain delivery, stop without retrying and ask the operator to inspect Sent mail or decide manually. Never batch or automatically send.

## Approval

Require the operator's explicit current-chat approval of every displayed recipient and content field. Bcc and reply-all require a visible, separate confirmation. No approval means no SMTP call.
