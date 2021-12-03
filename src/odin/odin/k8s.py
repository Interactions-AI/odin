"""Provide low-level primitives for scheduling Pods"""
# pylint: disable=too-many-lines

import os
import re
import json
from collections import namedtuple
from enum import Enum
from copy import deepcopy
from base64 import b64decode
from itertools import chain
from typing import Dict, List, Union, Optional, Any, AsyncIterator, Type, Tuple
import asyncio
from kubernetes import client, config
import requests_async as arequests
from eight_mile.utils import listify
from baseline.utils import optional_params, import_user_module
from odin import LOGGER
from odin.store import Store


ConfigMap = namedtuple('ConfigMap', 'path name sub_path')

HASH_TRAILING = '-hash'
CORE_MODULES = ['odin.handlers.job', 'odin.handlers.deployment', 'odin.handlers.service', 'odin.handlers.pod']
KF_MODULES = [
    'odin.handlers.mpijob',
    'odin.handlers.tfjob',
    'odin.handlers.pytorchjob',
]
ELASTIC_MODULES = [
    'odin.handlers.elasticjob',
]
DEFAULT_MODULES = CORE_MODULES + KF_MODULES
REGISTRY = 'registry'

Event = namedtuple("Event", "type reason source message timestamp")

Handle = Union[str, 'Job']
Volume = namedtuple('Volume', 'path name claim')
Status = namedtuple('Status', 'status_type message')
Secret = namedtuple('Secret', 'path name sub_path mode')
Cpu = namedtuple('Cpu', 'limits requests')
SecurityContext = namedtuple('SecurityContext', 'fs_group run_as_group run_as_user')
# Because not python3.7, These defaults are for the rightmost argument of Secret
DEFAULT_MODE = 0o644

SECRET_LOC = "/etc/odind/"
ODIN_CRED = "odin-cred"
ODIN_CRED_FILE = "odin-cred.yml"
SSH_KEY = "ssh-key"
SSH_KEY_FILE = "identity"
SSH_MODE = 0o400

ODIN_TASK_ENV = "ODIN_TASK_ID"
ODIN_CRED_ENV = "ODIN_CRED"


Secret.__new__.__defaults__ = ("", DEFAULT_MODE)


def populate_secret(secret_values: Dict) -> Secret:
    """Fill in default values of well known secrets.

    :param secret_values: The secrets asked for in the yaml.
    :returns: The secret values populated with defaults if they were missing.
    """
    if secret_values['name'] == ODIN_CRED:
        secret_values['path'] = secret_values.get('path', os.path.join(SECRET_LOC, ODIN_CRED_FILE))
        secret_values['sub_path'] = secret_values.get('sub_path', ODIN_CRED_FILE)
    if secret_values['name'] == SSH_KEY:
        secret_values['path'] = secret_values.get('path', os.path.join(SECRET_LOC, SSH_KEY_FILE))
        secret_values['sub_path'] = secret_values.get('sub_path', SSH_KEY_FILE)
        secret_values['mode'] = secret_values.get('mode', SSH_MODE)
    return Secret(**secret_values)


def populate_config_map(config_map_values: Dict) -> ConfigMap:
    """Populate a config map from a dictionary

    :param config_map_values: A dictionary of values
    :return: A config map
    """
    return ConfigMap(**config_map_values)


