"""Define (partial) resource handler for k8s Deployments"""

from typing import List
from kubernetes import client
from odin.k8s import ResourceHandler, register_resource_handler


@register_resource_handler(aliases=['deploy'])
class DeploymentHandler(ResourceHandler):

    """(partial) resource handler for k8s Deployments"""

    NAME = "DEPLOYMENT"

    @property
    def kind(self) -> str:
        """Give back the k8s "kind"

        :return: kind
        :rtype: str
        """
        return DeploymentHandler.NAME

    def __init__(self, namespace: str):
        """Initialize from given namespace

        :param namespace: A given namespace
        :type namespace: str
        """

        super().__init__(namespace)
        self.api = client.AppsV1Api()

    def get_pods(self, name: str) -> List[str]:
        """Get the list of pods that are managed by a service.

        :param name: The name of the service you want the pods from.
        :returns: The pod names
        """

        try:
            scale = self.api.read_namespaced_deployment_scale(name, self.namespace)
            selectors = scale.status.selector
            return self.core_api.list_namespaced_pod(self.namespace, label_selector=selectors).items
        except client.rest.ApiException:
            return []

    def get_api(self):
        """Get the deployment API
        :return The deployment API
        """
        return self.api
