"""Defines (partial) resource handler for k8s Services"""

from typing import List
from kubernetes import client
from odin.k8s import ResourceHandler, json_to_selector, register_resource_handler


@register_resource_handler(aliases=['svc'])
class ServiceHandler(ResourceHandler):
    """(partial) resource handler for k8s Services
    """

    NAME = "Service"

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return ServiceHandler.NAME

    def get_api(self) -> object:
        """Get the service API

        :return: Service API
        :rtype object
        """
        return self.core_api

    def get_pods(self, name: str) -> List[client.models.v1_pod.V1Pod]:
        """Get the list of pods that are managed by a service.

        :param name: The name of the service you want the pods from.
        :type name: str
        :returns: The pods
        :rtype: List[client.models.v1_pod.V1Pod]
        """
        try:
            service = self.core_api.read_namespaced_service(name, self.namespace)
            selectors = service.spec.selector
            selectors = json_to_selector(selectors)
            return self.core_api.list_namespaced_pod(self.namespace, label_selector=selectors).items
        except client.rest.ApiException:
            return []
