"""Defines a resource handler for Jobs"""

from kubernetes import client
from odin.store import Store
from odin.k8s import ResourceHandler, Task, Status, task_to_pod_spec, register_resource_handler


@register_resource_handler
class JobHandler(ResourceHandler):

    """resource handler for jobs"""

    NAME = "Job"

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return JobHandler.NAME

    def __init__(self, namespace: str):
        """Create a k8s Job handle with given namespace

        :param namespace: A namespace
        :type namespace: str
        """
        super().__init__(namespace)
        self.api = client.BatchV1Api()

    def get_api(self) -> object:
        """Get back the API for Jobs (BatchV1)

        :return: An API object
        :rtype: object
        """
        return self.api

    def submit(self, task: Task):
        """Submit a new task as a Job

        :param task: A task definition
        :type task: Task
        :return: A string identifier for this task
        :rtype: str
        """
        secrets = self._reference_secrets(task)
        configmaps = self._generate_configmaps(task)
        pod_spec = task_to_pod_spec(task, secrets=secrets, configmaps=configmaps)
        metadata = client.V1ObjectMeta(name=task.name)
        template_metadata = client.V1ObjectMeta(name='{}-template'.format(task.name))

        template = client.V1PodTemplateSpec(metadata=template_metadata, spec=pod_spec)

        task_spec = client.V1JobSpec(template=template)
        task_obj = client.V1Job(kind=JobHandler.NAME, spec=task_spec, metadata=metadata)

        self.api.create_namespaced_job(body=task_obj, namespace=self.namespace)
        return task.name

    def status(self, name: str, store: Store) -> Status:
        """Get back a status for this task

        :param name: The task name
        :type name: str
        :param store: The jobs store
        :type store: Store
        :return: A status for this task
        :rtype: Status
        """

        job_status = self.api.read_namespaced_job_status(name=name, namespace=self.namespace).status
        return job_status

    def kill(self, name, store: Store) -> None:
        """Kill a Job task with background cascaded delete on the pods

        https://github.com/kubernetes/kubernetes/issues/20902

        :param name: A job identifier
        :type name: str
        :param store: A job store
        :type store: Store
        :return: None
        """
        delete_options = client.V1DeleteOptions(api_version="batch/v1", propagation_policy="Background")
        return self.api.delete_namespaced_job(name=name, namespace=self.namespace, body=delete_options)

    def get_pods(self, name: str):
        """Get Job objects for this name

        Should we change to pods? We arent really using Jobs much RN

        :param name: A job identifier
        :type name: str
        :return: A list of jobs
        :rtype: List
        """
        try:
            results = self.api.read_namespaced_job(name, namespace=self.namespace)
            return [results]
        except Exception:
            return []