class Task:
    """An object that contains enough info to run in k8s
    """

    def __init__(
        self,
        name: str = None,
        image: str = None,
        command: Union[str, List[str]] = None,
        args: List[str] = None,
        mounts: Optional[List[Volume]] = None,
        secrets: Optional[List[Secret]] = None,
        config_maps: Optional[List[ConfigMap]] = None,
        cpu: Optional[Cpu] = None,
        num_gpus: int = None,
        security_context: Optional[SecurityContext] = None,
        pull_policy: str = 'IfNotPresent',
        node_selector: Optional[Dict[str, str]] = None,
        resource_type: str = "Pod",
        num_workers: int = 1,
        inputs: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
    ):
        """Constructor

        :param name: The name of this task
        :param image: The image to pull from the registry
        :param command: The command to execute from the container
        :param args: The arguments to supply the command
        :param mounts: Optional `Volume`s to mount
        :param secrets: Optional `Secret`s to mount
        :param config_maps: Optional `CongfigMap`s to mount
        :param cpu: Optional cpu resource limits and requests
        :param num_gpus: The number of GPUs requested for this task
        :param pull_policy: pull policy, defaults to `IfNotPresent`
        :param node_selector: This is a list of labels that can be used to select a specific node
        :param resource_type: The resource type (defaults to "Pod")
        :param num_workers: If this is a distributed job (e.g TFJob), how many workers
        :param inputs: Data artifacts that this job consumes.
        :param outputs: The data artifacts that this job will generate.
        """
        self.name = name
        self.image = image
        self.command = command
        self.args = args
        self.mounts = mounts
        self.secrets = secrets
        self.config_maps = config_maps
        self.cpu = cpu
        self.num_gpus = num_gpus
        self.security_context = security_context
        self.pull_policy = pull_policy
        self.node_selector = node_selector
        self.resource_type = resource_type
        self.num_workers = num_workers
        self.inputs = inputs
        self.outputs = outputs

    @classmethod
    def from_dict(cls, dict_value: Dict) -> 'Job':
        """Create a `Job` from some dict read from JSON/YAML

        :param dict_value: a Dictionary
        :returns: A job instance based on data inside the dictionary.
        """
        mounts = dict_value.get('mount', dict_value.get('mounts'))
        mounts = [Volume(m['path'], m['name'], m['claim']) for m in listify(mounts)] if mounts is not None else None
        cpu_req = dict_value.get('cpu')
        cpu_req = Cpu(cpu_req.get('limits'),
                cpu_req.get('requests')) if cpu_req is not None else None
        security_context = dict_value.get('security_context')
        security_context = SecurityContext(
                security_context.get('fs_group'),
                security_context.get('run_as_group'),
                security_context.get('run_as_user')) if security_context is not None else None
        secrets = dict_value.get('secret', dict_value.get('secrets'))
        secrets = [populate_secret(s) for s in listify(secrets)] if secrets is not None else None
        config_maps = dict_value.get('config_map', dict_value.get('config_maps'))
        config_maps = [populate_config_map(cm) for cm in listify(config_maps)] if config_maps is not None else None

        return Task(
            dict_value['name'],
            dict_value['image'],
            dict_value['command'],
            dict_value.get('args', []),
            mounts,
            secrets,
            config_maps,
            cpu_req,
            dict_value.get('num_gpus', 0),
            security_context,
            dict_value.get('pull_policy', 'IfNotPresent'),
            dict_value.get('node_selector'),
            dict_value.get('resource_type', "Pod"),
            dict_value.get('num_workers', 1),
            dict_value.get('inputs'),
            dict_value.get('outputs'),
        )


class SubmitError(ValueError):
    """A custom error to raise when a Task can't be scheduled."""


class TaskManager:
    """Base interface for managing tasks
    """

    def __init__(self):
        """Base init for a scheduler
        """

    def submit(self, task: Task, **kwargs) -> str:
        """Submit something to k8s

        :param task: A `Task` to submit
        :param kwargs:
        :raises SubmitError: When the task can't be scheduled
        :return: This returns a unique `resource_id` within the cluster
        """

    def status(self, handle: Handle) -> Status:
        """Get progress

        :param handle: job id string or Job object
        """

    def kill(self, handle: Handle) -> Dict:
        """Kill a resource

        :param handle: job id string or Job object
        """

    async def wait_for(self, task: Task) -> None:
        """Wait for something to complete (async)

        :param task: The `Task` to wait for
        :param phases: A list of terminal phases
        :return: Nothing
        """

    def results(self, handle: Handle) -> Dict:
        """Get results from job store

        :param handle: A string id or Job
        :return: Job results dict
        """

    def get_resource_type(self, handle: Handle) -> str:
        """What type of resource is associated with this job

        :param handle: The string name of the job or a `Job` itself
        :return: A ResourceType
        """

    def find_resource_names(self, task: str) -> List[str]:
        """What are the resources associated with this task"""


