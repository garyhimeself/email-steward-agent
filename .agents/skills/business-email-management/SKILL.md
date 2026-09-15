---
name: business-email-management
description: Use when operating this project's Alibaba Enterprise Mail workflow, including installation, mailbox access, drafting, sending, stars, or the optional daily brief.
---

# Business Email Management

## Purpose

Keep one operator's personal Alibaba mailbox safe while Codex reads, summarizes, drafts, and—only when confirmed—acts on one message.

## Permitted actions

- Read through IMAP without changing read state; draft only in this chat.
- Use Luna with low reasoning for retrieval and briefs; use Terra with low reasoning for writing.
- Send one exact SMTP message or star one exact mail only through the specialized skills below.

## Failure behavior

Stop before a mailbox mutation, explain the error without secrets, and ask for corrected details or an administrator check. Never use browser automation, automatic send, bulk send, delete, move, copy, or retry an uncertain send.

## Installation handoff

For “install this Agent,” collect the workspace, daily-brief choice, and five non-secret profile values in chat: name, personal company email, preferred language, reply language, and reply tone. On Windows, start only `installer/install_agent.bat` with `--secure-window` first, plus `--workspace`, `--daily-brief`, `--name`, `--email`, `--preferred-language`, `--reply-language`, and `--reply-tone`. This opens the separate local PowerShell window; do not invoke `installer/install_agent.py` directly or start ordinary interactive setup in Codex’s integrated terminal. Do not ask the operator to re-enter known values in the window. The only window entry is the third-party client password through the hidden `getpass` prompt. If the secure window cannot open, stop; never fall back to a terminal password prompt. Never pass a password in a command, environment variable, file, log, or chat. A rejected IMAP login does not prove a password is wrong: explain the relevant safe diagnostic and recommend checking third-party client access and administrator policy.

## Approval

Reading and drafting require no approval. Every send, Bcc, reply-all, and star requires explicit current-chat approval of the exact displayed item. Do not recommend Sol or high reasoning.
