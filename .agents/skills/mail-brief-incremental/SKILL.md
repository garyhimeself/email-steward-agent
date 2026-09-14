---
name: mail-brief-incremental
description: Use when an operator has explicitly enabled a daily brief and needs a non-duplicated summary of newly received unread mail.
---

# Incremental Daily Brief

## Purpose

Create a useful daily brief from new unread INBOX mail while retaining the least possible local state.

## Permitted actions

Use Luna with low reasoning; read only messages from the last successful watermark to now; produce the operator-approved title, dimensions, action format, time, and timezone. Keep only minimal identifiers and semantic cards for at most 90 days.

## Failure behavior

If configuration, scope, or a run fails, do not advance the watermark, retry automatically, or change mail. Explain the issue and preserve no raw body, attachment, or draft in state.

## Approval

The daily brief is off by default. Require operator approval before enabling it and before changing its scope, schedule, timezone, or format. The brief never sends email.