class ResourceHandler:
    """Handler for a resource type
    """

    PHASE_SUCCEEDED = 'Succeeded'
    PHASE_RUNNING = 'Running'
    TERMINAL_PHASES = ['Terminated', PHASE_SUCCEEDED, 'Error', 'Failed', 'ErrImagePull']
    RESTART_NEVER = "Never"
    RESTART_ON_FAILURE = "OnFailure"

    def __init__(self, namespace: str):
        """Create a resource handler

        :param namespace: The given namespace
        :type namespace: str
        """
        self.core_api = client.CoreV1Api()
        self.namespace = namespace

    @property
    def kind(self) -> str:
        """Give back the kind.  Base throws

        :raise Exception
        """
        raise Exception("Not implemented!")

    def _reference_secrets(self, task: Task) -> Optional[List[Secret]]:
        """Generate secrets based on the requirements of the job.

        Eventually we can support custom secrets by having the job create
        secrets from the yaml config. Then this function will combine secrets
        on the job with these injected secrets to yield the final full list.

        :param task: The job we are running to add secrets to.
        :type task: Task
        :returns: A list of Secrets or `None`
        :rtype: Optional[List[Secret]]
        """
        secrets = task.secrets if task.secrets is not None else []
        command = listify(task.command)
        if command[0].startswith('odin'):
            try:
                # Check if the odin-cred secret exists
                _ = self.core_api.read_namespaced_secret(name=ODIN_CRED, namespace=self.namespace)
                cred_secret = Secret(os.path.join(SECRET_LOC, ODIN_CRED_FILE), ODIN_CRED, ODIN_CRED_FILE)
                # Make sure they aren't already requesting this secret
                if not any(s == cred_secret for s in secrets):
                    secrets.append(cred_secret)
            except client.rest.ApiException:
                if '--cred' not in task.args:
                    LOGGER.warning(
                        'No --cred arg found on job %s and no odin-cred secret found to populate container.', task.name
                    )
        if command[0].startswith('odin-chores'):
            try:
                # Check if the ssh-key secret exists
                _ = self.core_api.read_namespaced_secret(name=SSH_KEY, namespace=self.namespace)
                # Make the key permissions -rw-------
                ssh_secret = Secret(os.path.join(SECRET_LOC, SSH_KEY_FILE), SSH_KEY, SSH_KEY_FILE, SSH_MODE)
                # Make sure they aren't already requesting this secret
                if not any(s == ssh_secret for s in secrets):
                    secrets.append(ssh_secret)
            except client.rest.ApiException:
                pass
        return secrets if secrets else None

    def _generate_configmaps(self, task: Task) -> Optional[List[ConfigMap]]:

        """Generate configmaps based on the requirements of the job.

        Eventually we can support custom configmaps by having the job create
        configmaps from the yaml config. Then this function will combine configmaps
        on the job with these injected configmaps to yield the final full list.

        :param task: The job we are running and want to add configmaps too.
        :type task: Task
        :returns: A list of configmaps or `None`
        :rtype: Optional[List[ConfigMap]]
        """
        configmaps = task.config_maps if task.config_maps is not None else []
        command = listify(task.command)
        if command[0].startswith('odin-chores'):
            try:
                # Check that the ssh-config configmap exists
                _ = self.core_api.read_namespaced_config_map(name='ssh-config', namespace=self.namespace)
                # Inject an ssh_config that will use the ssh key we inject with a secret
                ssh_config = ConfigMap('/etc/ssh/ssh_config', 'ssh-config', 'ssh_config')
                # Inject a known hosts file so it can find our gitlab server.
                known_hosts = ConfigMap('/etc/ssh/ssh_known_hosts', 'ssh-config', 'known_hosts')
                configmaps.extend((ssh_config, known_hosts))
            except client.rest.ApiException:
                pass
        return configmaps if configmaps else None

    def get_events(self, name: str, store: Store) -> List[Event]:
        """Get the k8s events that happened to some pod.

        :param name: The pod to get events for.
        :param store: The job store.

        :returns: The event information.
        """

        try:
            task_entry = store.get(name)
            # If its a CRD, the resource_id may not match the user given name, so this updates it
            name = task_entry[Store.RESOURCE_ID]
        except KeyError:
            pass

        field_selectors = (
            f"involvedObject.name={name},involvedObject.namespace={self.namespace},involvedObject.kind={self.kind}"
        )
        events = self.core_api.list_event_for_all_namespaces(field_selector=field_selectors)
        return [
            Event(
                event.type,
                event.reason,
                ",".join([x for x in event.source.to_dict().values() if x is not None]),
                event.message,
                event.last_timestamp,
            )
            for event in events.items
        ]

    def get_api(self):
        """Give back the API handler for this thing
        :return:
        """

    def get_pods(self, name: str) -> List[client.models.v1_pod.V1Pod]:
        """Get pods associated with this resource

        :param name: The name of this resource
        :type name: str
        :return A list of pods associated with this Task
        :rtype: List[client.models.v1_pod.V1Pod]
        """

    def submit(self, task: Task) -> str:
        """Submit a resource

        :param task: Task definition
        :type task: Task
        :return: A string identifier
        :rtype: str
        """

    def status(self, name: str, store: Store) -> Status:
        """Get a status by resource

        :param name:  A resource identifier
        :type name: str
        :param store: A jobs store
        :type store: Store
        :return: Return a `Status` object
        """

    def kill(self, name: str, store: Store):
        """Kill a resource that is running in k8s

        :param name: A resource identifier
        :type name: str
        :param store: A jobs store
        :type store: Store
        :return: None
        """


