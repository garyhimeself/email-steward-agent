# Install Email Steward

## Before you start

You need Codex, internet access, and your personal Alibaba Enterprise Mail address. The installer supports Windows and macOS. Do not share a mailbox password in chat.

In Alibaba webmail, make a **third-party client password**:

`Settings → Account & Security → Account Security → Third-party client login security management → Generate new password`

Copy and save the new password immediately: it is shown only once. This is not the same as your normal webmail password.

## Install from ZIP or GitHub

1. Download the private GitHub release or extract the ZIP to any temporary location.
2. Give the package to Codex and say: `Help me install this Agent.`
3. When asked for a workspace location, choose a private folder you can keep. Read the displayed full path and answer yes only if it is right. No workspace is created before this confirmation.
4. On Windows, open `installer/install_agent.bat`. On macOS, open `installer/install_agent.command`. If macOS blocks it, right-click the file, choose **Open**, and approve it once.
5. Give your name, individual company email, preferred language, reply language, and tone. The installer asks the third-party client password only in a hidden local prompt and stores it in the operating-system credential store.
6. Wait for the read-only IMAP check. “Succeeded” means the mailbox was reached without changing email state. If it fails, use [TROUBLESHOOTING.md](TROUBLESHOOTING.md); do not paste the password into chat.
7. Daily brief is off by default. Enable it only after deciding the title, dimensions, output format, time, and timezone.

## Required first acceptance, in a new Codex project

Create a Codex project scoped to the new workspace; suggested name: `Email Steward - Your Name`. Installation alone is not acceptance.

1. Open a **new Luna chat with low reasoning** and send:

   `Please complete first acceptance: find unread development-partnership emails from the last 7 days, show the summary and identifier of the most relevant one. Do not send mail.`

2. Open a **new Terra chat with low reasoning** and send:

   `Using message identifier [paste the identifier], draft a professional, friendly English reply. Do not send mail.`

Do not recommend Sol, high reasoning, or higher reasoning. A successful query and an unsent draft complete first acceptance; a real send is not required.

## Safety at a glance

The project never sends automatically. Before an exact send, it must display sender, To, Cc, Bcc, subject, body, message type, and source identifier and obtain your current-chat confirmation. Bcc and reply-all need their own visible check. `humanizer` can improve writing but cannot change facts, money, dates, commitments, recipients, or language.
