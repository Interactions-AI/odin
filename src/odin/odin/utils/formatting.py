"""Formatting utils
"""
from itertools import chain
from typing import Set, Optional
from collections import namedtuple


# https://stackoverflow.com/questions/5909873/how-can-i-pretty-print-ascii-tables-with-python
def print_table(rows: namedtuple, columns: Optional[Set[str]] = None) -> None:
    """Pretty print a table

    :param rows: Some rows
    :param columns: A set of columns to include in the output.
    """
    columns = columns if columns is not None else set(rows[0]._fields)
    fields = [f for f in rows[0]._fields if f in columns]
    if len(rows) > 1:
        lens = [
            len(str(max(chain((getattr(x, field) for x in rows), [field]), key=lambda x: len(str(x)))))
            for field in fields
        ]
        formats = []
        hformats = []
        for i, field in enumerate(fields):
            if isinstance(getattr(rows[0], field), int):
                formats.append("%%%dd" % lens[i])
            else:
                formats.append("%%-%ds" % lens[i])
            hformats.append("%%-%ds" % lens[i])
        pattern = " | ".join(formats)
        hpattern = " | ".join(hformats)
        separator = "-+-".join(['-' * n for n in lens])
        print(hpattern % tuple(fields))
        print(separator)
        for line in rows:
            print(pattern % tuple(getattr(line, field) for field in fields))
    elif len(rows) == 1:
        row = rows[0]
        hwidth = len(max(fields, key=lambda x: len(x)))
        for field in fields:
            print("%*s = %s" % (hwidth, field, getattr(row, field)))
