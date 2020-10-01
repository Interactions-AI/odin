"""Module to help decide what jobs are worthy of accepting

This module provides an interface for `ExportPolicy` and
various implementations that use XPCTL

It also includes a command-line driver to run the export policies
"""
import argparse
import logging
import json
from operator import gt, ge, itemgetter
from typing import List, Dict, Tuple, Callable, Type, Optional, Union

from baseline.utils import exporter, get_metric_cmp, optional_params, read_config_stream
from mead.utils import convert_path, get_dataset_from_key
from odin.store import Store, create_store_backend
from xpctl import xpctl_client
from xpctl.xpclient.api import XpctlApi
from xpctl.xpclient.rest import ApiException


__all__ = []
export = exporter(__all__)
EXPORT_POLICY_REGISTRY = {}

LOGGER = logging.getLogger('odin')


@export
class ExportPolicy:
    """See several metrics and decide which (if any should be exported)."""

    def __init__(self) -> None:
        """Constructor"""

    def select(self, job_ids: List[str]) -> Dict:
        """Evaluate a trained model based on this policy.

        :param job_ids: List of jobs to evaluate results from

        :returns: A dictionary of results
        """


@export
@optional_params
def register_export_policy(cls: Type[ExportPolicy], name: str = None) -> Type[ExportPolicy]:
    """Register an export policy

    :param cls: The class name
    :param name: The registry name
    :raises Exception: If name is already registered.
    :return: The class
    """
    name = name if name is not None else cls.__name__
    if name in EXPORT_POLICY_REGISTRY:
        raise Exception(
            'Error: attempt to re-define previously '
            f'registered ExportPolicy {name} (old: {EXPORT_POLICY_REGISTRY[name]}, new: {cls}) in registry'
        )
    EXPORT_POLICY_REGISTRY[name] = cls
    return cls


@export
def create_export_policy(name: str, config: Dict) -> ExportPolicy:
    """Create an export policy from the registry

    :param name: A name identifier
    :param config: The configuration to pass
    :return: A constructed instance
    """
    return EXPORT_POLICY_REGISTRY[name](**config)


@export
class ExperimentRepoExportPolicy(ExportPolicy):
    """Select the best model scoring model of the ones seen."""

    DATASET = 'dataset'
    LABEL = 'label'

    def __init__(self, api: XpctlApi, task: str, dataset: Union[str, None], metric: str, **kwargs) -> None:
        """Constructor for experiment repo-based exporting

        :param api: An XPCTL client api object
        :param task: A string task name
        :param dataset: A string key for dataset
        :param metric: The metric to evaluate
        :param kwargs:
        """
        super().__init__()
        self.api = api
        if task is None:
            raise ValueError("`task` parameter must not be None")
        self.task = task
        self.dataset: str = self._find_dataset(dataset) if dataset is not None else None
        self.metric: str = metric
        self.best_value: float = None
        self.best_label: float = None

    def _create_result_dict(self, job_id):
        return {
            "value": self.best_value,
            "selected": job_id,
            "metric": self.metric,
            "task": self.task,
            "dataset": self.dataset,
        }

    def _find_dataset(self, dataset):
        datasets = self.api.task_summary(self.task)
        datasets = {k: k for k in datasets.summary}
        return get_dataset_from_key(dataset, datasets)


@export
@register_export_policy('best-of-batch')
class BestOfBatchExportPolicy(ExperimentRepoExportPolicy):
    """Select a model that is the best of the batch"""

    def __init__(self, api: XpctlApi, task: str, dataset: str, metric: str, user_cmp: str = None, **kwargs) -> None:
        """Construct a best model in batch

        :param api: An XPCTL client api object
        :param task: A string name for the task
        :param dataset: A string key for the dataset
        :param metric: The metric to evaluate
        :param user_cmp: A comparator function
        :param kwargs:
        """
        super().__init__(api, task, dataset=None, metric=metric)
        self.cmp: Callable[[float, float], bool] = None
        self.cmp, self.best_value = get_metric_cmp(self.metric, user_cmp)

    def _get_by_label(self, job_id: str) -> float:
        """
        Get the value for a metric for an experiment. The experiment is found by the label.

        :param job_id: id for a job
        :raises RuntimeError: ApiException indicates we failed to connect to xpctl server.
        :return: the value for a metric for an experiment
        """
        try:
            exps = self.api.list_experiments_by_prop(self.task, label=job_id)
            return [x.value for x in exps[0].test_events if x.metric == self.metric][0]
            # assuming labels are unique here
        except ApiException as exception:
            raise RuntimeError(json.loads(exception.body)['detail'])

    def select(self, job_ids: List[str]) -> Dict:
        """Select the best job in the batch
        :param job_ids: The list of job IDs
        :return: The result dictionary
        """
        best_label = None
        for job_id in job_ids:
            value = self._get_by_label(job_id)
            if self.cmp(value, self.best_value):
                self.best_value = value
                best_label = job_id

        return self._create_result_dict(best_label)


