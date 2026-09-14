---
name: mail-compose-reply
description: Use when drafting, translating, or preparing a new enterprise email, reply, or reply-all for operator review without sending or saving a mailbox draft.
---

# Compose a Reply

## Purpose

Produce an accurate, natural, unsent draft that an operator can review in the chat.

## Permitted actions

Use Terra with low reasoning. Draft from a read source message; show To, Cc, Bcc, subject, body, message type, and source identifier. Use `humanizer` after fact review. Reply-all may include only addresses visible in the source mail.

## Failure behavior

If recipients, facts, price, dates, commitments, language, or message headers are unclear, leave a clear placeholder or ask the operator. Do not invent details, save a mailbox draft, send, or claim humanizer can guarantee undetectable AI text.

## Approval

Drafting needs no approval. Reply-all and Bcc must be highlighted for later explicit approval; sending requires the separate `mail-smtp-send` skill and current-chat approval.
