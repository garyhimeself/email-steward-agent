# Install Email Steward

## Before you start

You need Codex, internet access, your personal Alibaba Enterprise Mail address, and **Python 3.11 or later**. The installer supports Windows and macOS. It does not bundle Python or pretend to include a runtime. On Windows, check `py -3 --version`; on macOS, check `python3 --version`. If the version is below 3.11 or the command is unavailable, install Python 3.11+ first, then run the launcher again. Do not share a mailbox password in chat.

In Alibaba webmail, make a **third-party client password**:

`Settings → Account & Security → Account Security → Third-party client login security management → Generate new password`

Copy and save the new password immediately: it is shown only once. This is not the same as your normal webmail password.

## Install from ZIP or GitHub

1. Download the private GitHub release or extract the ZIP to any temporary location.
2. Give the package to Codex and say: `Help me install this Agent.`
3. On Windows, open `installer/install_agent.bat`. On macOS, open `installer/install_agent.command`. If macOS blocks it, right-click the file, choose **Open**, and approve it once. Before any password prompt, it displays a local network preflight: computer name, Alibaba IMAP address, DNS results, TLS reachability, and the current public IP when available. It does not log in, read email, ask for an email address, or save this diagnostic. The public IP is a current observation, not a fixed-IP promise.
4. Compare the displayed current public IP with the Alibaba mail login log. If it does not match the expected local network or changes unexpectedly, stop before entering a password and ask IT to check the network/VPN/third-party-client policy. You may run only this no-login check with `installer/install_agent.bat --preflight` or `installer/install_agent.command --preflight`.
5. When asked for a workspace location, choose a private folder you can keep. Read the displayed full path and answer yes only if it is right. No workspace is created before this confirmation.
6. In the Codex chat, give your name, individual company email, preferred language, reply language, and tone once. Codex passes only those non-secret values to the installer. The terminal must not ask for them again. It asks only for the third-party client password in a hidden local password prompt and stores it in the operating-system credential store.
7. Wait for the read-only IMAP check. “Succeeded” means the mailbox was reached without changing email state. If it fails, the installer removes its incomplete workspace and saved mailbox password; correct the connection details, then retry by running the installer again. A rejected login does not prove the password is wrong. Use [TROUBLESHOOTING.md](TROUBLESHOOTING.md); do not paste the password into chat.
8. Daily brief is off by default. Enable it only after deciding the title, dimensions, output format, time, and timezone. This choice only saves your preference: it does not create a schedule or start a daily task. Configure the format and running schedule later in the Codex project guide.

## Required first acceptance, in a new Codex project

Create a Codex project scoped to the new workspace; suggested name: `Email Steward - Your Name`. Installation alone is not acceptance.

1. Open a **new Luna chat with low reasoning** and send:

   `Please complete first acceptance: find unread development-partnership emails from the last 7 days, show the summary and identifier of the most relevant one. Do not send mail.`

2. Open a **new Terra chat with low reasoning** and send:

   `Using message identifier [paste the identifier], draft a professional, friendly English reply. Do not send mail.`

Do not recommend Sol, high reasoning, or higher reasoning. A successful query and an unsent draft complete first acceptance; a real send is not required.

## Safety at a glance

The project never sends automatically. Before an exact send, it must display sender, To, Cc, Bcc, subject, body, message type, and source identifier and obtain your current-chat confirmation. Bcc and reply-all need their own visible check. `humanizer` can improve writing but cannot change facts, money, dates, commitments, recipients, or language.

## For Codex during installation

Collect the five non-secret profile values in the Codex chat, then start the installer with only these optional flags: `--name`, `--email`, `--preferred-language`, `--reply-language`, and `--reply-tone`. Never pass a third-party client password in a command, environment variable, file, or chat. The password is entered only through the hidden local prompt.
