import sys
import tempfile
import unittest
from io import BytesIO
from email.message import EmailMessage
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from email_steward.attachments import (
    MAX_ATTACHMENT_BYTES,
    MAX_TOTAL_ATTACHMENT_BYTES,
    cleanup_temp_files,
    safe_attachment_paths,
)


class SafeAttachmentTests(unittest.TestCase):
    def _message_with_attachments(self, attachments):
        message = EmailMessage()
        message.set_content("Please review the attached files.")
        for filename, content_type, content in attachments:
            maintype, subtype = content_type.split("/", 1)
            message.add_attachment(
                content, maintype=maintype, subtype=subtype, filename=filename
            )
        return message

    def _ooxml_payload(self, application_directory):
        payload = BytesIO()
        with ZipFile(payload, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
            archive.writestr(f"{application_directory}/document.xml", "<document />")
        return payload.getvalue()

    def test_allowlist_materializes_only_safe_business_file_types(self):
        message = self._message_with_attachments(
            [
                ("proposal.pdf", "application/pdf", b"%PDF-1.7\n% safe test bytes"),
                ("brief.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", self._ooxml_payload("word")),
                ("costs.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", self._ooxml_payload("xl")),
                ("contacts.csv", "text/csv", b"name,value\nAda,1\n"),
                ("notes.txt", "text/plain", b"safe test text"),
                ("product.png", "image/png", b"\x89PNG\r\n\x1a\n safe test bytes"),
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
        self.assertEqual(
            [path.read_bytes() for path in paths],
            [
                b"%PDF-1.7\n% safe test bytes",
                self._ooxml_payload("word"),
                self._ooxml_payload("xl"),
                b"name,value\nAda,1\n",
                b"safe test text",
                b"\x89PNG\r\n\x1a\n safe test bytes",
            ],
        )

    def test_rejects_executables_scripts_macro_documents_and_archives(self):
        message = self._message_with_attachments(
            [
                ("installer.exe", "application/vnd.microsoft.portable-executable", b"MZ"),
                ("setup.ps1", "text/plain", b"Write-Host unsafe"),
                ("payload.js", "application/javascript", b"alert('unsafe')"),
                ("budget.xlsm", "application/vnd.ms-excel.sheet.macroEnabled.12", b"PK\x03\x04"),
                ("letter.docm", "application/vnd.ms-word.document.macroEnabled.12", b"PK\x03\x04"),
                ("bundle.zip", "application/zip", b"PK\x03\x04"),
            ]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        paths = safe_attachment_paths(message, temp_dir)

        self.assertEqual(paths, [])
        self.assertEqual(list(temp_dir.iterdir()), [])

    def test_normalizes_filename_and_never_writes_outside_the_temp_directory(self):
        message = self._message_with_attachments(
            [("..\\..//Q3 proposal (final).pdf", "application/pdf", b"%PDF-1.7\n% safe test bytes")]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        paths = safe_attachment_paths(message, temp_dir)

        self.assertEqual([path.name for path in paths], ["Q3_proposal_final.pdf"])
        self.assertTrue(paths[0].resolve().is_relative_to(temp_dir.resolve()))

    def test_cleanup_removes_all_temporary_attachment_bytes(self):
        message = self._message_with_attachments([("proposal.pdf", "application/pdf", b"%PDF-1.7\n% safe test bytes")])
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))

        safe_attachment_paths(message, temp_dir)
        cleanup_temp_files(temp_dir)

        self.assertFalse(temp_dir.exists())

    def test_rejects_allowed_names_when_payload_signatures_do_not_match(self):
        message = self._message_with_attachments(
            [
                ("invoice.pdf", "application/pdf", b"This is not a PDF"),
                ("photo.png", "image/png", b"This is not a PNG"),
                ("brief.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK\x03\x04 not a complete OOXML archive"),
                ("contacts.csv", "text/csv", b"\xff\xfe\x00\x01"),
            ]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        self.assertEqual(safe_attachment_paths(message, temp_dir), [])
        self.assertEqual(list(temp_dir.iterdir()), [])

    def test_rejects_missing_or_malformed_declared_mime_types(self):
        message = EmailMessage()
        message.set_content("Please review the attached files.")

        missing_type = EmailMessage()
        missing_type.set_payload(b"safe text")
        missing_type["Content-Disposition"] = 'attachment; filename="notes.txt"'
        message.make_mixed()
        message.attach(missing_type)

        malformed_type = EmailMessage()
        malformed_type.set_payload(b"safe text")
        malformed_type["Content-Type"] = "text/plain; charset"
        malformed_type["Content-Disposition"] = 'attachment; filename="other.txt"'
        message.attach(malformed_type)

        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        self.assertEqual(safe_attachment_paths(message, temp_dir), [])
        self.assertEqual(list(temp_dir.iterdir()), [])

    def test_rejects_a_single_allowed_attachment_before_writing_when_it_exceeds_the_limit(self):
        message = self._message_with_attachments(
            [("large.txt", "text/plain", b"a" * (MAX_ATTACHMENT_BYTES + 1))]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        with self.assertRaisesRegex(ValueError, "single attachment"):
            safe_attachment_paths(message, temp_dir)

        self.assertEqual(list(temp_dir.iterdir()), [])

    def test_cleans_up_files_from_this_call_when_total_attachment_limit_is_exceeded(self):
        first = b"a" * (MAX_ATTACHMENT_BYTES - 1024)
        second = b"b" * (MAX_ATTACHMENT_BYTES - 1024)
        third = b"c" * (MAX_ATTACHMENT_BYTES - 1024)
        message = self._message_with_attachments(
            [
                ("first.txt", "text/plain", first),
                ("second.txt", "text/plain", second),
                ("third.txt", "text/plain", third),
            ]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        with self.assertRaisesRegex(ValueError, "total attachment"):
            safe_attachment_paths(message, temp_dir)

        self.assertEqual(list(temp_dir.iterdir()), [])

    def test_rejects_ooxml_with_excessive_declared_uncompressed_content(self):
        payload = BytesIO()
        with ZipFile(payload, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
            archive.writestr("word/document.xml", "<document />")
            archive.writestr("word/oversized.xml", b"x" * (64 * 1024 * 1024 + 1))
        message = self._message_with_attachments(
            [("brief.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", payload.getvalue())]
        )
        temp_dir = Path(tempfile.mkdtemp(dir=Path(__file__).parent))
        self.addCleanup(cleanup_temp_files, temp_dir)

        self.assertEqual(safe_attachment_paths(message, temp_dir), [])
        self.assertEqual(list(temp_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