@export
@register_export_policy('best-of-all')
class BestExportPolicy(ExperimentRepoExportPolicy):
    """Select a model that is the best on this dataset"""

    def __init__(self, api: XpctlApi, task: str, dataset: str, metric: str, user_cmp: str = None, **kwargs) -> None:
        """

        :param api: An XPCTL client api object
        :param task: A string name for the task
        :param dataset: A string key for the dataset
        :param metric: The dataset to evaluate
        :param user_cmp: A comparator function
        :param kwargs:
        """
        assert dataset is not None
        super().__init__(api, task, dataset, metric)
        self.cmp: Callable[[float, float], bool] = None
        self.cmp, self.best_value = get_metric_cmp(self.metric, user_cmp)

    def _get_results(self) -> List[Tuple[str, float]]:
        """
        Return List[(label, value)] for all experiments with this dataset.

        :raises RuntimeError: ApiException indicates we failed to connect to xpctl server.
        :return: Give back a tuple of the label and the score
        """
        try:
            exps = self.api.list_experiments_by_prop(task=self.task, dataset=self.dataset)
            labels_values = []
            for exp in exps:
                labels_values.append((exp.label, [x.value for x in exp.test_events if x.metric == self.metric][0]))
            return labels_values
        except ApiException as exception:
            raise RuntimeError(json.loads(exception.body)['detail'])

    def select(self, job_ids: List[str]) -> Dict:
        """Select the best job in the dataset
        :param job_ids: The list of job IDs
        :return: The result dictionary
        """
        labels_values = self._get_results()
        best_job = None
        for job_id, job_value in labels_values:
            if self.cmp(job_value, self.best_value) and job_id in job_ids:
                self.best_value = job_value
                best_job = job_id
        if best_job is not None:
            return self._create_result_dict(best_job)
        return {}


@export
@register_export_policy('best-of-mead-eval-only')
class BestExportPolicyOutput(ExportPolicy):
    """Select the best model based on mead eval results.

    This is actually more general it selects the best based on
    values in the outputs section of a job db entry.
    """

    def __init__(self, store: Store, metric: str, user_cmp: Optional[str] = None, **kwargs) -> None:
        """
        :param store: The odin job db
        :param metric: The metric used to compare models
        :param user_cmp: A user supplied comparison operator
        :param kwargs: absorb kwargs from other exports
        """
        super().__init__()
        self.store = store
        self.metric = metric
        cmp, self.default_value = get_metric_cmp(self.metric, user_cmp)
        self.reverse = cmp in {gt, ge}
        self.best_value = 0

    def _get_result(self, job_id: str, metric: str) -> float:
        """Get the metric out of the job db entry.

        :param job_id: The job to look up
        :param metric: The metric to look for
        :returns: The metric
        """
        job_entry = self.store.get(job_id)
        return job_entry.get('outputs', {}).get(metric, self.default_value)

    def _create_result_dict(self, job_id: str) -> Dict:
        return {"value": self.best_value, "selected": job_id, "metric": self.metric}

    def select(self, job_ids: List[str]) -> Dict:
        """Select the best job in the dataset
        :param job_ids: The list of job IDs
        :return: The result dictionary
        """
        job = [(j, self._get_result(j, self.metric)) for j in job_ids]
        best_job = sorted(job, key=itemgetter(1), reverse=self.reverse)[0]
        self.best_value = best_job[1]
        return self._create_result_dict(best_job[0])


