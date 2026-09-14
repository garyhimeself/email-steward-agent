# Email Steward Agent

Email Steward helps a marketing teammate safely read their own Alibaba Enterprise Mail, prepare a daily brief, and write a reply draft in Codex. It is designed for one operator and one mailbox on Windows or macOS.

It never sends automatically. A send, Bcc, reply-all, or star requires an explicit confirmation for the exact displayed item in the current chat.

## Choose the right Codex model

| Work | Recommended setting |
| --- | --- |
| Find, read, classify mail; make a daily brief | **Luna, low reasoning** |
| Draft, translate, humanize, and prepare a reply | **Terra, low reasoning** |

Do not use or recommend Sol, high reasoning, or higher reasoning. The work is structured; when information is missing, ask a person rather than using a larger model.

## What happens during installation

1. Read [INSTALL.md](INSTALL.md), then run the Windows or macOS launcher.
2. Before setup, create an Alibaba **third-party client password** in webmail: `Settings → Account & Security → Account Security → Third-party client login security management → Generate new password`.
3. Copy and store that password immediately. It is shown only once. Enter it only in the local hidden password prompt—never into a Codex chat.
4. The installer asks where to create the workspace, asks for confirmation, saves non-secret preferences locally, and performs a read-only IMAP check. It does not change mail.
5. Create a Codex project whose file scope is that workspace, then complete the Luna and Terra acceptance prompts shown by the installer.

## Safe everyday use

- Use Luna, low reasoning: “Find unread development-partnership emails from the last 7 days. Do not send mail.”
- Use Terra, low reasoning: “Draft a friendly English reply to message [identifier]. Do not send it.”
- `humanizer` is used for a final natural-language pass. It may improve wording, but must not change facts, money, dates, commitments, recipients, or language.
- Before sending, verify To, Cc, Bcc, subject, body, and source message. Reply-all and Bcc are shown separately for confirmation.
- The daily brief is optional and off by default. Configure its dimensions, schedule, and timezone before enabling it.

Need help? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md). Chinese instructions: [README.zh-CN.md](README.zh-CN.md).
