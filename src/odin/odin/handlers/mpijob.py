"""Define a resource handler for multi-worker MPI jobs"""
from typing import List
from kubernetes import client
from odin.store import Store
from odin.k8s import Task, Status, ResourceHandler, StatusType, json_to_selector, register_resource_handler


@register_resource_handler
class MPIJobHandler(ResourceHandler):

    """Resource handler for multi-worker MPI jobs
    """

    NAME = "MPIJob"
    GROUP = "kubeflow.org"
    PLURAL = "mpijobs"
    VERSION = "v1alpha1"
    SELECTOR = "mpi_job_name"
    ROLE_SELECTOR = "mpi_role_type"
    ROLE_TYPE = "launcher"

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return MPIJobHandler.NAME

    def __init__(self, namespace):
        super().__init__(namespace)
        self.api = client.CustomObjectsApi()

    def get_api(self) -> object:
        """Get API for the resource

        :return: An API
        :rtype: object
        """
        return self.api

    def submit(self, task: Task) -> str:

        """Submit an mpi job

        :param task: The Task to launch.
        :type task: Task
        :returns: The name of the job.
        :rtype: str
        """
        secrets = self._reference_secrets(task)
        configmaps = self._generate_configmaps(task)
        pod_spec = task.to_pod_spec(task, container_name="mpi", secrets=secrets, configmaps=configmaps)
        template_metadata = client.V1ObjectMeta(name=task.name)
        template = client.V1PodTemplateSpec(metadata=template_metadata, spec=pod_spec)

        spec = {}
        spec['replicas'] = task.num_workers
        spec['restartPolicy'] = MPIJobHandler.RESTART_NEVER
        spec['template'] = template

        mpi_job_spec = {}
        mpi_job_spec['kind'] = 'MPIJob'
        mpi_job_spec['apiVersion'] = 'kubeflow.org/' + MPIJobHandler.VERSION
        mpi_job_spec['metadata'] = client.V1ObjectMeta(generate_name=task.name)
        mpi_job_spec['spec'] = spec

        mpi_job = self.api.create_namespaced_custom_object(
            MPIJobHandler.GROUP, MPIJobHandler.VERSION, self.namespace, MPIJobHandler.PLURAL, mpi_job_spec
        )
        return mpi_job['metadata']['name']

    def get_pods(self, name: str) -> List[client.models.v1_pod.V1Pod]:
        """Find all the pods contained in a tf job.

        :param name: The name of job (the jobs db resource id)
        :type name: str
        :returns: The pods in the job
        :rtype: List[client.models.v1_pod.V1Pod]
        """
        try:
            selector = json_to_selector(
                {MPIJobHandler.SELECTOR: name, MPIJobHandler.ROLE_SELECTOR: MPIJobHandler.ROLE_TYPE}
            )
            return self.core_api.list_namespaced_pod(self.namespace, label_selector=selector).items
        except client.rest.ApiException:
            return []

    def status(self, name: str, store: Store) -> Status:
        """mpi-operator seems to have no way to support querying status, instead, find out its pods' status

        :param name: The job name
        :type name: str
        :param store: The job store
        :type store: Store
        :return: A status
        :rtype: Status
        """

        resource_id = store.get(name)[Store.RESOURCE_ID]
        statuses = [p.status for p in self.get_pods(resource_id)]
        if len(statuses) != 1:
            return Status(StatusType.RUNNING, "Unknown status")
            # raise Exception("No such job found: {}".format(name))

        status = statuses[0]
        return status

    def kill(self, name: str, store: Store) -> None:
        """Kill an MPIJob

        :param name: A name
        :type name: str
        :param store: The job store
        :type store: Store
        """
        delete_options = client.V1DeleteOptions(api_version=MPIJobHandler.VERSION, propagation_policy="Background")
        resource_id = store.get(name)[Store.RESOURCE_ID]
        self.api.delete_namespaced_custom_object(
            MPIJobHandler.GROUP,
            MPIJobHandler.VERSION,
            self.namespace,
            MPIJobHandler.PLURAL,
            resource_id,
            body=delete_options,
        )
