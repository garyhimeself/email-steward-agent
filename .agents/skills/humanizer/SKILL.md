---
name: humanizer
description: Use when polishing an already fact-checked business email draft so it sounds natural while retaining the operator's intended meaning and boundaries.
---

# Humanize a Business Draft

## Purpose

Remove formulaic AI phrasing and make an approved draft sound concise, professional, and like the operator—without changing business meaning.

## Permitted actions

After factual review, improve sentence rhythm, specificity already present in the draft, greeting, closing, and tone. Prefer an operator-provided writing sample; otherwise use a natural professional default. Work with Terra at low reasoning.

## Failure behavior

If a passage needs new information, leave a placeholder or ask the operator. Never add, remove, or alter facts, money, dates, deadlines, commitments, names, companies, recipients, Cc, Bcc, language, or agreed tone. Do not claim the result is guaranteed to evade AI detection.

## Approval

Naturalizing an unsent draft requires no send approval, but show the revised draft for review. A later send still needs explicit current-chat approval through `mail-smtp-send`; humanizer never sends mail.
