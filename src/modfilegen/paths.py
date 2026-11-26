"""Reading simulation identifiers out of a USM directory path.

The converters locate a simulation by position in the path they are handed:
``<temp>/<idsim>/<idPoint>/<year>``, with the identifier at ``parts[-3]``.

They used to split on ``os.sep``. On Windows that is a backslash, so a path
written with forward slashes -- which Python, pathlib, every notebook and
every test accept -- split into a single element and the lookup raised
``IndexError: list index out of range``.

``PurePath.parts`` reads both separators on Windows and the POSIX one
elsewhere, and keeps the same component count as the old split for the
absolute and relative paths the converters are given, so the negative
indices they use are unchanged.

One difference is deliberate: a trailing separator no longer yields a final
empty component. ``"a/b/"`` gives ``("a", "b")`` where the split gave
``["a", "b", ""]``.
"""

from pathlib import PurePath

__all__ = ["path_parts"]


def path_parts(directory_path):
    """The components of ``directory_path``, whatever separator it uses."""
    return PurePath(directory_path).parts