class StatusType(Enum):
    """General purpose mapping of Status onto an object, irrespective of ResourceType

    """

    RUNNING = "RUNNING"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"
    MISSING = "MISSING"

    @staticmethod
    def from_pod_status(pod_status: client.V1PodStatus) -> 'StatusType':
        """Create a status message from `Pod` output

        :param pod_status: The pod status
        :return: An enum value
        """
        phase = pod_status.phase
        if phase not in ResourceHandler.TERMINAL_PHASES:
            return StatusType.RUNNING
        if phase == 'Succeeded':
            return StatusType.SUCCEEDED
        return StatusType.FAILED

    @staticmethod
    def from_job_status(job_status: Any) -> 'StatusType':
        """Create a status message from `Job` output

        :param job_status: The job status
        :return: An enum value
        """
        if job_status.active:
            return StatusType.RUNNING
        if job_status.failed:
            return StatusType.FAILED

        #  if job_status.succeeded:
        return StatusType.SUCCEEDED


def json_to_selector(selectors: Dict[str, str]) -> str:
    """Convert a json dict into a selector string."""
    return ', '.join(f"{k}={v}" for k, v in selectors.items())


def find_bearer_token(api: client.CoreV1Api, svc_acc: str, namespace: str = 'default') -> str:
    """Get the bearer token. Used when odin is running locally on a cluster with RBAC.

    :param api: The k8s api client
    :param svc_acc: The name of the service account
    :param namespace: The namespace of the service account

    :returns: The bearer token. Returns an empty string if not found.
    """
    try:
        sa = api.read_namespaced_service_account(svc_acc, namespace=namespace)
        secret = api.read_namespaced_secret(sa.secrets[0].name, namespace=namespace)
        token = b64decode(secret.data['token']).decode('utf-8')
        return f"bearer {token}"
    except client.rest.ApiException:
        return ""


def get_custom_object_name(
    api: client.CustomObjectsApi, name: str, group: str, version: str, plural: str, namespace: str = 'default'
) -> str:
    """Get the name generated by kubeflow for tf/pyt jobs.

    :param api: The k8s api to interact with tf/pyt jobs.
    :type api: client.CustomObjectsAPI
    :param name: The name that odin gives the task
    :type name: str
    :param group: The group name of the people creating the custom resource (kubeflow.org)
    :param version: The version of the api to use. (defaults to v1beta2 for kubeflow objects)
    :param plural: The name used by the custom objects in the api. TFJob -> tfjobs, PytorchJob -> pytorchjob
    :param namespace: The namespace of the job.

    :returns: The name that kubeflow gives the job.
    """
    jobs = api.list_namespaced_custom_object(group, version, namespace, plural)['items']
    job = [j for j in jobs if j['metadata']['generateName'] == name]
    if job:
        return job[0]['metadata']['name']
    return None


