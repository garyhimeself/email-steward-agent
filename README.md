# Email Steward Agent

[English](README.md) | [简体中文](README.zh-CN.md)

## 中文简介

**邮件管家 Agent** 帮助营销同事在 Codex 中安全地读取自己的阿里企业邮箱、整理日报，并起草开发合作邮件回复。它面向 Windows 和 macOS 上的一位操作者及其个人邮箱。

- 不会自动发送邮件；发送、密送、回复全部和星标均需对当前展示的具体项目逐项确认。
- 收取与日报建议使用 **Luna，低推理**；撰写、翻译和自然化润色建议使用 **Terra，低推理**。
- 第三方客户端安全密码只保存于操作者本机的系统凭据库，绝不应发送到 Codex 对话或提交至仓库。

完整中文安装、使用和排错说明请见 [README.zh-CN.md](README.zh-CN.md)。

---

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
3. Copy and store that password immediately. It is shown only once. On Windows, Codex opens a **separate secure PowerShell window** for the hidden local prompt—never enter it into a Codex chat.
4. Codex collects the workspace and non-secret preferences in chat, shows a summary for confirmation, then opens the secure window for the password. The integrated terminal is never a password fallback. The installer performs a read-only IMAP check and does not change mail.
5. Create a Codex project whose file scope is that workspace, then complete the Luna and Terra acceptance prompts shown by the installer.

## Safe everyday use

- Use Luna, low reasoning: “Find unread development-partnership emails from the last 7 days. Do not send mail.”
- Use Terra, low reasoning: “Draft a friendly English reply to message [identifier]. Do not send it.”
- `humanizer` is used for a final natural-language pass. It may improve wording, but must not change facts, money, dates, commitments, recipients, or language.
- Before sending, verify To, Cc, Bcc, subject, body, and source message. Reply-all and Bcc are shown separately for confirmation.
- The daily brief is optional and off by default. Configure its dimensions, schedule, and timezone before enabling it.

Need help? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md). Chinese instructions: [README.zh-CN.md](README.zh-CN.md).
