# Upgrade guide

## From the former Skill name

`business-email-managerment` was a spelling error. It remains as a compatibility entry, so existing references keep working. For every new instruction, use `business-email-management`.

## Safe upgrade

1. Download and extract the new release outside your existing workspace. Do not copy passwords or `.email-steward` data into the release folder.
2. From the extracted release folder, run `installer\install_agent.bat --upgrade-workspace --workspace "C:\path\to\your\existing-workspace"`. This updates only public Agent files; it keeps local configuration, system credentials, and other operator files.
3. Re-open the Codex project in the existing workspace. The first mailbox action runs `python installer/mail_runtime.py credential-status --workspace .`; when it reports `credential_ready`, do not enter a password again.
4. If status is `credential_missing`, use `installer\install_agent.bat --secure-window --repair-credential --workspace "."` from the workspace. Only the separate hidden security window accepts the third-party client password; the workspace is not overwritten.
5. Use Luna with low reasoning for one read-only mail query and Terra with low reasoning plus `humanizer` for one unsent draft. Do not send a test email.
