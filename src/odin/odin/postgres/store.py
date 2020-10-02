from typing import Optional, List, Any
import sqlalchemy as sql
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from odin.store import Cache, Store, Dict, register_cache_backend, register_store_backend
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from copy import deepcopy

class DB:

    SessionFactory = None
    Engine = None
    Base = declarative_base()

    @staticmethod
    def get_session_factory(pool_size=10, **kwargs):
        uri = kwargs.get('uri', None)
        if uri is None:
            dbtype = kwargs.get('dbtype', 'postgresql')
            host = kwargs.get('host', 'localhost')
            port = kwargs.get('port', None)
            if port is not None:
                host = '{}:{}'.format(host, port)
            username = kwargs.get('user', None)
            passwd = kwargs.get('passwd', None)

            user = username if passwd is None else '{}:{}'.format(username, passwd)
            dbname = kwargs.get('db', 'jobs_db')
            uri = '{}://{}@{}/{}'.format(dbtype, user, host, dbname)
        if not DB.SessionFactory:
            DB.Engine = sql.create_engine(uri, echo=False, paramstyle='format', pool_size=pool_size)
            DB.Base.metadata.create_all(DB.Engine)
            DB.SessionFactory = sessionmaker(DB.Engine)
        return DB.SessionFactory


class CacheTable(DB.Base):
    __tablename__ = 'hashes'
    id = sql.Column(sql.Integer, primary_key=True)
    inputs = sql.Column(sql.String, nullable=False)
    outputs = sql.Column(JSON, nullable=False)


class Job(DB.Base):
    __tablename__ = Store.JOBS
    id = sql.Column(sql.Integer, primary_key=True)
    label = sql.Column(sql.String, nullable=False)
    job_name = sql.Column(sql.String)
    version = sql.Column(sql.String)
    status = sql.Column(sql.String)
    submit_time = sql.Column(sql.DateTime)
    completion_time = sql.Column(sql.DateTime, nullable=True)
    parent_label = sql.Column(sql.String, nullable=True, default=None)
    details = sql.Column(JSON, nullable=False)


@register_cache_backend('postgres')
class PostgresCache(Cache):
    """A key-value cache backed by PG"""

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
        port: int = 5432,
        **kwargs
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
        self.Session = DB.get_session_factory(user=user, passwd=passwd, host=host, db=db, port=port)

    def __setitem__(self, key: str, value: Any) -> None:
        """Add to the cache, if the key exists overwrite it.

        :param key: The key to add to the cache.
        :param value: The value that goes with the key
        """
        session = self.Session()

        kv = session.query(CacheTable).filter(CacheTable.key == key).scalar()
        if kv:
            kv.value = value
        else:
            session.add(CacheTable(inputs=key, value=value))
        session.commit()

    def __getitem__(self, key: str) -> Any:
        """Get data from the cache. Returns None if key is missing.

        :param key: The key to look for.
        :returns: The value associated with the key.
        """
        session = self.Session()
        kv = session.query(CacheTable).filter(CacheTable.key == key)
        return kv.outputs

    def __delitem__(self, key: str) -> None:
        """Delete a key-value pair from the cache.

        :param key: The key to remove.
        """
        session = self.Session()

        kv = session.query(CacheTable).filter(CacheTable.key == key)
        if kv:
            session.delete(kv)

    def keys(self) -> List[str]:
        """Get the keys in the cache."""
        session = self.Session()
        stmt = sql.text("SELECT key FROM hashes")
        stmt = stmt.columns(CacheTable.inputs)
        return session.query(CacheTable.inputs).from_statement(stmt).all()


@register_store_backend('postgres')
class PostgresStore(Store):
    """MongoDB backed `Store` implementation

    This implementation fulfills the `Store` interface backed by a MongoDB
    """
    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        passwd: Optional[str] = None,
        db: str = 'jobs_db',
        port: int = 5432,
        **kwargs
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
        self.Session = DB.get_session_factory(user=user, passwd=passwd, host=host, db=db, port=port)

    def _get_if(self, job_id: str, session=None):
        if session is None:
            session = self.Session()
        return session.query(Job).filter(Job.label == job_id)

    def get(self, job_id: str) -> Dict:
        """This gives back the result of the job store for this entry

        :param job_id: This is a unique ID for this job
        :raises KeyError: If the job is not in the database.
        :return: A dictionary containing the output user data
        """
        result = self._get_if(job_id).scalar()
        if result is None:
            raise KeyError(f"No job {job_id} found in jobs DB")
        job_info = self._pack_job_info(result)
        return job_info

    def _pack_job_info(self, job: Job) -> Dict:
        job_info = {}
        job_info[Store.PIPE_ID] = job.label
        job_info[Store.JOB_NAME] = job.job_name
        job_info['status'] = job.status
        job_info[Store.SUBMIT_TIME] = job.submit_time
        job_info[Store.REV_VER] = job.version
        job_info[Store.PARENT] = job.parent_label
        job_info.update(job.details)
        return job_info

    def get_parent(self, job_str: str) -> Dict:
        """Get job results from the parent job

        :param job_str: This job
        :return: The parent job
        """
        return self._get_if(job_str).first().parent

    def get_previous(self, job_str: str) -> List[Dict]:
        """Get all job results that can before this job

        :param job_str: This job
        :return: All previous
        """
        session = self.Session()
        parent_label = self._get_if(job_str).first().parent_label
        details = session.query(Job).filter(Job.parent_label == parent_label).first().details
        executed = details[Store.EXECUTED]
        return session.query(Job).label.in_(executed)

    def _set(self, value: Dict) -> None:
        """This updates the job store for this entry

        :param value:
        """

        d = deepcopy(value)
        id = d.pop(Store.PIPE_ID)
        parent_label = d.pop(Store.PARENT, None)
        job_name = d.pop(Store.JOB_NAME, None)
        completion_time = d.pop(Store.COMPLETION_TIME, None)
        submit_time = d.pop(Store.SUBMIT_TIME, datetime.now())
        status = d.pop("status", None)
        version = d.pop(Store.REV_VER, None)

        session = self.Session()
        kv = self._get_if(id, session).scalar()
        if kv is not None:
            kv.details.update(d)
            if status is not None:
                kv.status = status
            if completion_time is not None:
                kv.completion_time = completion_time
        else:
            session.add(Job(label=id, details=d, version=version, status=status, submit_time=submit_time,
                            completion_time=completion_time, parent_label=parent_label, job_name=job_name))
        session.commit()

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
        session = self.Session()
        children = session.query(Job).filter(Job.parent_label == job_id).all()
        for job in children:
            session.delete(job)

        parent = session.query(Job).filter(Job.label == job_id).first()
        session.delete(parent)

        session.commit()
        return True

    def parents_like(self, pattern: str) -> List[str]:
        """Get all the parent jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any parents that match this
        { <field>: { $regex: /pattern/<options> } }
        """
        session = self.Session()
        matches = [h.label for h in session.query(Job).filter(Job.parent_label == None).filter(Job.label.ilike(f'{pattern}%')).all()]
        return matches

    def children_like(self, pattern: str) -> List[str]:
        """Get all jobs that match some pattern

        :param pattern: A pattern to match
        :return: Any jobs that match this
        """
        session = self.Session()
        matches = [h.label for h in session.query(Job).filter(Job.parent_label!=None).filter(Job.label.ilike(f'{pattern}%')).all()]
        return matches

    def is_a_child(self, child: str) -> bool:
        """Is the resource a child of a job

        :param child: The name of the child
        :return: `True` if its a child
        """
        return self._get_if(child).first().parent_label is not None


