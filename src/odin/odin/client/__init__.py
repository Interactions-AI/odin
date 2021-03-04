"""Client code specific constants."""
import os
import requests
from typing import Dict
from odin.utils.auth import _authenticate

ODIN_URL = os.environ.get('ODIN_URL', 'localhost')
ODIN_PORT = os.environ.get('ODIN_PORT', 9003)


def encode_path(path: str) -> str:
    """Encode a path from `/` to `__`

    :param path: A path to encode
    :return: An encoded vector
    """
    vec = []
    while path:
        head, tail = os.path.split(path)
        vec.append(tail)
        path = head
    return '__'.join(filter(lambda x: x, vec[::-1]))


class HttpClient:
    def __init__(self, url=None, host=None, port=None, scheme=None, username=None, password=None, jwt_token=None):
        if url is None:
            if host is None:
                host = ODIN_URL
            if port is None:
                port = ODIN_PORT
            if scheme is None:
                scheme = 'https'
            self.url = f'{scheme}://{host}:{port}'
        else:
            self.url = url

        username = username
        password = password
        if username is not None and password is not None:
            self.jwt_token = _authenticate(self.url, username, password)
        else:
            self.jwt_token = jwt_token

    def schedule_pipeline(self, work: str) -> Dict:
        """Request the status over HTTP
        :param url: the base URL
        :param work: The pipeline ID
        """
        job = encode_path(work)
        response = requests.post(
            f'{self.url}/v1/pipelines',
            headers={'Authorization': f'Bearer {self.jwt_token}'},
            json={"pipeline": {"job": job}},
        )
        if response.status_code == 401:
            raise ValueError("Invalid login")
        results = response.json()
        return results

    def create_job(self, name: str) -> Dict:

        """Request the server makes a new job.

        :param url: Base url of the remote odin server
        :param name: The name of the job you want to create
        """
        job = encode_path(name)
        response = requests.post(
            f"{self.url}/v1/jobs", headers={"Authorization": f"Bearer {self.jwt_token}"}, json={"job": {"name": job}}
        )
        if response.status_code == 401:
            raise ValueError("Invalid Login")
        results = response.json()
        return results

    def request_events(self, resource: str) -> Dict:
        """Get events for a resource over HTTP

        :param url: The base URL
        :param resource: The resource ID
        """
        response = requests.get(f'{self.url}/v1/resources/{resource}/events')
        if response.status_code == 401:
            raise ValueError("Invalid login")
        results = response.json()
        return results

    def request_data(self, resource: str) -> Dict:
        """Get data for a resource over HTTP

        :param url: The base URL
        :param resource: The resource ID
        """
        response = requests.get(f'{self.url}/v1/resources/{resource}/data')
        results = response.json()
        return results

    def request_cluster_hw_status(self) -> Dict:
        """Request the status over HTTP
        """
        response = requests.get(f'{self.url}/v1/nodes')
        nodes = response.json()['nodes']
        return nodes

    def push_file(self, job: str, file_name: str, file_contents: str) -> Dict:
        """Push a file to update a pipeline.

        :param job: The job definition that will be updated
        :param file_name: The name to save the file as on the remove server
        :param file_contents: The content of the file we want to upload
        """
        job = encode_path(job)
        response = requests.post(
            f'{self.url}/v1/jobs/{job}/files/{file_name}',
            data=file_contents,
            headers={'Content-Type': 'text/plain', 'Authorization': f'Bearer {self.jwt_token}'},
        )
        if response.status_code == 401:
            raise ValueError("Invalid login")
        results = response.json()
        return results

    def delete_pipeline(self, work: str, purge_db: bool = False, purge_fs: bool = False) -> Dict:
        """Request delete pipeline
        :param url: the base URL
        :param work: The pipeline ID
        :param purge_db: Should we delete the pipeline from the jobs db too?
        :param purge_fs: Should we remove pipeline file system artifacts?
        """

        response = requests.delete(
            f'{self.url}/v1/pipelines/{work}',
            headers={'Authorization': f'Bearer {self.jwt_token}'},
            params={'db': purge_db, 'fs': purge_fs},
        )
        if response.status_code == 401:
            raise ValueError("Invalid login")
        results = response.json()
        return results

    def request_status(self, work: str) -> Dict:
        """Request the status over HTTP
        :param url: the base URL
        :param work: The pipeline ID
        :param columns: A set of columns to include in the output
        :param all_cols: Should we just show all columns, If true then columns in ignored
        """
        response = requests.get(f'{self.url}/v1/pipelines?q={work}')
        results = response.json()['pipelines']
        return results

    def request_logs(self, pod: str, namespace='default', **kwargs) -> str:
        """This function really shouldnt be provided here -- forget you saw this

        Using the logs directly from k8s isnt desirable, we should add this to the HTTP tier, but if you really
        need it, this function should get results back
        :param work:
        :return:
        """
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            config.load_kube_config()
        api = client.CoreV1Api()
        logs = api.read_namespaced_pod_log(pod, namespace=namespace, **kwargs)
        return logs
