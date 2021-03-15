#from pydantic import BaseModel as Model
# This gives us backwards compatible API calls
from fastapi_camelcase import CamelModel as Model
from typing import Optional, List
from datetime import date, datetime


class UserDefinition(Model):
    username: str
    password: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None


class UserWrapperDefinition(Model):
    user: UserDefinition


class UserResults(Model):
    users: List[UserDefinition]


class EventDefinition(Model):
    id: str
    event_type: str
    reason: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None
    timestamp: Optional[datetime] = None


class KeyValueDefinition(Model):
    key: str
    value: str


class VolumeMountDefinition(Model):
    path: str
    name: str
    claim: str


class EventResults(Model):
    events: List[EventDefinition]


class TaskDefinition(Model):
    id: str
    name: str
    image: str
    command: str
    args: List[str] = []
    mounts: List[VolumeMountDefinition] = []
    num_gpus: Optional[int]
    pull_policy: str
    node_selector: List[KeyValueDefinition] = []
    resource_type: str
    num_workers: Optional[int]
    depends: List[str] = []
    inputs: List[str] = []
    outputs: List[str] = []


class TaskStatusDefinition(Model):
    id: str
    task: str
    name: str
    status: str
    command: str
    image: str
    resource_type: str
    resource_id: str
    submit_time: Optional[datetime]
    completion_time: Optional[datetime]
    events: List[EventDefinition] = []


class PipelineDefinition(Model):

    id: Optional[str]
    job: str
    version: Optional[str]
    tasks: List[TaskStatusDefinition] = []
    name: Optional[str]
    status: Optional[str]
    message: Optional[str]
    submit_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None


class PipelineWrapperDefinition(Model):
    pipeline: Optional[PipelineDefinition] = None


class PipelineResults(Model):
    pipelines: List[PipelineDefinition] = []


class PipelineCleanupDefinition(Model):
    task_id: str
    cleaned_from_k8s: Optional[bool] = True
    purged_from_db: Optional[bool] = False
    removed_from_fs: Optional[bool] = False


class PipelineCleanupResults(Model):
    cleanups: List[PipelineCleanupDefinition] = []


class ConfigDefinition(Model):
    id: str
    name: str
    content: str


class JobDefinition(Model):
    id: Optional[str] = None
    name: str
    location: Optional[str] = None
    creation_time: Optional[datetime]
    tasks: List[TaskDefinition] = []
    configs: List[ConfigDefinition] = []


class JobWrapperDefinition(Model):
    job: Optional[JobDefinition] = None


class JobResults(Model):
    jobs: List[JobDefinition] = []


class UploadDefinition(Model):
    bytes: int
    location: str


class AuthResponseDefinition(Model):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """
    message: Optional[str] = None
