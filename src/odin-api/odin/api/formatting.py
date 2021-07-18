"""Formatting utils
"""
from itertools import chain
from typing import List, Set, Optional
from collections import namedtuple
from baseline.utils import color, Colors

DEFAULT_COLUMNS = {'task', 'status', 'command', 'resource_id', 'submitted'}

Row = namedtuple('Row', 'task status command name image resource_type resource_id submitted completed')
Pipeline = namedtuple('Pipeline', 'label job version status submitted completed')
Cleaned = namedtuple('Cleaned', 'task_id cleaned_from_k8s purged_from_db removed_from_fs')
Event = namedtuple("Event", "type reason source message timestamp")

class PipelineStatus:
    """Enum of pipeline status.

    Not a real enum to get easier access to string values.
    """

    BUILDING = "BUILDING"
    RUNNING = "RUNNING"
    TERMINATED = "TERMINATED"
    DONE = "DONE"

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


def show_status(pipe: Pipeline, rows: List[Row], columns: Optional[Set[str]] = None, all_cols: bool = False) -> None:
    """Show the status for a pipeline.

    :param pipe: Information about the pipeline itself.
    :param rows: The rows of the table.
    :param columns: A set of columns to include in the output.
    :param all_cols: Include all the columns in the output.
    """
    status = None
    if pipe.status == PipelineStatus.DONE:
        status = color(pipe.status, Colors.CYAN)
    elif pipe.status == PipelineStatus.RUNNING:
        status = color(pipe.status, Colors.GREEN)
    elif pipe.status == PipelineStatus.TERMINATED:
        status = color(pipe.status, Colors.RED)
    elif pipe.status == PipelineStatus.BUILDING:
        status = color(pipe.status, Colors.YELLOW)
    width = max(len(pipe.label), len('Finished'))
    print(f'{pipe.label:<{width}} --> {status}')
    if pipe.submitted is not None:
        start = "Started"
        print(f'{start:<{width}} --> {pipe.submitted}')
    if pipe.completed is not None:
        fin = "Finished"
        print(f'{fin:<{width}} --> {pipe.completed}')
    print()
    if columns:
        columns.update(DEFAULT_COLUMNS)
    else:
        columns = DEFAULT_COLUMNS
    if rows:
        if all_cols:
            columns.update(rows[0]._fields)
        print_table(rows, columns)