def task_to_pod_spec(  # pylint: disable=too-many-locals
    task: Task,
    container_name: Optional[str] = None,
    secrets: Optional[List[Secret]] = None,
    configmaps: Optional[List[ConfigMap]] = None,
) -> client.V1PodSpec:
    """Convert this job into a POD spec that a k8s scheduler can run

    :param task: name for this task
    :type task: Task
    :param container_name: name for the container if None, it will be the job name
    :type container_name: Optional[str]
    :param secrets: A list of secrets to inject into the container.
    :type secrets: Optional[List[Secret]]
    :param configmaps: A list of configmaps to inject.
    :type configmaps: Optional[List[ConfigMap]]
    :returns: A PodSpec in the k8s client API
    :rtype: client.V1PodSpec
    """
    limits = {}
    requests = {}
    if task.num_gpus is not None:
        limits['nvidia.com/gpu'] = task.num_gpus
    if task.cpu is not None:
        limits['cpu'] = task.cpu.limits
        requests['cpu'] = task.cpu.requests
    resources = client.V1ResourceRequirements(limits=limits, requests=requests)
    sec_ctx = client.V1PodSecurityContext()
    if task.security_context is not None:
        if task.security_context.fs_group is not None:
            sec_ctx.fs_group = task.security_context.fs_group
        if task.security_context.run_as_group is not None:
            sec_ctx.run_as_group = task.security_context.run_as_group
        if task.security_context.run_as_user is not None:
            sec_ctx.run_as_user = task.security_context.run_as_user
    volume_mounts = []
    if task.mounts is not None:
        volume_mounts.extend(client.V1VolumeMount(mount_path=m.path, name=m.name) for m in task.mounts)

    if secrets is not None:
        volume_mounts.extend(client.V1VolumeMount(mount_path=s.path, name=s.name, sub_path=s.sub_path) for s in secrets)
    if configmaps is not None:
        volume_mounts.extend(
            client.V1VolumeMount(mount_path=c.path, name=c.name, sub_path=c.sub_path) for c in configmaps
        )

    container = client.V1Container(
        args=task.args,
        command=listify(task.command),
        name=container_name if container_name else task.name,
        image=task.image,
        volume_mounts=volume_mounts if volume_mounts else None,
        image_pull_policy=task.pull_policy,
        resources=resources,
        env=[
            client.V1EnvVar(ODIN_TASK_ENV, task.name),
            client.V1EnvVar(ODIN_CRED_ENV, os.path.join(SECRET_LOC, ODIN_CRED_FILE)),
        ],
    )

    volumes = []
    if task.mounts is not None:
        for mount in task.mounts:
            pvc = client.V1PersistentVolumeClaimVolumeSource(claim_name=mount.claim)
            volumes.append(client.V1Volume(name=mount.name, persistent_volume_claim=pvc))
    if secrets is not None:
        secrets = {s.name: s for s in secrets}
        volumes.extend(
            client.V1Volume(
                name=secret.name, secret=client.V1SecretVolumeSource(secret_name=secret.name, default_mode=secret.mode)
            )
            for secret in secrets.values()
        )
    if configmaps is not None:
        volumes.extend(
            client.V1Volume(name=c, config_map=client.V1ConfigMapVolumeSource(name=c))
            for c in set(c.name for c in configmaps)
        )

    selector = task.node_selector if task.node_selector else None

    regcred = client.V1LocalObjectReference(name='registry')
    pod_spec = client.V1PodSpec(
        containers=[container],
        security_context=sec_ctx,
        image_pull_secrets=[regcred],
        volumes=volumes if volumes else None,
        node_selector=selector,
        restart_policy=ResourceHandler.RESTART_NEVER,
    )
    return pod_spec