@export
@register_export_policy('best-of-mead-eval')
class BestExporrPolicyMeadEvalXPCTL(ExperimentRepoExportPolicy):
    """Get the best model sorted by mead eval and then xpctl scores."""

    def __init__(
        self, api: XpctlApi, store: Store, task: str, dataset: str, metric: str, user_cmp: str = None, **kwargs
    ) -> None:
        """Construct a best model in batch

        :param api: An XPCTL client api object
        :param store: The odin jobs db
        :param task: A string name for the task
        :param dataset: A string key for the dataset
        :param metric: The metric to evaluate
        :param user_cmp: A comparator function
        :param kwargs:
        """
        super().__init__(api, task, dataset, metric)
        self.store = store
        self.cmp: Callable[[float, float], bool] = None
        self.cmp, self.default_value = get_metric_cmp(self.metric, user_cmp)
        self.reverse = self.cmp in {gt, ge}

    def _get_xpctl_result(self, job_id: str) -> float:
        """
        Get the value for a metric for an experiment. The experiment is found by the label.

        :param job_id: id for a job
        :raises RuntimeError: ApiException indicates we failed to connect to xpctl server.
        :return: the value for a metric for an experiment
        """
        try:
            exps = self.api.list_experiments_by_prop(self.task, label=job_id)
            return [x.value for x in exps[0].test_events if x.metric == self.metric][0]
            # assuming labels are unique here
        except ApiException as exception:
            raise RuntimeError(json.loads(exception.body)['detail'])

    def _get_results(self, job_id: str, metric: str) -> Tuple[float, float]:
        """Get the mead-eval output for a job and if the output includes
           the label get the xpctl score too.

        :param job_id: The job to look up the results for
        :param metric: The metric to look up.
        :returns: The mead-eval and xpctl scores
        """
        job_entry = self.store.get(job_id)
        outputs = job_entry.get('outputs', {})
        mead_eval = outputs.get(metric, self.default_value)
        label = outputs.get('label')
        xpctl = self._get_xpctl_result(label) if label is not None else self.default_value
        return mead_eval, xpctl

    def select(self, job_ids: List[str]) -> Dict:
        """Select the best job in the dataset
        :param job_ids: The list of job IDs
        :return: The result dictionary
        """
        job = [(j, *self._get_results(j, self.metric)) for j in job_ids]
        # Python has a stable sort so if we sort by xpctl first
        job = sorted(job, key=itemgetter(2), reverse=self.reverse)
        # Then sort by mead-eval
        best_job = sorted(job, key=itemgetter(1), reverse=self.reverse)[0]
        # The result is sorted by mead-eval with ties broken by xpctl
        self.best_value = (best_job[1], best_job[2])
        return self._create_result_dict(best_job[0])


def main():  # pylint: disable=too-many-statements
    """Select a model for export if one meets the criteria
    """
    parser = argparse.ArgumentParser(description='Select a model for export if one meets the criteria')
    parser.add_argument('--cred', help='cred file', default="/etc/odind/odin-cred.yml")
    parser.add_argument('--type', help='Policy type', required=True)
    parser.add_argument(
        '--label', required=True, help="The odin task label for this selecting task, used to access the store"
    )
    parser.add_argument('--models', required=True, nargs='+')
    parser.add_argument('--dataset', help="(deprecated) The name of the dataset to evaluate", required=False)
    parser.add_argument('--task', required=False)
    parser.add_argument('--metric', default='acc')
    parser.add_argument('--user_cmp', default=None)
    parser.add_argument('--config', help='(deprecated) JSON Configuration for an experiment', type=convert_path)
    parser.add_argument(
        '--settings',
        help='JSON Configuration for mead',
        required=False,
        default='config/mead-settings.json',
        type=convert_path,
    )
    parser.add_argument('--datasets', help='(deprecated) json library of dataset labels', type=convert_path)
    parser.add_argument('--logging', help='json file for logging', default='config/logging.json', type=convert_path)
    parser.add_argument('--data_root', help='Data directory', default='/data')
    parser.add_argument('--xpctl_api_url', help='XPCTL api', type=str)

    args = parser.parse_args()

    if args.datasets is not None:
        LOGGER.warning("--datasets is unused and unneeded for calls to `odin-select`")
    if args.config is not None:
        LOGGER.warning("--config is unused and unneeded for calls to `odin-select`")
    if args.dataset is not None:
        LOGGER.warning("--dataset is unused and unneeded for calls to `odin-select`")

    cred_params = read_config_stream(args.cred)

    store = create_store_backend(**cred_params['jobs_db'])
    args.store = store

    xpctl_url = args.xpctl_api_url if args.xpctl_api_url is not None else cred_params['reporting_db']['host']
    args.api = xpctl_client(host=xpctl_url)

    params = vars(args)
    del params['cred']
    policy = create_export_policy(args.type, params)
    results = policy.select(args.models)
    if results:
        print(results)

        job_details = store.get(args.label)
        outputs = job_details.get("outputs", {})
        if outputs is None:
            outputs = {}
            job_details['outputs'] = outputs
        outputs.update(results)
        store.set(job_details)


if __name__ == "__main__":
    main()
