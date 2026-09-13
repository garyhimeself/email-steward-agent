import sys
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.attachments import cleanup_temp_files, safe_attachment_paths


class SafeAttachmentTests(unittest.TestCase):
    def _message_with_attachments(self, attachments):
        message = EmailMessage()
        message.set_content("Please review the attached files.")
        for filename, content_type in attachments:
            maintype, subtype = content_type.split("/", 1)
            message.add_attachment(
                b"safe test bytes", maintype=maintype, subtype=subtype, filename=filename
            )
        return message

    def test_allowlist_materializes_only_safe_business_file_types(self):
        message = self._message_with_attachments(
            [
                ("proposal.pdf", "application/pdf"),
                ("brief.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                ("costs.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("contacts.csv", "text/csv"),
                ("notes.txt", "text/plain"),
                ("product.png", "image/png"),
            ]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        paths = safe_attachment_paths(message, temp_dir)

        self.assertEqual(
            [path.name for path in paths],
            ["proposal.pdf", "brief.docx", "costs.xlsx", "contacts.csv", "notes.txt", "product.png"],
        )
        self.assertTrue(all(path.parent == temp_dir for path in paths))
        self.assertEqual([path.read_bytes() for path in paths], [b"safe test bytes"] * 6)

    def test_rejects_executables_scripts_macro_documents_and_archives(self):
        message = self._message_with_attachments(
            [
                ("installer.exe", "application/vnd.microsoft.portable-executable"),
                ("setup.ps1", "text/plain"),
                ("payload.js", "application/javascript"),
                ("budget.xlsm", "application/vnd.ms-excel.sheet.macroEnabled.12"),
                ("letter.docm", "application/vnd.ms-word.document.macroEnabled.12"),
                ("bundle.zip", "application/zip"),
            ]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        paths = safe_attachment_paths(message, temp_dir)

        self.assertEqual(paths, [])
        self.assertEqual(list(temp_dir.iterdir()), [])

    def test_normalizes_filename_and_never_writes_outside_the_temp_directory(self):
        message = self._message_with_attachments(
            [("..\\..//Q3 proposal (final).pdf", "application/pdf")]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        paths = safe_attachment_paths(message, temp_dir)

        self.assertEqual([path.name for path in paths], ["Q3_proposal_final.pdf"])
        self.assertTrue(paths[0].resolve().is_relative_to(temp_dir.resolve()))

    def test_cleanup_removes_all_temporary_attachment_bytes(self):
        message = self._message_with_attachments([("proposal.pdf", "application/pdf")])
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))

        safe_attachment_paths(message, temp_dir)
        cleanup_temp_files(temp_dir)

        self.assertFalse(temp_dir.exists())


if __name__ == "__main__":
    unittest.main()
