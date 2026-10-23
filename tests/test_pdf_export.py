import pytest

import pdf_export
from pdf_export import PdfError


def test_settings(monkeypatch):
    monkeypatch.setattr(pdf_export, "word_available", lambda: False)
    monkeypatch.setattr(pdf_export, "soffice", lambda: "soffice")
    assert pdf_export.pick(None) == "libreoffice"
    assert pdf_export.pick("none") == "none"
    with pytest.raises(PdfError, match="Word wasn't found"):
        pdf_export.pick("word")
    with pytest.raises(PdfError, match="must be one of"):
        pdf_export.pick("pandoc")


def test_word_first(monkeypatch):
    monkeypatch.setattr(pdf_export, "word_available", lambda: True)
    monkeypatch.setattr(pdf_export, "soffice", lambda: "soffice")
    assert pdf_export.pick("auto") == "word"
    assert pdf_export.pick("libreoffice") == "libreoffice"


def test_nothing_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_export, "word_available", lambda: False)
    monkeypatch.setattr(pdf_export, "soffice", lambda: None)
    with pytest.raises(PdfError, match="LibreOffice"):
        pdf_export.export([tmp_path / "x.docx"], "auto")
    assert pdf_export.export([tmp_path / "x.docx"], "none") == "none"
