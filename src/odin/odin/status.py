"""Tool to get odin job status
"""
import argparse
from collections import namedtuple
from typing import Union, List, Tuple

from eight_mile.utils import listify
from baseline.utils import exporter
from odin.store import Store

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
