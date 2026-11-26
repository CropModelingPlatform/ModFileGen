"""One text I/O policy for every model file ModFileGen reads or writes.

Built-in ``open()`` without ``encoding`` uses the locale encoding, and
without ``newline`` it translates ``"\\n"`` to the platform line ending. On
Linux that gives UTF-8 and LF; on Windows it gives cp1252 and CRLF. The same
converter would then write different bytes on a student's laptop than on the
cluster, which is the kind of defect that does not crash, it just changes
results.

So every model file is written as UTF-8 with LF endings, on every platform.
That is exactly what the Linux runs produce today, so the generated files are
unchanged there, and Windows now matches them byte for byte.

``pandas.read_csv`` is not affected: it defaults to UTF-8 rather than the
locale, so the reports parsed with it already behaved the same everywhere.

Reading an engine's own output is the one place where strictness would hurt.
STICS and DSSAT are Fortran programs that occasionally emit a stray
non-UTF-8 byte in a label -- DSSAT's OVERVIEW.OUT carries 0xF8 for a degree
sign. Decoding that strictly raises ``UnicodeDecodeError`` and loses the
whole simulation over a character nobody reads, so engine output is decoded
leniently: the numeric fields, which are what gets parsed, are unaffected.
"""

ENCODING = "utf-8"

#: Writing a file a model will read. LF on every platform.
WRITE = {"encoding": ENCODING, "newline": "\n"}

#: Reading a file ModFileGen itself wrote, or package data: strict.
READ = {"encoding": ENCODING}

#: Reading an engine's own output. Lenient, and newline translation left on,
#: so a report a Windows build wrote with CRLF still parses.
READ_ENGINE = {"encoding": ENCODING, "errors": "replace"}

__all__ = ["ENCODING", "WRITE", "READ", "READ_ENGINE"]
