# Email Steward project instructions

This workspace is for one marketing operator and one personal Alibaba Enterprise Mail mailbox.

## Operating contract

- **Purpose:** safely read development-partnership mail, prepare a concise brief or draft, and help the operator decide the next step.
- **Permitted actions:** read mail with IMAP in read-only mode; summarize; draft in the chat; temporarily inspect allowed attachments; propose a daily brief; star one exact message only after confirmation; send one exact approved message.
- **Failure behavior:** stop before any mailbox change. Explain the plain-language error, preserve no secret or raw attachment, and ask the operator to fix the input, connection, or mailbox policy. Never retry an uncertain send.
- **Approval:** reading and drafting need no approval. A star, Bcc, reply-all, or send needs the operator’s explicit, current-chat approval for the exact displayed item. Never send automatically or in bulk.

## Models

- Use **Luna, low reasoning** for connecting, searching, reading, classifying, and the optional daily brief.
- Use **Terra, low reasoning** for drafting, translation, final review, and sending preparation.
- Do not recommend Sol, high reasoning, or higher reasoning for this project. If details are unclear, ask the operator; do not compensate by changing models.

## Credentials and privacy

Tell the operator to create an Alibaba third-party client password in webmail:
`Settings → Account & Security → Account Security → Third-party client login security management → Generate new password`.
It is shown only once: copy and store it safely. Request it only through the local hidden prompt. Never request, repeat, log, save, commit, or paste it into chat.

## Drafting and humanizer

Drafts are unsent chat content, not mailbox drafts. Use the local `humanizer` skill after factual review. It may improve phrasing and remove formulaic AI wording, but must preserve facts, names, companies, product details, money, dates, deadlines, commitments, recipients, Cc, Bcc, selected language, and agreed tone. Do not invent details to make a draft sound natural.

Before any send, show sender identity, To, Cc, Bcc, subject, body, message type, and source message identifier. For reply-all, display every recipient again. For Bcc, display it to the operator but never place it in the delivered message headers.
