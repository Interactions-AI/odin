"""Defines a resource handler for multi-worker TFJobs"""

from typing import List
from kubernetes import client
from odin.store import Store
from odin.k8s import (
    Task,
    Status,
    ResourceHandler,
    StatusType,
    task_to_pod_spec,
    json_to_selector,
    register_resource_handler,
)


@register_resource_handler
class TFJobHandler(ResourceHandler):
    """Resource handler for multi-worker PyTorchJobs"""

    NAME = "TFJob"
    GROUP = "kubeflow.org"
    PLURAL = "tfjobs"
    VERSION = "v1"
    ALIAS = ('tfjob', 'tensorflowjob')
    # This label selector was changed on Mar 7, 2019. We are using the old format
    # https://github.com/kubeflow/tf-operator/pull/951
    SELECTOR = "tf-job-name"
    GROUP_KEY = "group-name"

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return TFJobHandler.NAME

    def __init__(self, namespace):
        super().__init__(namespace)
        self.api = client.CustomObjectsApi()

    def get_api(self) -> object:
        """Get the API for this resource type

        :return An API object
        :rtype object
        """
        return self.api

    def get_pods(self, name: str) -> List[client.models.v1_pod.V1Pod]:
        """Find all the pods contained in a tf job.

        :param name: The name of job (the jobs db resource id)
        :type name: str
        :returns: The pods in the job
        :rtype: List[client.models.v1_pod.V1Pod]
        """
        try:
            selector = json_to_selector({TFJobHandler.SELECTOR: name, TFJobHandler.GROUP_KEY: TFJobHandler.GROUP})
            return self.core_api.list_namespaced_pod(self.namespace, label_selector=selector).items
        except client.rest.ApiException:
            return []

    def submit(self, task: Task) -> str:
        """Submit a multi-worker TF Task

        :param task: A task definition to run
        :type task: Task
        :return: A task identifier
        :rtype: str
        """
        secrets = self._reference_secrets(task)
        configmaps = self._generate_configmaps(task)
        pod_spec = task_to_pod_spec(task, container_name="tensorflow", secrets=secrets, configmaps=configmaps)
        template_metadata = client.V1ObjectMeta(name=task.name)

        template = client.V1PodTemplateSpec(metadata=template_metadata, spec=pod_spec)

        worker_replica_spec = {}
        worker_replica_spec['replicas'] = task.num_workers
        worker_replica_spec['restartPolicy'] = TFJobHandler.RESTART_NEVER
        worker_replica_spec['template'] = template

        spec = {}
        spec['tfReplicaSpecs'] = {}
        spec['tfReplicaSpecs']['Worker'] = worker_replica_spec

        tf_job_spec = {}
        tf_job_spec['kind'] = 'TFJob'
        tf_job_spec['apiVersion'] = 'kubeflow.org/' + TFJobHandler.VERSION
        tf_job_spec['metadata'] = client.V1ObjectMeta(generate_name=task.name)
        tf_job_spec['spec'] = spec

        tf_job = self.api.create_namespaced_custom_object(
            TFJobHandler.GROUP, TFJobHandler.VERSION, self.namespace, TFJobHandler.PLURAL, tf_job_spec
        )
        return tf_job['metadata']['name']

    def status(self, name: str, store: Store) -> Status:
        """tf-operator seems to have no way to support querying status, instead, find out its pods' status

        :param name: The task name
        :type name: Task
        :param store: The job store
        :type store: Store
        :return: A status
        :rtype: Status
        """

        resource_id = store.get(name)[Store.RESOURCE_ID]
        statuses = [p.status for p in self.get_pods(resource_id)]

        # The idea here is that every single tfjob pod has to be done
        if not all([s.phase in TFJobHandler.TERMINAL_PHASES for s in statuses]):
            return Status(StatusType.RUNNING, None)

        status = statuses[0]
        return status

    def kill(self, name, store: Store) -> None:
        """Kill a TFJob

        :param name: The job name
        :type name: str
        :param store: The job store
        :type store: Store
        :return: None
        """
        delete_options = client.V1DeleteOptions(api_version=TFJobHandler.VERSION, propagation_policy="Background")
        resource_id = store.get(name)[Store.RESOURCE_ID]
        return self.api.delete_namespaced_custom_object(
            TFJobHandler.GROUP,
            TFJobHandler.VERSION,
            self.namespace,
            TFJobHandler.PLURAL,
            resource_id,
            body=delete_options,
        )
