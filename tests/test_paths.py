"""Reading simulation identifiers out of a USM directory path.

The converters find a simulation by position: ``<temp>/<idsim>/<idPoint>/
<year>``, with the identifier at ``parts[-3]``. They used to split on
``os.sep``, which on Windows is a backslash, so a path written with forward
slashes came back as one element and the lookup raised IndexError.
"""

import os
import re
from pathlib import Path

import pytest

from modfilegen import paths
from modfilegen.paths import path_parts

USM = ("sim-1", "5.925_6.025", "2000")


def test_forward_slashes_are_always_understood():
    """Python, pathlib, notebooks and tests all accept this spelling."""
    assert path_parts("tmp/sim-1/5.925_6.025/2000")[-3:] == USM


def test_an_absolute_posix_path_keeps_the_component_count():
    """The converters index from the end, so the count has to match."""
    parts = path_parts("/tmp/sim-1/5.925_6.025/2000")

    assert parts[-3:] == USM
    assert len(parts) == len("/tmp/sim-1/5.925_6.025/2000".split("/"))


def test_the_native_separator_works():
    native = os.path.join("tmp", *USM)

    assert path_parts(native)[-3:] == USM


def test_a_path_object_is_accepted():
    assert path_parts(Path("tmp") / "sim-1" / "5.925_6.025" / "2000")[-3:] == USM


@pytest.mark.skipif(os.name != "nt", reason="backslashes are literal on POSIX")
def test_windows_reads_backslashes_too():
    assert path_parts(r"C:\tmp\sim-1\5.925_6.025\2000")[-3:] == USM


def test_too_short_a_path_does_not_pretend():
    """The converters guard with len(parts) >= 3; give them a real length."""
    assert len(path_parts("output")) == 1


def test_no_converter_splits_a_path_on_the_separator():
    """`os.sep` and `os.path.sep` are the same trap under two spellings.

    The first sweep replaced `split(os.sep)` and missed `split(os.path.sep)`,
    which kept three STICS v11 tests failing on Windows. This guard covers
    both, and the forward-slash split as well.
    """
    source_root = Path(paths.__file__).parent
    pattern = re.compile(
        r"""\.split\(\s*(?:os\.sep|os\.path\.sep|['"]/['"]|os\.altsep)\s*\)"""
    )

    offenders = []
    for path in sorted(source_root.rglob("*.py")):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if line.strip().startswith("#") or not pattern.search(line):
                continue
            offenders.append(f"{path.relative_to(source_root)}:{number} {line.strip()}")

    assert not offenders, (
        "split on a path separator; use modfilegen.paths.path_parts:\n"
        + "\n".join(offenders)
    )
