---
name: business-email-managerment
description: Compatibility entry for the former misspelled Email Steward Skill name.
---

# Business Email Managerment (Compatibility)

## Purpose

Preserve existing references to `business-email-managerment` while directing new work to `business-email-management`.

## Permitted actions

Use the current `business-email-management` Skill for the same personal Alibaba Enterprise Mail workflow and its model, privacy, and confirmation rules.

## Failure behavior

If the current Skill is unavailable, stop without reading or changing mailbox state and tell the operator to use `business-email-management`.

## Approval

The current Skill controls approval. Reading and drafting need no approval; exact sends, Bcc, reply-all, and stars need explicit current-chat confirmation.
