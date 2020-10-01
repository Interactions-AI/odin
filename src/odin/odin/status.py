"""Tool to get odin job status
"""
import argparse
from collections import namedtuple
from typing import Union, List, Tuple, Set, Optional

from baseline.utils import exporter, listify, read_config_stream, color, Colors
from mead.utils import convert_path
from odin.store import Store, create_store_backend
from odin.executor import PipelineStatus
from odin.utils.formatting import print_table

__all__ = []
export = exporter(__all__)

DEFAULT_COLUMNS = {'task', 'status', 'command', 'resource_id', 'submitted'}
Row = namedtuple('Row', 'task status command name image resource_type resource_id submitted completed')
Pipeline = namedtuple('Pipeline', 'label job version status submitted completed')


def id2row(job_name: str, status: str, store: Store) -> Row:
    """Convert some id to a `Row`

    :param job_name: A job id
    :param status: the job status
    :param store: The jobs DB
    :return: A `Row`
    """
    job_details = store.get(job_name)
    return Row(
        job_name,
        status,
        job_details['command'],
        job_details['name'],
        job_details['image'],
        job_details.get('resource_type', "Pod"),
        job_details.get(Store.RESOURCE_ID),
        job_details.get(Store.SUBMIT_TIME),
        job_details.get(Store.COMPLETION_TIME),
    )


def ids2rows(job_names: Union[str, List[str]], status: str, store: Store) -> List[Row]:
    """Convert one or more ids a `List[Row]`

    :param job_names: A list
    :param status: the job status
    :param store: The jobs DB
    :return: A `List[Row]`
    """
    job_names = listify(job_names)
    return [id2row(job_name, status, store) for job_name in job_names]


def get_status(work: str, store: Store) -> Tuple[Pipeline, List[Row]]:
    """Get status for a pipeline

    :param work: A pipeline name
    :param store: A job store
    :return: The information about the pipeline and a list of information about each pod
    """
    parent_details = store.get(work)
    pipe = Pipeline(
        parent_details[Store.PIPE_ID],
        parent_details.get(Store.JOB_NAME),
        parent_details.get(Store.REV_VER),
        parent_details['status'],
        parent_details.get(Store.SUBMIT_TIME),
        parent_details.get(Store.COMPLETION_TIME),
    )
    rows = []
    job_names = parent_details[Store.EXECUTED]
    rows += ids2rows(job_names, Store.EXECUTED, store)

    job_name = parent_details[Store.EXECUTING]
    if job_name:
        rows += ids2rows(job_name, "terminated" if pipe.status == "TERMINATED" else Store.EXECUTING, store)

    job_names = parent_details[Store.WAITING]
    rows += ids2rows(job_names, Store.WAITING, store)
    return pipe, rows


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


def main():
    """Take in a job and get back its status

    TODO: support passing in specific Job IDs and regex
    """
    parser = argparse.ArgumentParser(description='Get job status')
    parser.add_argument('work', help='Pipeline or Job')
    parser.add_argument('--cred', help='cred file', type=convert_path, required=True)
    parser.add_argument('--format', help='Format the output', default="human")
    parser.add_argument('--columns', nargs="+", default=[], help="Columns of the status to show.")
    parser.add_argument('--all', action='store_true', help="Show all columns of the status message.")
    args = parser.parse_args()
    cred_params = read_config_stream(args.cred)
    store = create_store_backend(**cred_params['jobs_db'])
    work = store.parents_like(args.work)
    if not work:
        print('No job found')
    for parent in work:
        try:
            show_status(*get_status(parent, store), columns=set(args.columns), all_cols=args.all)
        except Exception:
            print('ERROR: Skipping {}'.format(parent))


if __name__ == "__main__":
    main()
