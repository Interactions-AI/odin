"""Cleanup odin jobs
"""
import os
import shutil
import argparse
from collections import namedtuple
from itertools import chain
from typing import List, Optional, Set

from baseline.utils import exporter, read_config_stream
from mead.utils import convert_path
from odin import LOGGER
from odin.k8s import KubernetesTaskManager, TaskManager
from odin.store import Store, MongoStore
from odin.utils.formatting import print_table


__all__ = []
export = exporter(__all__)


Cleaned = namedtuple('Cleaned', 'task_id cleaned_from_k8s purged_from_db removed_from_fs')


def done(job: str, completed: Set[str]) -> str:
    """Convert set membership into `Yes` for `No`.

    :param job: The job to check if it was acted on
    :param completed: The jobs acted on,
    :returns: Yes or No
    """
    return 'Yes' if job in completed else 'No'


@export
def cleanup(
    work: str,
    store: Store,
    sched: Optional[TaskManager] = None,
    purge_db: bool = False,
    purge_fs: bool = False,
    data_dir: Optional[str] = None,
) -> List[Cleaned]:
    """Cleanup a job

    :param work: The name of the job
    :param store: The job store
    :param sched: The scheduler used to kill jobs.
    :param purge_db: Should the pipeline also be removed from the job db.
    :param purge_fs: Should the pipeline also be removed from the file system.
    :param data_dir: A directory that combined with work is where all artifacts produced by the pipeline live.

    :returns: The list jobs and if it was removed from k8s or the job db.
    """
    if not work:
        return []
    sched = sched if sched else KubernetesTaskManager(store)
    parent_details = store.get(work)
    children = list(chain(parent_details[Store.EXECUTED], parent_details[Store.EXECUTING]))
    cleaned = set()
    purged = set()
    removed = set()
    if purge_fs:
        if data_dir is None:
            LOGGER.warning("Requested removal from the file system but no data directory provided.")
        else:
            shutil.rmtree(os.path.join(data_dir, work), ignore_errors=True)
            removed = set(chain([work], children))
    for job in children:
        try:
            sched.kill(job)
            cleaned.add(job)
        except:  # pylint: disable=bare-except
            pass
        if purge_db:
            if store.remove(job):
                purged.add(job)
    # Remove the work entry from the db last so if there is an error before hand we can still use the db entry.
    if purge_db:
        if store.remove(work):
            purged.add(work)
    return [Cleaned(j, done(j, cleaned), done(j, purged), done(j, removed)) for j in chain([work], children)]


def main():
    """Clean up a job
    """
    parser = argparse.ArgumentParser(description='Clean up a job')
    parser.add_argument('work', help='Job')
    parser.add_argument('--cred', help='cred file', type=convert_path, required=True)
    parser.add_argument('--db', action='store_true', help="Also remove from the jobs db")
    parser.add_argument('--fs', action='store_true', help="Also remove from the filesystem")
    parser.add_argument('--data_dir', help="The root of where data is saved.")

    args = parser.parse_args()

    cred_params = read_config_stream(args.cred)
    store = MongoStore(**cred_params['jobs_db'])

    cleaned = cleanup(args.work, store, purge_db=args.db, purge_fs=args.fs, data_dir=args.data_dir)
    print("Results of this request:")
    print_table(cleaned)


if __name__ == "__main__":
    main()
