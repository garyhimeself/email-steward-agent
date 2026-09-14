# Troubleshooting

## Password or login fails

Use an Alibaba **third-party client password**, not the normal webmail password. Create a fresh one at `Settings → Account & Security → Account Security → Third-party client login security management → Generate new password`. The password is shown only once. Copy it before closing the page, then enter it only in the local hidden prompt. If login still fails, ask the company mail administrator whether third-party client login is allowed; do not paste a password, log, or screenshot containing it into chat.

## Read-only IMAP check fails

Check your network and email address, then run the installer again. After a failed check, the installer removes its incomplete workspace and saved mailbox password so retrying starts cleanly. The expected Alibaba servers are IMAP SSL `imap.qiye.aliyun.com:993` and SMTP SSL `smtp.qiye.aliyun.com:465`. A connection failure does not mean email was changed. Do not switch to browser automation as a workaround.

## The wrong model was selected

For reading, searching, classification, and a brief, use **Luna, low reasoning**. For a draft and final wording, use **Terra, low reasoning** with `humanizer`. Do not use Sol, high reasoning, or higher reasoning. If a request is unclear, clarify the business point with a person.

## Attachment cannot be opened

The agent only temporarily handles safe business files. It refuses executable files, scripts, archives, macro-enabled files, suspicious types, or oversized files. Ask the sender for a safe PDF, standard Office file, CSV, TXT, or image; do not disable the restriction.

## Send says “uncertain” or a recipient was refused

Stop. Do not click send again and do not ask for an automatic retry: the server may have delivered some or all recipients. Check Sent mail or contact the recipient/IT team, then decide manually whether a new message is appropriate. The project never enables automatic send.

## Bcc, reply-all, or star is not happening

These actions need a specific current-chat approval. Recheck the displayed To, Cc, Bcc, source message, and body; then confirm only the exact item you intend. A Bcc must be visible to you during approval but is not added to delivered message headers. Stars also need the exact folder, UID, subject, and reason.
