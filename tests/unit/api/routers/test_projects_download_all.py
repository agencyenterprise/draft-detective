"""Unit tests for the project zip's Content-Disposition header."""

from starlette.responses import StreamingResponse

from lib.api.routers.projects import _attachment_disposition


def test_ascii_name_goes_in_the_plain_form():
    assert _attachment_disposition("Report_files.zip") == (
        'attachment; filename="Report_files.zip"'
    )


def test_non_latin_title_goes_in_the_encoded_form():
    """Starlette encodes headers as Latin-1, so a raw Chinese title fails the response."""
    header = _attachment_disposition("研究 报告_files.zip")

    assert header == (
        "attachment; filename*=utf-8''%E7%A0%94%E7%A9%B6%20%E6%8A%A5%E5%91%8A_files.zip"
    )
    StreamingResponse(iter([b""]), headers={"Content-Disposition": header})
