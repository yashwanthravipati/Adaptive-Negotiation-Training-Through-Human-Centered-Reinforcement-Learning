"""ZIP uploads preserve document boundaries and tolerate unusable bundle entries."""

import io
import stat
import struct
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from negotrain.cases import documents
from negotrain.cases.documents import extract_documents
from test_prep import make_docx, make_pdf


def make_zip(files: list[tuple[str | ZipInfo, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in files:
            archive.writestr(name, data)
    return buffer.getvalue()


def test_zip_and_loose_documents_keep_paths_and_text_without_writing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bundle = make_zip(
        [
            ("case/", b""),
            ("case/general.PDF", make_pdf("General instructions")),
            ("case/scores.docx", make_docx("Scores", [["Price", "Points"], ["10", "40"]])),
            ("case/buyer/sheet.txt", b"Buyer instructions"),
            ("case/seller/sheet.txt", b"Seller instructions"),
            ("__MACOSX/._general.PDF", b"metadata"),
            ("case/.DS_Store", b"metadata"),
            ("case/._scores.docx", b"metadata"),
        ]
    )
    extracted, warnings = extract_documents([("case.ZIP", bundle), ("notes.md", b"Notes")])
    assert not warnings
    assert len(extracted) == 5
    assert "General instructions" in extracted["case.ZIP/case/general.PDF"]
    assert "Price\tPoints" in extracted["case.ZIP/case/scores.docx"]
    assert extracted["case.ZIP/case/buyer/sheet.txt"] == "Buyer instructions"
    assert extracted["case.ZIP/case/seller/sheet.txt"] == "Seller instructions"
    assert extracted["notes.md"] == "Notes"
    assert list(tmp_path.iterdir()) == []


def test_zip_keeps_readable_files_and_reports_unreadable_and_unsupported_members():
    bundle = make_zip(
        [
            ("instructions.txt", b"General instructions"),
            ("scan.pdf", b"not a PDF"),
            ("blank.md", b"   "),
            ("photo.png", b"image"),
            ("nested.zip", make_zip([("nested.txt", b"Nested instructions")])),
        ]
    )
    extracted, warnings = extract_documents([("case.zip", bundle)])
    assert extracted == {"case.zip/instructions.txt": "General instructions"}
    for name in ("scan.pdf", "blank.md", "photo.png", "nested.zip"):
        assert any(f"case.zip/{name}" in warning for warning in warnings)


@pytest.mark.parametrize(
    ("data", "message"),
    [(b"not a ZIP", "could not read ZIP"), (make_zip([]), "no supported documents")],
)
def test_invalid_or_empty_archive_does_not_block_other_uploads(data, message):
    extracted, warnings = extract_documents([("case.zip", data), ("notes.txt", b"Notes")])
    assert extracted == {"notes.txt": "Notes"}
    assert any("case.zip" in warning and message in warning for warning in warnings)


def test_duplicate_upload_names_do_not_overwrite_documents():
    extracted, warnings = extract_documents(
        [
            ("case.zip", make_zip([("sheet.txt", b"Buyer")])),
            ("case.zip", make_zip([("sheet.txt", b"Seller")])),
            ("sheet.txt", b"Additional instructions"),
            ("sheet.txt", b"More instructions"),
        ]
    )
    assert not warnings
    assert len(extracted) == 4
    assert set(extracted.values()) == {
        "Buyer",
        "Seller",
        "Additional instructions",
        "More instructions",
    }


def test_zip_skips_unsafe_paths_and_symlinks():
    link = ZipInfo("linked.txt")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    bundle = make_zip(
        [
            ("../outside.txt", b"Outside"),
            ("/absolute.txt", b"Absolute"),
            (link, b"/some/target"),
            ("safe.txt", b"Safe instructions"),
        ]
    )
    extracted, warnings = extract_documents([("case.zip", bundle)])
    assert extracted == {"case.zip/safe.txt": "Safe instructions"}
    assert len(warnings) == 3


@pytest.mark.parametrize(
    ("limit", "value", "files", "message"),
    [
        ("MAX_ZIP_ENTRIES", 1, [("a.txt", b"a"), ("b.txt", b"b")], "too many ZIP entries"),
        ("MAX_ZIP_BYTES", 8, [("large.txt", b"x" * 1024)], "uncompressed ZIP limit"),
    ],
)
def test_zip_limits_report_an_error_before_reading_members(
    monkeypatch, limit, value, files, message
):
    monkeypatch.setattr(documents, limit, value)

    def unexpected_read(*args, **kwargs):
        pytest.fail("oversized ZIP members must not be decompressed")

    bundle = make_zip(files)
    monkeypatch.setattr(ZipFile, "open", unexpected_read)
    extracted, warnings = extract_documents([("large.zip", bundle)])
    assert extracted == {}
    assert any(message in warning for warning in warnings)


def test_password_protected_member_is_reported_and_other_documents_survive():
    bundle = bytearray(make_zip([("private.txt", b"Secret"), ("general.txt", b"Public")]))
    # Mark the first entry encrypted in both ZIP headers, as in a password-protected ZIP.
    struct.pack_into("<H", bundle, 6, 1)
    central = bundle.index(b"PK\x01\x02")
    struct.pack_into("<H", bundle, central + 8, 1)
    extracted, warnings = extract_documents([("case.zip", bytes(bundle))])
    assert extracted == {"case.zip/general.txt": "Public"}
    assert any("case.zip/private.txt" in w and "password-protected" in w for w in warnings)


def test_corrupt_member_is_reported_without_losing_other_documents():
    bundle = bytearray(make_zip([("broken.txt", b"Broken"), ("general.txt", b"Public")]))
    central = bundle.index(b"PK\x01\x02")
    # A CRC mismatch exercises a genuine archive read failure.
    struct.pack_into("<I", bundle, central + 16, 0)
    extracted, warnings = extract_documents([("case.zip", bytes(bundle))])
    assert extracted == {"case.zip/general.txt": "Public"}
    assert any("case.zip/broken.txt" in w and "could not read ZIP entry" in w for w in warnings)
