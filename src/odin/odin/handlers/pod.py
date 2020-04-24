"""Defines a resource handler for Pods"""

from typing import List
from kubernetes import client
from odin.store import Store
from odin.k8s import Task, Status, ResourceHandler, task_to_pod_spec, register_resource_handler


@register_resource_handler
class PodHandler(ResourceHandler):
    """A resource handler for Pods"""

    NAME = 'Pod'

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return PodHandler.NAME

    def submit(self, task: Task) -> str:
        """Submit a pod to run

        :param task: A task/pod
        :type task: Task
        :return: A string name
        :rtype str
        """
        secrets = self._reference_secrets(task)
        configmaps = self._generate_configmaps(task)
        pod_spec = task_to_pod_spec(task, secrets=secrets, configmaps=configmaps)
        metadata = client.V1ObjectMeta(name=task.name)

        pod = client.V1Pod(metadata=metadata, spec=pod_spec)
        self.core_api.create_namespaced_pod(body=pod, namespace=self.namespace)
        return task.name

    def get_api(self) -> object:
        """Get the (core) API for this resource handler

        :return: The core API
        :rtype: object
        """
        return self.core_api

    def get_pods(self, name: str) -> List[client.models.v1_pod.V1Pod]:
        """Get all pods for this Task

        :param: name A name
        :type: str
        :return: All pods
        :rtype: List[client.models.v1_pod.V1Pod]
        """
        results = self.core_api.read_namespaced_pod(name, self.namespace)

        return [results] if results else []

    def status(self, name: str, store: Store) -> Status:
        """Get status for this pod

        :param name: The name
        :type name: str
        :param store: The job store
        :type store: Store
        :return: A status
        :rtype: Status
        """
        pod_status = self.core_api.read_namespaced_pod_status(name=name, namespace=self.namespace).status
        return pod_status

    def kill(self, name: str, store: Store) -> None:
        """Kill a pod

        :param name: pod name
        :type name: str
        :param store: A store
        :type store: Store
        """
        self.core_api.delete_namespaced_pod(name=name, namespace=self.namespace)