class KubernetesTaskManager(TaskManager):
    """`TaskManager` implementation to use k8s to schedule
    """

    def __init__(self, store: Store, namespace: str = 'default', modules: List[str] = DEFAULT_MODULES):
        """Create a Pod scheduler

        :param store: A job store
        :param namespace: A k8s namespace, defaults to `default`
        :param modules: A list of ResourceHandler modules to load
        """
        super().__init__()
        self.namespace = namespace
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            config.load_kube_config()
        self.store = store

        for module in modules:
            import_user_module(module)
        self.handlers = {k: create_resource_handler(k, namespace) for k in RESOURCE_HANDLERS.keys()}

    async def follow_logs(  # pylint: disable=missing-yield-type-doc,too-many-locals
        self,
        resource_name: str,
        namespace: str = 'default',
        container: Optional[str] = None,
        lines: Optional[int] = None,
        service_account: str = 'odin',
    ) -> AsyncIterator[str]:
        """Stream the logs from a pod in an async way.

        The logs are streamed a line at a time (separated by `\n`)

        Note:
            Because we stream logs via async code we have to directly interact with
            the k8s rest API via the requests_async library. This requires using
            camelCase when interacting with it.

        :param resource_name: The name of the thing to get logs from
        :param namespace: The namespace the pod lives in
        :param container: The container to get logs from. Only needed when there
            are multiple pods in a single container.
        :param lines: Only grab the last {lines} entries from the log
        :param service_account: The service account used on rbac clusters.
        :returns: An async generator of strings
        """
        try:
            config.load_incluster_config()
            conf = client.Configuration()
            api = client.CoreV1Api()
        except config.config_exception.ConfigException:
            config.load_kube_config()
            conf = client.Configuration()
            api = client.CoreV1Api()
            bearer = find_bearer_token(api, service_account)
            if bearer:
                conf.api_key['authorization'] = bearer

        pods = self.find_resource_names(resource_name)
        if len(pods) > 1:
            for msg in chain([f"Found {len(pods)} pods,"], pods, [f"Using pod/{pods[0]}"]):
                yield msg
        pod = pods[0] if pods else resource_name

        params = {'follow': 'true'}
        if container is not None:
            params['container'] = container
        if lines is not None:
            # Here we use camelCase because we are directly interacting with the k8s rest api
            # and it demands camelCase like the yaml manifests do.
            params['tailLines'] = lines
        resp = await arequests.get(
            f"{conf.host}/api/v1/namespaces/{namespace}/pods/{pod}/log",
            params=params,
            stream=True,
            verify=conf.ssl_ca_cert,
            headers=conf.api_key,
        )
        line = []
        async for chunk in resp.iter_content():
            if chunk == b"\n":
                yield b"".join(line).decode('utf-8')
                line = []
                continue
            line.append(chunk)
        yield b"".join(line).decode('utf-8')

    # Need to push this down into the resource handler
    def get_logs(self, name: str, container: Optional[str] = None, lines: Optional[int] = None) -> str:
        """Get a snapshot of the logs of a pod.

        Note:
            This function is implemented via the python k8s client which is synchronous
            and uses snake_case for parameters.

        :param name: The name of the resource to get logs from
        :param container: The container to get logs from. Only needed when there
            are multiple pods in a single container.
        :param lines: Only grab the last {lines} entries from the log
        :returns: The logs in a single string.
        """
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            config.load_kube_config()
        prefix = ""
        api = client.CoreV1Api()

        pods = self.find_resource_names(name)
        if len(pods) > 1:
            prefix = "\n".join(chain([f"Found {len(pods)} pods,"], pods, [f"using pod/{pods[0]}"]))
        if not pods:
            pods.append(name)

        # Here we fill a dict with the extra parameters for our call to `read_namespaced_pod_log`. This is
        # because to get the default behavior you need to not pass a value, passing a value of `None` isn't
        # the same thing. The other option is a large mess of ifs to make calls with different parameters.
        args = {}
        if container is not None:
            args['container'] = container
        if lines is not None:
            # Here the parameter is in snake_case because we are interacting with k8s through the python client.
            args['tail_lines'] = lines

        all_logs = [prefix] if prefix else []
        for pod in pods:
            logs = api.read_namespaced_pod_log(pod, namespace=self.namespace, **args)
            all_logs.append(f"{'='*16}\n{pod}\n{'-'*16}\n{logs}")
        return '\n'.join(all_logs)

    def _find_resources(self, task: str) -> List[Tuple[str, str]]:

        """Figure out what type of resource this is.

        If its a svc or deployment it should have a long name with `/` delimiter.
        If it is a job inside odin, we will just look up its kind

        :param task:
        :return: give back a 2 strings, the first is the resource type, the second is the id
        """

        if '/' in task:
            prefix, resource = task.split('/')
            prefix = prefix.lower()
            if prefix in ('svc', 'service'):
                return [('svc', resource),]
            if prefix in ('deploy', 'deployment'):
                return [('deploy', resource),]

        try:
            job_entry = self.store.get(task)
            if job_entry['parent'] is None:
                sub_tasks = job_entry['waiting'] + job_entry['executing'] + job_entry['executed']
                task_entries = [self.store.get(s) for s in sub_tasks]
                return [(sub.get(Store.RESOURCE_TYPE, 'Pod'), sub[Store.RESOURCE_ID]) for sub in task_entries]
        except KeyError:
            # If the resource is missing from the job db we assume it some thing the user
            # figured out like the `${PyTorchJob_ID}-worker-0`. This lets us get logs
            # from arbitrary resources on the cluster
            return [('Pod', task),]

        return [(job_entry.get(Store.RESOURCE_TYPE, 'Pod'), job_entry[Store.RESOURCE_ID]),]

    def find_resource_names(self, task: str) -> List[str]:
        """Find possible pods that we could get logs from.

        If they request logs from a service with svc/service-name or deploy/deployment-name
        do the same thing kubectl logs does, pick one and show the logs. Differently from kubectl
        we list that possible options so users can get logs from one specifically if they want.

        If the resource they want logs from is a pytorch or tf job when we get logs from a specific pod

        :param task: The thing we want logs from
        :returns: The list of pods that it makes sense to get logs from.
        """
        resources = self._find_resources(task)
        all_pods = []
        for (resource_type, resource) in resources:
            pods = self.handler_for(resource_type).get_pods(resource)
            for p in pods:
                all_pods.append(p.metadata.name)
        return all_pods

    def handler_for(self, resource_type: str = "Pod") -> object:
        """Get the right API based on the `resource_type`

        :param resource_type: The resource type to get an API for
        :return: return some API
        """
        return self.handlers[resource_type]

    # def _get_pods(self):
    #    results = self.api_for(ResourceType.POD).list_namespaced_pod(namespace=self.namespace)
    #    return [item for item in results.items if self.store.is_a_child(item)]

    def _status(self, handle: Handle):  # pylint: disable=missing-return-type-doc
        """Get the status of a job.

        :param handle: A string id of Job
        :returns: The status object
        """
        resource_type = self.get_resource_type(handle)
        name = handle.name if isinstance(handle, Task) else handle
        handler = self.handler_for(resource_type)
        return handler.status(name, self.store)

    def status(self, handle: Handle) -> Status:
        """Get the status of a pod

        :param handle: A string id or Job
        :return: The k8s status
        """
        try:
            status = self._status(handle)
            if isinstance(status, Status):
                return status
            return Status(StatusType.from_pod_status(status), status.message)
        except client.rest.ApiException:
            return Status(StatusType.MISSING, "resource not found")

    def submit(self, task: Task, **kwargs) -> str:
        """Submit job as a pod

        :param task: a `Task` to submit
        :param kwargs:
        :return: k8s response
        """
        try:
            return self.handler_for(task.resource_type).submit(task)
        except client.rest.ApiException as exc:
            raise SubmitError(json.loads(exc.body)['message'])

    def kill(self, handle: Handle) -> None:  # pylint: disable=missing-return-type-doc
        """Kill a Job

        :param handle: A string id or Job
        """
        resource_type = self.get_resource_type(handle)
        name = handle.name if isinstance(handle, Task) else handle
        self.handler_for(resource_type).kill(name, self.store)

    async def wait_for(self, task: Task) -> Task:
        """Wait for pod to complete, as defined by any of these phases

        :param job: The `Job` to wait on
        :returns: The Job when it is done.
        """
        while self.status(task).status_type is StatusType.RUNNING:
            await asyncio.sleep(1)
        return task

    async def wait_until_running(self, task: Task) -> None:
        """Wait for a pod to actually start running.

        :param job: The `Job` to wait on.
        """
        while self._status(task).phase != ResourceHandler.PHASE_RUNNING:
            await asyncio.sleep(1)

    async def hash_task(self, task: Task) -> List[str]:
        """Get the hash of a task, defined as the list of hashes for each container the task uses.

        In order to tell if a task in a pipeline can be skipped we need to know that the code for that task is
        unchanged. This can be done with a hash of the container the code runs in. Docker creates a hash of the
        container (using sha256). k8s also tracks this container hash for containers that are running in a pod.

        In order to get the container hashes we need the job running on the cluster so we create a copy of the
        job, change the command to sleep rather than running code, and removing things that would stop it from
        running right away (gpus, node_selectors, etc) and execute this job. Now that the job is running we
        can query the k8s api to get the job status and extract the hashes for all the containers in the job.

        :param task: The task to hash
        :returns: A list of hashes for the container that make up the job.
        """
        task = deepcopy(task)
        # Update the job name so in cause it is still alive when the real job runs the names won't collide.
        task.name = task.name + HASH_TRAILING
        task.args = ['300']
        task.command = 'sleep'
        # Remove things that could stop it from running right away
        task.node_selector = None
        task.num_gpus = None
        task.mount = None
        # Spin up the task
        try:
            self.submit(task)
        except client.rest.ApiException as exc:
            raise SubmitError(json.loads(exc.body)['message'])
        # Make sure the task is actually running. We can't get the hashes if the pod is in the Pending state
        await self.wait_until_running(task)
        # Get the imageId of all the containers in the task (they look like this)
        # "docker-pullable://localhost:32000/blester/mongo-demo@sha256:550892bae020e5ac0b850d6a2e1bd0e8cc5c9eb5eed903dc3544f808981f7076"  # pylint: disable=line-too-long
        task_status = self._status(task)
        statuses = sorted(task_status.container_statuses, key=lambda x: x.image)
        hashes = list(
            map(
                lambda x: x.groups()[0],
                filter(lambda x: x is not None, (re.search('@sha256:(.*)$', s.image_id) for s in statuses)),
            )
        )
        self.kill(task)
        return hashes

    def results(self, handle: Handle) -> Dict:
        """Get results from job store

        :param handle: A string id or Job
        :return: task results dict
        """
        name = handle.name if isinstance(handle, Task) else handle
        return self.store.get(name)

    def get_events(self, name: str) -> List[Event]:
        """Get the k8s events that happened to some pod.

        :param name: name

        :returns: The event information.
        """
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            config.load_kube_config()

        all_events = []
        resources = self._find_resources(name)
        for (resource_type, name) in resources:
            handler = self.handler_for(resource_type.lower())
            events = handler.get_events(name, self.store)
            all_events += events
        return all_events

    def get_resource_type(self, handle: Handle) -> str:
        """What type of resource is associated with this job

        If the input is a `Job`, we can just pass back its
        `resource_name` field.  If its a handle, we need to find
        it in the Job DB.

        :param handle: The string name of the job or a `Task` itself
        :return: A ResourceType
        """
        if isinstance(handle, Task):
            return handle.resource_type
        json_obj = self.store.get(handle)
        return json_obj.get(Store.RESOURCE_TYPE, "Pod")


RESOURCE_HANDLERS = {}


@optional_params
def register_resource_handler(cls: Type[ResourceHandler], aliases: List[str] = None) -> Type[ResourceHandler]:
    """Register an export policy

    :param cls: The class name
    :param aliases: `List[str]` A list of aliases other than ResourceHandler.NAME
    :raises Exception: If name is already registered.
    :return: The class
    """
    aliases = aliases if aliases is not None else []
    names = aliases + [cls.NAME, cls.NAME.lower()]

    for name in names:
        if name in RESOURCE_HANDLERS:
            raise Exception(
                'Error: attempt to re-define previously '
                f'registered ExportPolicy {name} (old: {RESOURCE_HANDLERS[name]}, new: {cls}) in registry'
            )
        RESOURCE_HANDLERS[name] = cls
    return cls


def create_resource_handler(name: str, namespace: str) -> ResourceHandler:
    """Create an export policy from the registry

    :param name: A name identifier
    :type name: str
    :param namespace: A namespace to pass
    :type namespace: str
    :return: A constructed instance
    """
    return RESOURCE_HANDLERS[name](namespace)
