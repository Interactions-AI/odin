"""Job store API
"""
import re
import os
from typing import Dict, List, Optional, Any

import pymongo
from baseline.utils import read_config_file


# Same constants as defined in odin.k8s, repeated here to avoid circular import
ODIN_TASK_ENV = "ODIN_TASK_ID"
ODIN_CRED_ENV = "ODIN_CRED"


class Store:
    """Base interface for a job store
    """

    JOBS = 'jobs'
    STATUS = 'status'
    PARENT = 'parent'
    EXECUTED = 'executed'
    EXECUTING = 'executing'
    REV_VER = 'version'
    WAITING = 'waiting'
    JOB_NAME = 'job'
    PIPE_ID = 'label'
    ERROR_MESSAGE = 'error_message'
    REQUEST_EARLY_EXIT = 'request_early_exit'
    DONE = 'DONE'
    COMPLETION_TIME = 'completion_time'
    SUBMIT_TIME = 'submit_time'
    RESOURCE_ID = 'resource_id'
    RESOURCE_TYPE = 'resource_type'
    CACHED = 'Cached'

    def __init__(self):
        """A Store is an abstract interface for talking to a job database
        """

    def get(self, job_id: str) -> Dict:
        """This gives back the result of the job store for this entry

        :param job_id: This is a unique ID for this job
        :return: A dictionary containing the output user data
        """

    def set(self, value: Dict) -> None:
        """This updates the job store for this entry

        This Dict must include a `label` key
        :param value: An object to store for this job
        """
        self._set_preconditions(value)
        self._set(value)

    def _set(self, value: Dict):
        """Actual setter function

        :param value:
        :return:
        """

    def exists(self, job_id: str) -> bool:
        """Check if there is a job in the database with this id

        :param job_id:
        :return:
        """

    def remove(self, job_id: str) -> bool:
        """Delete a job from the database

        :param job_id:
        :return: If the job could be removed
        """

    def get_parent(self, job_str: str) -> Dict:
        """Get job results from the parent job

        :param job_str: This job
        :return: The parent job
        """

    def get_previous(self, job_str: str) -> List[Dict]:
        """Get all job results that can before this job

        :param job_str: This job
        :return: All previous
        """

    def _set_preconditions(self, value: Dict):
        if value is None:
            raise Exception("You may not set an empty value")

        if Store.PIPE_ID not in value:
            raise Exception(f"There must a be {Store.PIPE_ID} field in the dictionary to persist it")

    def parents_like(self, pattern: str) -> List[str]:
        """Get all the parent jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any parents that match this
        """

    def children_like(self, pattern: str) -> List[str]:
        """Get all jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any jobs taht match this
        """

    def is_a_child(self, child: str) -> bool:
        """Is the resource a child of a job

        :param child: The name of the child
        :return: `True` if its a child
        """


class MemoryStore(Store):
    """MemoryStore is a memory-backed store, mainly for testing
    """

    def __init__(self):
        """Use a `Dict` to hold state locally
        """
        super().__init__()
        self.db = {}

    def get(self, job_id: str) -> Dict:
        """This gives back the result of the job store for this entry

        :param job_id: This is a unique ID for this job
        :return: A dictionary containing the output user data
        """
        return self.db[job_id]

    def _set(self, value: Dict) -> None:
        """This updates the job store for this entry

        This Dict must include a `label` key
        :param value: An object to store for this job
        """

        self.db[value[Store.PIPE_ID]] = value

    def exists(self, job_id: str) -> bool:
        """Check if there is a job in the database with this id

        :param job_id:
        :return:
        """
        return job_id in self.db

    def remove(self, job_id: str) -> bool:
        """Delete a job from the database

        :param job_id:
        :return: If the job could be removed
        """
        if job_id not in self.db:
            return False

        del self.db[job_id]
        return True

    def get_parent(self, job_str: str) -> Dict:
        """Get job results from the parent job

        :param job_str: This job
        :return: The parent job
        """
        return self.get(self.get(job_str)[Store.PARENT])

    def get_previous(self, job_str: str) -> List[Dict]:
        """Get all job results that came before this job

        :param job_str: This job
        :return: All previous
        """
        parent = self.get_parent(job_str)
        return [self.get(prev) for prev in parent[Store.EXECUTED]]

    def _match_like(self, pattern: str) -> List[str]:
        matches = [key for key in self.db.keys() if re.match(pattern, key)]
        return matches

    def parents_like(self, pattern: str) -> List[str]:
        """Get all the parent jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any parents that match this
        """
        matches = self._match_like(pattern)
        parents = [match for match in matches if 'j--' not in match]
        return parents

    def children_like(self, pattern: str) -> List[str]:
        """Get all jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any jobs taht match this
        """
        matches = self._match_like(pattern)
        children = [match for match in matches if 'j--' in match]
        return children

    def is_a_child(self, child: str) -> bool:
        """Is the resource a child of a job

        This is a hack, but we dont really care since this
        isnt used for production, just testing.

        :param child: The name of the child
        :return: `True` if its a child
        """
        return 'j--' in child


