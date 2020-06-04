"""Defines a resource handler for multi-worker PyTorchJobs"""

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


@register_resource_handler(aliases=['pytjob'])
class PyTorchJobHandler(ResourceHandler):
    """Resource handler for multi-worker PyTorchJobs"""

    NAME = "PyTorchJob"
    GROUP = "kubeflow.org"
    PLURAL = "pytorchjobs"
    VERSION = "v1"
    # This label selector was changed, we are using the new format
    SELECTOR = "pytorch-job-name"
    GROUP_KEY = "group-name"

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return PyTorchJobHandler.NAME

    def __init__(self, namespace: str):
        """Create a resource handler with resources in the given namespace

        :param namespace: A namespace for resources
        :type namespace: str
        """
        super().__init__(namespace)
        self.api = client.CustomObjectsApi()

    def get_api(self) -> object:
        """Get the API for this resource handler

        :return: An API for this handler
        :rtype: object
        """
        return self.api

    def submit(self, task: Task) -> str:
        """Submit a multi-worker PyTorchJob Task

        :param task: The task definition
        :type task: Task
        :return: A string handle name
        :rtype: str
        """
        secrets = self._reference_secrets(task)
        configmaps = self._generate_configmaps(task)
        pod_spec = task_to_pod_spec(task, container_name="pytorch", secrets=secrets, configmaps=configmaps)
        template_metadata = client.V1ObjectMeta(name=task.name)

        template = client.V1PodTemplateSpec(metadata=template_metadata, spec=pod_spec)

        worker_replica_spec = {}
        worker_replica_spec['replicas'] = task.num_workers
        worker_replica_spec['restartPolicy'] = PyTorchJobHandler.RESTART_NEVER
        worker_replica_spec['template'] = template

        master_replica_spec = {}
        master_replica_spec['replicas'] = 1
        master_replica_spec['restartPolicy'] = PyTorchJobHandler.RESTART_NEVER
        master_replica_spec['template'] = template

        spec = {}
        spec['pytorchReplicaSpecs'] = {}
        spec['pytorchReplicaSpecs']['Master'] = master_replica_spec
        spec['pytorchReplicaSpecs']['Worker'] = worker_replica_spec

        pytorch_job_spec = {}
        pytorch_job_spec['kind'] = "PyTorchJob"
        pytorch_job_spec['apiVersion'] = 'kubeflow.org/' + PyTorchJobHandler.VERSION
        pytorch_job_spec['metadata'] = client.V1ObjectMeta(generate_name=task.name)
        pytorch_job_spec['spec'] = spec

        pytorch_job = self.api.create_namespaced_custom_object(
            PyTorchJobHandler.GROUP,
            PyTorchJobHandler.VERSION,
            self.namespace,
            PyTorchJobHandler.PLURAL,
            pytorch_job_spec,
        )
        return pytorch_job['metadata']['name']

    def get_pods(self, name: str) -> List[client.models.v1_pod.V1Pod]:
        """Find all the pods contained in a pytorch job.

        :param name: The name of job (the jobs db resource id)
        :type name: str
        :returns: The pods in the job
        :rtype: List[client.models.v1_pod.V1Pod]
        """
        try:
            selector = json_to_selector(
                {PyTorchJobHandler.SELECTOR: name, PyTorchJobHandler.GROUP_KEY: PyTorchJobHandler.GROUP}
            )
            return self.core_api.list_namespaced_pod(self.namespace, label_selector=selector).items
        except client.rest.ApiException:
            return []

    def status(self, name: str, store: Store) -> Status:
        """Find out its pods' status

        :param name: A task name
        :type name: str
        :param store: A job store
        :type store: Store
        :return: A job status
        :rtype: Status
        """

        resource_id = store.get(name)[Store.RESOURCE_ID]
        statuses = [p.status for p in self.get_pods(resource_id)]

        # The idea here is that every single pod has to be done
        if not all([s.phase in PyTorchJobHandler.TERMINAL_PHASES for s in statuses]):
            return Status(StatusType.RUNNING, None)

        status = statuses[0]
        return status

    def kill(self, name: str, store: Store) -> None:
        """Kill a multi-worker PyTorch task with given name

        :param name: The task to kill
        :type name: str
        :param store: The jobs store
        :type store: Store
        :return: None
        """
        delete_options = client.V1DeleteOptions(api_version=PyTorchJobHandler.VERSION, propagation_policy="Background")
        resource_id = store.get(name)[Store.RESOURCE_ID]
        return self.api.delete_namespaced_custom_object(
            PyTorchJobHandler.GROUP,
            PyTorchJobHandler.VERSION,
            self.namespace,
            PyTorchJobHandler.PLURAL,
            resource_id,
            body=delete_options,
        )
