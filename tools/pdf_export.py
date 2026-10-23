"""PDF export for the built documents, with whatever this computer has.

config.yaml `pdf_engine`:
    auto         (default) Microsoft Word if installed, else LibreOffice
    word         Word only: Windows (docx2pdf.ps1) or macOS (the docx2pdf package)
    libreoffice  LibreOffice only (free, any system); fonts must be installed for it, and its page count can
                 differ slightly from Word's, so open the PDF once to check
    none         no PDFs; the .docx files are still built

Usage (from the workspace folder):
    python engine/tools/pdf_export.py [--engine auto|word|libreoffice] <file.docx> [...]
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ENGINES = ("auto", "word", "libreoffice", "none")
SOFFICE_PATHS = (r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                 "/Applications/LibreOffice.app/Contents/MacOS/soffice")


class PdfError(Exception):
    pass


def word_available():
    if sys.platform == "win32":
        import winreg
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"))
            return True
        except OSError:
            return False
    if sys.platform == "darwin" and Path("/Applications/Microsoft Word.app").exists():
        try:
            import docx2pdf  # noqa: F401
            return True
        except ImportError:
            return False
    return False


def soffice():
    found = shutil.which("soffice") or shutil.which("libreoffice")
    return found or next((p for p in SOFFICE_PATHS if Path(p).is_file()), None)


def pick(setting):
    """The engine to use ('word', 'libreoffice' or 'none'), or a PdfError saying what is missing."""
    setting = str(setting or "auto").lower()
    if setting not in ENGINES:
        raise PdfError(f"pdf_engine must be one of {ENGINES}, got '{setting}'")
    if setting == "none":
        return "none"
    if setting in ("auto", "word") and word_available():
        return "word"
    if setting == "word":
        hint = " (macOS also needs: pip install docx2pdf)" if sys.platform == "darwin" else ""
        raise PdfError(f"pdf_engine: word, but Microsoft Word wasn't found{hint}")
    if soffice():
        return "libreoffice"
    raise PdfError("no PDF engine found: install LibreOffice (free, libreoffice.org) or Microsoft Word, "
                   "or set pdf_engine: none")


def export(files, setting="auto"):
    """Write <file>.pdf next to each .docx; returns the engine used."""
    engine = pick(setting)
    files = [Path(f).resolve() for f in files]
    if engine == "none":
        return engine
    if engine == "word" and sys.platform == "win32":
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(TOOLS / "docx2pdf.ps1"),
                        *map(str, files)], check=True)
    elif engine == "word":
        from docx2pdf import convert
        for f in files:
            convert(str(f), str(f.with_suffix(".pdf")))
    else:
        # LibreOffice runs its own Python; our PYTHON* variables would confuse it.
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        for f in files:
            subprocess.run([soffice(), "--headless", "--convert-to", "pdf", "--outdir", str(f.parent), str(f)],
                           check=True, stdout=subprocess.DEVNULL, env=env)
            print(f"OK  {f.with_suffix('.pdf')}")
    missing = [f.name for f in files if not f.with_suffix(".pdf").is_file()]
    if missing:
        raise PdfError(f"{engine} wrote no PDF for {', '.join(missing)}")
    return engine


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    if a.engine is None:
        from config import CFG
        a.engine = CFG.get("pdf_engine")
    try:
        print(f"engine: {export(a.files, a.engine)}")
    except PdfError as e:
        print(f"FAILED {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
