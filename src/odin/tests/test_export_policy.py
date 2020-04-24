import json
from typing import Callable, List, Dict
import random
import string
from unittest.mock import MagicMock

from baseline.utils import get_metric_cmp
from odin.model.selector import ExperimentRepoExportPolicy, BestOfBatchExportPolicy, BestExportPolicy
from odin.store import MemoryStore, Store
from xpctl.xpclient.models import Experiment, Result
from xpctl.xpclient import Configuration
from xpctl.xpclient.api import XpctlApi
from xpctl.xpclient import ApiClient
from xpctl.xpclient.rest import ApiException
import urllib3
import warnings


class ExportPolicyTest(ExperimentRepoExportPolicy):
    def __init__(self, user_cmp: str = None) -> None:
        xpctl = MagicMock()
        dataset = 'test'

        def build_mock(dataset):
            def _build(_):
                m = MagicMock()
                m.summary = {dataset: dataset}
                return m

            return _build

        xpctl.task_summary.side_effect = build_mock(dataset)
        super().__init__(xpctl, "test", dataset, "f1")
        self.comparator: Callable[[float, float], bool] = None
        self.comparator, self.best_value = get_metric_cmp(self.metric, user_cmp)

    def _get_experiment(self, label: str) -> float:
        return float(label)

    def select(self, job_ids: List[str], store: Store) -> Dict:
        best_label = None
        for job_id in job_ids:
            prev = store.get(job_id)
            label = prev["label"]
            value = self._get_experiment(label)
            if self.comparator(value, self.best_value):
                self.best_value = value
                best_label = label

        return self._create_result_dict(best_label)


def test_simple_export():
    jobs = MemoryStore()
    jobs.set({Store.PIPE_ID: "1", Store.PARENT: "A"})
    jobs.set({Store.PIPE_ID: "2", Store.PARENT: "A"})
    jobs.set({Store.PIPE_ID: "3", Store.PARENT: "A"})
    jobs.set({Store.PIPE_ID: "4", Store.PARENT: "B"})
    jobs.set({Store.PIPE_ID: "me", Store.PARENT: "A"})
    jobs.set({Store.PIPE_ID: "A", Store.EXECUTED: ["1", "2", "3"]})
    policy = ExportPolicyTest(">")
    output = policy.select(["1", "2", "3"], jobs)
    assert output["value"] == 3.0
    assert output["selected"] == "3"

    policy = ExportPolicyTest("<")
    output = policy.select(["1", "2", "3"], jobs)
    assert output["value"] == 1.0
    assert output["selected"] == "1"


def build_xpctl_data():
    num_chars = 8
    num_exps = 5
    job_ids = []
    experiments = []
    datasets = ['test1', 'test2']
    task = 'test_odin_export_policy'
    for index in range(num_exps):
        job_ids.append(''.join(random.choices(string.ascii_uppercase + string.digits, k=num_chars)))
    metrics = ['f1', 'acc']
    for index, val in enumerate(range(50, 100, 10)):
        experiments.append(
            Experiment(
                task='test_odin_export_policy',
                label=job_ids[index],
                test_events=[
                    Result(metric=metrics[0], value=val, tick_type='EPOCH', tick=0, phase='Test'),
                    Result(metric=metrics[1], value=val, tick_type='EPOCH', tick=0, phase='Test'),
                ],
                train_events=[],
                valid_events=[],
            )
        )
    experiments[0].config = f'{{"test":"test", "dataset": "{datasets[0]}"}}'
    experiments[1].config = f'{{"test":"test", "dataset": "{datasets[0]}"}}'
    experiments[2].config = f'{{"test":"test", "dataset": "{datasets[0]}"}}'
    experiments[3].config = f'{{"test":"test", "dataset": "{datasets[1]}"}}'
    experiments[4].config = f'{{"test":"test", "dataset": "{datasets[1]}"}}'
    experiments[0].dataset = datasets[0]
    experiments[1].dataset = datasets[0]
    experiments[2].dataset = datasets[0]
    experiments[3].dataset = datasets[1]
    experiments[4].dataset = datasets[1]
    # for best of batch export policy we should export the fifth one.
    # for best of dataset export policy, in the first case we should export the third one, in the second case the fifth
    # one
    return job_ids, experiments


def test_best_of_batch_export():
    job_ids, exps = build_xpctl_data()
    task = 'test_odin-export_policy'

    api = MagicMock()

    def find(task, label):
        return [exp for exp in exps if exp.label == label]

    api.list_experiments_by_prop.side_effect = find

    b = BestOfBatchExportPolicy(api=api, task=task, dataset=None, metric='f1')
    result = b.select(job_ids=job_ids)
    assert result['selected'] == job_ids[4]


def test_best_export():
    job_ids, exps = build_xpctl_data()
    task = 'test_odin-export_policy'
    dataset = 'test1'

    api = MagicMock()

    def find(task, dataset):
        return [exp for exp in exps if exp.dataset == dataset]

    def build_mock(_):
        m = MagicMock()
        m.summary = {dataset: dataset}
        return m

    api.list_experiments_by_prop.side_effect = find
    api.task_summary.side_effect = build_mock

    b = BestExportPolicy(api=api, task=task, dataset=dataset, metric='f1')
    result = b.select(job_ids=job_ids)
    assert result['selected'] == job_ids[2]


def test_best_export_multiple_datasets():
    job_ids, exps = build_xpctl_data()
    task = 'test_odin-export_policy'
    dataset1 = 'test1'
    dataset2 = 'test2'

    api1 = MagicMock()
    api2 = MagicMock()

    def find(task, dataset):
        return [exp for exp in exps if exp.dataset == dataset]

    def build_mock(dataset):
        def _build(_):
            m = MagicMock()
            m.summary = {dataset: dataset}
            return m

        return _build

    api1.list_experiments_by_prop.side_effect = find
    api1.task_summary.side_effect = build_mock(dataset1)

    api2.list_experiments_by_prop.side_effect = find
    api2.task_summary.side_effect = build_mock(dataset2)

    b2 = BestExportPolicy(api=api1, task=task, dataset=dataset1, metric='f1')
    result = b2.select(job_ids=job_ids)
    assert result['selected'] == job_ids[2]
    b2 = BestExportPolicy(api=api2, task=task, dataset=dataset2, metric='f1')
    result = b2.select(job_ids=job_ids)
    assert result['selected'] == job_ids[4]
