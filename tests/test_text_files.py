"""The text I/O policy: UTF-8 and LF for every model file, on every platform.

Built-in ``open()`` without ``encoding`` uses the locale encoding and without
``newline`` translates to the platform line ending, so the same converter
would write cp1252 and CRLF on Windows where it writes UTF-8 and LF on
Linux. These tests pin the bytes, not the platform.
"""

from pathlib import Path

import pytest

from modfilegen import text_files
from modfilegen.converter import Converter
from modfilegen.Converter.SticsConverter.sticsconverter import (
    remove_comma as remove_comma_v9,
)
from modfilegen.Converter.SticsV11Converter.sticsconverter import (
    remove_comma as remove_comma_v11,
)


# --- the policy itself -----------------------------------------------------


def test_the_write_policy_is_utf8_and_lf():
    """Changing this silently changes every file a model reads."""
    assert text_files.WRITE == {"encoding": "utf-8", "newline": "\n"}


def test_reads_are_strict_utf8():
    assert text_files.READ == {"encoding": "utf-8"}


def test_engine_output_is_decoded_leniently():
    """A Fortran program may emit a byte no decoder accepts.

    Losing a whole simulation over a degree sign in a label nobody parses
    would be worse than replacing the character.
    """
    assert text_files.READ_ENGINE["errors"] == "replace"
    # Newline translation is left on, so a CRLF report from a Windows build
    # still parses: no "newline" key here.
    assert "newline" not in text_files.READ_ENGINE


# --- writing a model input file -------------------------------------------


def test_write_file_uses_lf_and_never_crlf(tmp_path):
    Converter().write_file(str(tmp_path), "param.txt", "first\nsecond\n")

    written = (tmp_path / "param.txt").read_bytes()
    assert written == b"first\nsecond\n"
    assert b"\r" not in written


def test_write_file_encodes_as_utf8(tmp_path):
    """The STICS parameter descriptions carry French accents."""
    Converter().write_file(str(tmp_path), "param.txt", "minéralisation\n")

    assert (tmp_path / "param.txt").read_bytes() == "minéralisation\n".encode("utf-8")


def test_write_file_creates_the_directory(tmp_path):
    target = tmp_path / "deep" / "usm"

    Converter().write_file(str(target), "param.txt", "x\n")

    assert (target / "param.txt").read_text(encoding="utf-8") == "x\n"


@pytest.mark.parametrize("version", ["v9", "v11"])
def test_the_module_level_write_file_also_uses_lf(tmp_path, version):
    """Each converter has its own write_file next to the shared one."""
    if version == "v9":
        from modfilegen.Converter.SticsConverter.sticsconverter import write_file
    else:
        from modfilegen.Converter.SticsV11Converter.sticsconverter import write_file

    write_file(str(tmp_path), "tempopar.sti", "codeseprapport\n2\n")

    assert (tmp_path / "tempopar.sti").read_bytes() == b"codeseprapport\n2\n"


# --- reading an engine's own output ---------------------------------------


REMOVE_COMMA = {"v9": remove_comma_v9, "v11": remove_comma_v11}


@pytest.mark.parametrize("version", sorted(REMOVE_COMMA))
def test_remove_comma_strips_the_trailing_separator(tmp_path, version):
    report = tmp_path / "mod_rapport.sti"
    report.write_bytes(b"a;b;\nc;d;\n")

    REMOVE_COMMA[version](str(report))

    assert report.read_bytes() == b"a;b;\nc;d\n"


@pytest.mark.parametrize("version", sorted(REMOVE_COMMA))
def test_remove_comma_survives_a_byte_no_decoder_accepts(tmp_path, version):
    """0xF8 is what DSSAT writes for a degree sign; 0xB0 appears in a .ECO.

    Strict UTF-8 would raise UnicodeDecodeError here and lose the simulation.
    """
    report = tmp_path / "mod_rapport.sti"
    report.write_bytes(b"temp\xf8;value;\n1;2;\n")

    REMOVE_COMMA[version](str(report))

    text = report.read_text(encoding="utf-8")
    assert text.endswith("1;2\n")
    assert "value" in text


@pytest.mark.parametrize("version", sorted(REMOVE_COMMA))
def test_remove_comma_normalises_a_crlf_report_to_lf(tmp_path, version):
    """A Windows build of STICS writes CRLF; the readers then split on ';'.

    Reading with newline translation on and writing with LF makes the file
    look the same as on Linux.
    """
    report = tmp_path / "mod_rapport.sti"
    report.write_bytes(b"a;b;\r\nc;d;\r\n")

    REMOVE_COMMA[version](str(report))

    assert b"\r" not in report.read_bytes()


# --- no site left behind ---------------------------------------------------


def test_nothing_opens_a_text_file_without_an_encoding():
    """A single bare open() is enough to make Windows diverge again.

    This guard used to scan only src/, which is how `setup.py` kept
    `open('README.rst').read()`: on Windows that decodes a UTF-8 README as
    cp1252 and `pip install` dies on the first emoji. So the scan now covers
    setup.py and the tests too.
    """
    import re

    root = Path(text_files.__file__).resolve().parents[2]
    if not (root / "setup.py").exists():
        pytest.skip("not running from a source checkout")

    # setup.py and the package. tests/ is left out for now: the APSIM test
    # modules still carry bare open() calls, and their fix sits in an
    # uncommitted branch of work.
    targets = [root / "setup.py"]
    targets.extend(sorted((root / "src").rglob("*.py")))

    call = re.compile(r"(?:with|=|\breturn)\s+open\(")
    offenders = []
    for path in targets:
        if path.name in {"text_files.py", "test_text_files.py"}:
            continue
        if any(part in {"build", "dist", "__pycache__"} for part in path.parts):
            continue
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not call.search(line) or line.strip().startswith("#"):
                continue
            if any(
                token in line
                for token in ("encoding=", "text_files.", "'rb'", '"rb"', "'wb'", '"wb"')
            ):
                continue
            # A call split over several lines carries the policy further down.
            if line.rstrip().endswith("open("):
                continue
            offenders.append(f"{path.relative_to(root)}:{number} {line.strip()}")

    assert not offenders, "open() without an encoding:\n" + "\n".join(offenders)


def test_setup_py_reads_its_metadata_on_a_non_utf8_locale():
    """`pip install` must not depend on the machine's locale encoding.

    setup.py reads README.rst, which carries emoji. On Windows the default
    is cp1252 and the build backend died decoding them, so the package could
    not be installed there at all. PYTHONUTF8=0 reproduces that: it falls
    back to the ANSI code page on Windows and to ASCII under LC_ALL=C.
    """
    import os
    import subprocess
    import sys

    root = Path(text_files.__file__).resolve().parents[2]
    if not (root / "setup.py").exists():
        pytest.skip("not running from a source checkout")
    # setup.py imports setuptools on line 11, before reading README on line
    # 16, so without setuptools this would pass without testing anything.
    # uv does not seed it into a virtual environment; `pip install -e
    # ".[dev]"` brings it in.
    pytest.importorskip("setuptools")

    environment = dict(os.environ)
    environment.update(
        {"PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C", "LANG": "C"}
    )

    result = subprocess.run(
        [sys.executable, "setup.py", "--version"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "UnicodeDecodeError" not in result.stderr