class Cache:
    """Abstract basecase for a key-value cache."""

    def __setitem__(self, key: str, value: Any) -> None:
        """Add to the cache, if the key exists overwrite it.

        :param key: The key to add to the cache.
        :param value: The value that goes with the key
        """

    def __getitem__(self, key: str) -> Any:
        """Get data from the cache. Returns None if key is missing.

        :param key: The key to look for.
        :returns: The value associated with key.
        """

    def __delitem__(self, key: str) -> None:
        """Delete a key-value pair from the cache.

        :param key: The key to remove.
        """

    def keys(self) -> List[str]:
        """Get the keys in the cache."""


class MemoryCache(Cache):
    """An in-memory key-value cache implemented as a dict."""

    def __init__(self):
        super().__init__()
        self.db = {}

    def __setitem__(self, key: str, value: Any) -> None:
        """Add to the cache, if the key exists overwrite it.

        :param key: The key to add to the cache.
        :param value: The value that goes with the key
        """
        self.db[key] = value

    def __getitem__(self, key: str) -> Any:
        """Get data from the cache. Returns None if key is missing.

        :param key: The key to look for.
        :returns: The value associated with key.
        """
        return self.db.get(key)

    def __delitem__(self, key: str) -> None:
        """Delete a key-value pair from the cache.

        :param key: The key to remove.
        """
        self.db.pop(key, None)

    def keys(self) -> List[str]:
        """Get the keys in the cache."""
        return self.db.keys()


class MongoCache(Cache):
    """A key-value cache backed by a Mongodb."""

    COLL = 'hashes'
    IN = 'inputs'
    OUT = 'outputs'
    ID = '_id'

    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        passwd: Optional[str] = None,
        db: str = 'jobs_db',
        port: int = pymongo.MongoClient.PORT,
    ):
        """Connect to the mongodb backend.

        :param host: The location of the db.
        :param user: The username to log in with.
        :param passwd: The password to use.
        :param db: The database to use.
        :param port: The port to connect on.
        :raises Exception: If connection to mongo fails.
        :raises ServerSelectionTimeoutError: If the connection times out.
        """
        super().__init__()
        self.dbhost = host
        if user and passwd:
            uri = f"mongodb://{user}:{passwd}@{host}:{port}/{db}"
            client = pymongo.MongoClient(uri)
        else:
            client = pymongo.MongoClient(host, port)
        if client is None:
            raise Exception(f"Cannot connect to mongo: [{host}:{port}] as user: [{user}]")
        try:
            self.db = client.get_database(db)
        except pymongo.errors.ServerSelectionTimeoutError:
            raise Exception(f"Connot get db from mongo: [{host}:{port}], connections timed out")
        # Creating an index in Mongo is Idempotent
        self.db[MongoCache.COLL].create_index([(MongoCache.IN, pymongo.ASCENDING)], unique=True)

    def __setitem__(self, key: str, value: Any) -> None:
        """Add to the cache, if the key exists overwrite it.

        :param key: The key to add to the cache.
        :param value: The value that goes with the key
        """
        self.db[MongoCache.COLL].replace_one(
            {MongoCache.IN: key}, {MongoCache.IN: key, MongoCache.OUT: value}, upsert=True
        )

    def __getitem__(self, key: str) -> Any:
        """Get data from the cache. Returns None if key is missing.

        :param key: The key to look for.
        :returns: The value associated with the key.
        """
        hit = self.db[MongoCache.COLL].find_one({MongoCache.IN: key})
        return hit[MongoCache.OUT] if hit else None

    def __delitem__(self, key: str) -> None:
        """Delete a key-value pair from the cache.

        :param key: The key to remove.
        """
        self.db[MongoCache.COLL].delete_one({MongoCache.IN: key})

    def keys(self) -> List[str]:
        """Get the keys in the cache."""
        return [doc[MongoCache.IN] for doc in self.db[MongoCache.COLL].find({}, {MongoCache.IN: 1, MongoCache.ID: 0})]


