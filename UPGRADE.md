# Upgrade guide

## From the former Skill name

`business-email-managerment` was a spelling error. It remains as a compatibility entry, so existing references keep working. For every new instruction, use `business-email-management`.

## Safe upgrade

1. Keep your existing workspace and do not copy passwords or `.email-steward` data into a new ZIP.
2. Replace only the public Agent files from the new release; retain your operating-system credential entry.
3. Re-open the Codex project in the workspace. Use Luna with low reasoning for reading and Terra with low reasoning plus `humanizer` for drafting.
4. Run one read-only mail query and one unsent draft. Do not send a test email.

If the read-only IMAP check fails, correct the connection issue and run the installer again. It removes only an incomplete new installation; it never overwrites an existing non-empty workspace.
