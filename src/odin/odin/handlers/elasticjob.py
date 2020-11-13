"""Defines a resource handler for multi-worker PyTorch ElasticJobs"""

from typing import List
from kubernetes import client
from os import getenv
from odin import LOGGER
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


@register_resource_handler(aliases=['pytorchelastic'])
class PyTorchElasticJobHandler(ResourceHandler):
    """Resource handler for multi-worker PyTorch ElasticJobs"""

    NAME = "ElasticJob"
    GROUP = "elastic.pytorch.org"
    PLURAL = "elasticjobs"
    VERSION = "v1alpha1"
    # This label selector was changed, we are using the new format
    SELECTOR = "job-name"
    GROUP_KEY = "group-name"
    EXIT_CODE = "ExitCode"
    ETCD_PORT = 2379

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return PyTorchElasticJobHandler.NAME

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
        pod_spec = task_to_pod_spec(task, container_name="pytorch-elasticjob", secrets=secrets, configmaps=configmaps)
        template_metadata = client.V1ObjectMeta(name=task.name)

        template = client.V1PodTemplateSpec(metadata=template_metadata, spec=pod_spec)

        worker_replica_spec = {}
        worker_replica_spec['replicas'] = task.num_workers
        worker_replica_spec['restartPolicy'] = PyTorchElasticJobHandler.EXIT_CODE
        worker_replica_spec['template'] = template

        spec = {}
        spec['replicaSpecs'] = {}
        spec['replicaSpecs']['Worker'] = worker_replica_spec
        spec['minReplicas'] = task.num_workers
        spec['maxReplicas'] = task.num_workers
        etcd_svc = getenv('PYTORCH_ELASTIC_ETCD_SVC')
        if not etcd_svc:
            LOGGER.warning("No environment variable set for etcd service, looking for first available in elastic-job namespace")
            api = client.CoreV1Api()
            etcd_svc = [x for x in api.list_namespaced_service('elastic-job').items if x.metadata.name =='etcd-service'][0].spec.cluster_ip
        LOGGER.info("Using etcd service on %s:%d", etcd_svc, PyTorchElasticJobHandler.ETCD_PORT)
        spec['rdzvEndpoint'] = f'{etcd_svc}:{PyTorchElasticJobHandler.ETCD_PORT}'
        pytorch_job_spec = {}
        pytorch_job_spec['kind'] = PyTorchElasticJobHandler.NAME
        pytorch_job_spec['apiVersion'] = f'{PyTorchElasticJobHandler.GROUP}/{PyTorchElasticJobHandler.VERSION}'
        pytorch_job_spec['metadata'] = client.V1ObjectMeta(generate_name=task.name)
        pytorch_job_spec['spec'] = spec

        pytorch_job = self.api.create_namespaced_custom_object(
            PyTorchElasticJobHandler.GROUP,
            PyTorchElasticJobHandler.VERSION,
            self.namespace,
            PyTorchElasticJobHandler.PLURAL,
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
                {PyTorchElasticJobHandler.GROUP_KEY: PyTorchElasticJobHandler.GROUP}
            )

            pods = [x for x in self.core_api.list_namespaced_pod(self.namespace, label_selector=selector).items if x.metadata.name.startswith(name)]
            return pods
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
        if not all([s.phase in PyTorchElasticJobHandler.TERMINAL_PHASES for s in statuses]):
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
        delete_options = client.V1DeleteOptions(api_version=PyTorchElasticJobHandler.VERSION, propagation_policy="Background")
        resource_id = store.get(name)[Store.RESOURCE_ID]
        return self.api.delete_namespaced_custom_object(
            PyTorchElasticJobHandler.GROUP,
            PyTorchElasticJobHandler.VERSION,
            self.namespace,
            PyTorchElasticJobHandler.PLURAL,
            resource_id,
            body=delete_options,
        )