class MongoStore(Store):
    """MongoDB backed `Store` implementation

    This implementation fulfills the `Store` interface backed by a MongoDB
    """

    def __init__(self, host, user, passwd, db='jobs_db', port=pymongo.MongoClient.PORT):
        """A MongoStore is a Store implemented using MongoDB
        """
        super().__init__()
        self.dbhost = host
        if user and passwd:
            uri = f"mongodb://{user}:{passwd}@{host}:{port}/{db}"
            client = pymongo.MongoClient(uri)
        else:
            client = pymongo.MongoClient(host, port)
        if client is None:
            error_str = f"cannot connect to mongo: [{host}:{port}] as user: [{user}]"
            raise Exception(error_str)
        try:
            self.db = client.get_database(db)

        except pymongo.errors.ServerSelectionTimeoutError:
            raise Exception(f"cannot get db from mongo: [{host}:{port}], connection timed out")

    def _get_if(self, job_id: str):
        return self.db[MongoStore.JOBS].find_one({Store.PIPE_ID: job_id})

    def get(self, job_id: str) -> Dict:
        """This gives back the result of the job store for this entry

        :param job_id: This is a unique ID for this job
        :raises KeyError: If the job is not in the database.
        :return: A dictionary containing the output user data
        """
        result = self._get_if(job_id)
        if result is None:
            raise KeyError(f"No job {job_id} found in jobs DB")
        return result

    def get_parent(self, job_str: str) -> Dict:
        """Get job results from the parent job

        :param job_str: This job
        :return: The parent job
        """
        return self.get(self.get(job_str)[Store.PARENT])

    def get_previous(self, job_str: str) -> List[Dict]:
        """Get all job results that can before this job

        :param job_str: This job
        :return: All previous
        """
        parent = self.get_parent(job_str)
        return [self.get(prev) for prev in parent[Store.EXECUTED]]

    def _set(self, value: Dict) -> None:
        """This updates the job store for this entry

        :param value:
        """
        self.db[MongoStore.JOBS].replace_one({Store.PIPE_ID: value[Store.PIPE_ID]}, value, upsert=True)

    def exists(self, job_id: str) -> bool:
        """Check if there is a job in the database with this id

        :param job_id:
        :return:
        """
        return self._get_if(job_id) is not None

    def remove(self, job_id: str) -> bool:
        """Delete a job from the database

        :param job_id:
        :return: Did the removal succeed.
        """
        result = self._get_if(job_id)
        if result is None:
            return False

        db_id = result['_id']
        self.db[MongoStore.JOBS].remove({'_id': db_id})
        return True

    def parents_like(self, pattern: str) -> List[str]:
        """Get all the parent jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any parents that match this
        { <field>: { $regex: /pattern/<options> } }
        """
        parents = self.db[MongoStore.JOBS].find({Store.PIPE_ID: {'$regex': pattern}, Store.PARENT: None})

        return [p[Store.PIPE_ID] for p in parents]

    def children_like(self, pattern: str) -> List[str]:
        """Get all jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any jobs that match this
        """
        children = self.db[MongoStore.JOBS].find({Store.PIPE_ID: {'$regex': pattern}, Store.PARENT: {"$ne": None}})

        return [c[Store.PIPE_ID] for c in children]

    def is_a_child(self, child: str) -> bool:
        """Is the resource a child of a job

        :param child: The name of the child
        :return: `True` if its a child
        """
        children = self.children_like(child)
        return bool(children)


def write_outputs(output: Dict, label: Optional[str] = None, cred_file: Optional[str] = None) -> None:
    """Write the contents of `output` to the store as your output.

    :param output: The data you want to write, must be savable in mongo.
    :param label: The label used to look up the jobs db entry. Backs off to value stored in $ODIN_TASK_ID
    :param cred_file: The location where the odin cred file lives. Backs off to value stored in $ODIN_CRED
    """
    label = label if label is not None else os.getenv(ODIN_TASK_ENV)
    cred_file = cred_file if cred_file is not None else os.getenv(ODIN_CRED_ENV)
    cred = read_config_file(cred_file)
    store = MongoStore(**cred['jobs_db'])
    entry = store.get(label)
    out = entry['outputs']
    if out is None:
        entry['outputs'] = output
    else:
        out.update(output)
        entry['outputs'] = output
    store.set(entry)
