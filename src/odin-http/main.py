import glob
import requests
import time
from shutil import copyfile
import yaml
from shortid import ShortId
from fastapi import FastAPI, Depends, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Template
from kubernetes import client, config
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os
import git
from datetime import datetime
import logging
from eight_mile.utils import read_yaml
from odin.http.models import *
from odin.http.orm import *
from odin.http.utils import (
    _convert_to_path,
    set_repo_creds,
    _request_status,
    _submit_job,
    _request_cleanup,
    _request_logs,
    _request_data,
    _request_events,
    _validate_filename,
)
import jose.jwt as jwt
# This indicates what branch we should be looking at in git for its pipelines
SHORT_ID = ShortId()
PIPELINES_MAIN = os.environ.get('ODIN_PIPELINES_MAIN', 'master')
RENDERED_TEMPLATES = os.environ.get('ODIN_RENDER_PATH', 'rendered')
JWT_ISSUER = os.environ.get('ODIN_AUTH_ISSUER', 'com.interactions')
JWT_SECRET = os.environ.get('ODIN_SECRET')
JWT_LIFETIME_SECONDS = os.environ.get('ODIN_TOKEN_DURATION', 60 * 60 * 12)
JWT_ALGORITHM = os.environ.get('ODIN_AUTH_ALG', 'HS256')
MIDGARD_PORT = os.environ.get('MIDGARD_PORT', 29999)
MIDGARD_API_VERSION = os.environ.get('MIDGARD_API_VERSION', 'v1')
LOGGER = logging.getLogger('odin-http')
WS_SCHEME = os.environ.get('ODIN_WS_SCHEME', 'ws')
WS_HOST = os.environ.get('ODIN_WS_HOST', 'localhost')
WS_PORT = os.environ.get('ODIN_WS_PORT', 30000)
ODIN_DB = os.getenv('ODIN_DB', 'odin_db')
ODIN_FS_ROOT = os.getenv('ODIN_FS_ROOT', '/data/pipelines')
LOGGER = logging.getLogger('odin-http')
TEMPLATE_SUFFIX = ".jinja2"

def get_db_config() -> dict:
    cred_params = {}
    cred_params['backend'] \
        = os.environ.get("ODIN_JOBS_BACKEND", "postgres")
    cred_params['dbhost'] = os.environ.get("SQL_HOST", "127.0.0.1")
    cred_params['dbport'] = os.environ.get("DB_PORT", 5432)
    cred_params['user'] = os.environ.get("DB_USER")
    cred_params['passwd'] = os.environ.get("DB_PASS")
    cred_params['odin_root_user'] = os.environ.get("ODIN_ROOT_USER")
    cred_params['odin_root_passwd'] = os.environ.get("ODIN_ROOT_PASS")
    cred_params['db'] = ODIN_DB
    LOGGER.warning('%s %s %s %s', cred_params['user'], cred_params['db'], cred_params['dbhost'], cred_params['dbport'])
    return cred_params


def get_ws_url():
    return f'{WS_SCHEME}://{WS_HOST}:{WS_PORT}'

def _generate_template_job_suffix(prefix: str) -> str:
    """This generates a new name from the provided prefix suffixed by a shortid

    :param prefix: A provided prefix
    :returns: A unique name that is a combination of the prefix and a shortid
    """
    short_id = SHORT_ID.generate().lower().replace('_', '-')[:4]
    return f'{prefix}{short_id}'


def _is_template(job_path):
    full_path = os.path.join(ODIN_FS_ROOT, job_path)
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        return False

    results = glob.glob(os.path.join(full_path, f'*{TEMPLATE_SUFFIX}'))
    if results:
        LOGGER.info("%s is a template", job_path)
        return True
    return False


def _substitute_template(job_path, context_map: dict):
    # Look for all templated files and replace them all

    target_dir = _generate_template_job_suffix(os.path.join(ODIN_FS_ROOT, RENDERED_TEMPLATES, job_path))

    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    templ_path = os.path.join(ODIN_FS_ROOT, job_path)
    LOGGER.info("Generating template job at %s", target_dir)
    if 'name' not in context_map:
        context_map['name'] = os.path.basename(target_dir)
    for base_file in os.listdir(templ_path):
        file = os.path.join(templ_path, base_file)
        output_file = base_file.replace(TEMPLATE_SUFFIX, "")
        rendered_file = os.path.join(target_dir, output_file)
        # If its not a template, copy it over
        if not file.endswith(TEMPLATE_SUFFIX):
            copyfile(file, os.path.join(target_dir, rendered_file))
            continue

        with open(file) as rf:
            source = rf.read()
            template = Template(source)
            rendered_yaml = template.render(context_map)

        # Convert it to a YAML object
        yy = yaml.load(rendered_yaml, Loader=yaml.FullLoader)

        with open(rendered_file, "w", encoding='utf-8') as wf:
            yaml.safe_dump(yy, wf)
            LOGGER.info("Wrote out %s", rendered_file)
    return target_dir


class VersionedAPI(FastAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.router.prefix = "/v1"


app = VersionedAPI(prefix="/v1")

# FIXME: tighten this up
app.add_middleware(CORSMiddleware,
                   allow_origins=['*'],
                   allow_methods=['OPTIONS'],
                   allow_headers=['Origin', 'X-Requested-With'])

dao = Dao(dbname=ODIN_DB, **get_db_config())
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth")

def _read_file(file_to_read):
    if not os.path.exists(file_to_read) or not os.path.isfile(file_to_read):
        raise Exception("Invalid filename: {}".format(file_to_read))
    with open(file_to_read, 'r') as rf:
        return rf.read()


def _get_job_loc(id_):
    return os.path.join(ODIN_FS_ROOT, id_)


def _get_job_file(id_, filename):
    return os.path.join(_get_job_loc(id_), filename)


def _get_job_repo_sha() -> str:
    repo = git.Repo(ODIN_FS_ROOT)
    repo = set_repo_creds(repo)
    sha = repo.head.object.hexsha
    return sha

# https://stackoverflow.com/questions/35585236/git-ls-remote-in-gitpython
def _ls_remote(repo):
    for ref in repo.git.ls_remote().split('\n'):
        hash_ref_list = ref.split('\t')
        if hash_ref_list[1] == 'HEAD':
            return hash_ref_list[0]
    raise Exception("Unknown head")


def _repo_version_match(repos: git.Repo) -> bool:
    master_version = _ls_remote(repos)
    head_version = str(git.repo.fun.rev_parse(repos, 'HEAD'))
    return master_version == head_version


def _stash_pull_pop(repo: git.Repo):
    do_push_pop = False
    if repo.is_dirty():
        LOGGER.warning("Repo is dirty.  Stashing changes")
        do_push_pop = True
        repo.git.stash()

    if not _repo_version_match(repo):
        LOGGER.info("Repo is out of date.  Pulling")
        repo.git.pull('--rebase', 'origin', f'{PIPELINES_MAIN}')

    if do_push_pop:
        LOGGER.warning("Popping stashed changes to repo")
        repo.git.stash('pop')


def _update_job_repo() -> None:
    repo = git.Repo(ODIN_FS_ROOT)
    repo = set_repo_creds(repo)
    _stash_pull_pop(repo)


def _add_to_job_repo(filename: str, message: str = None) -> str:
    """Push a directory to git

    :param dir: Directory
    :raises ChoreSkippedException: If there is missing inputs.
    :return: `True`
    """

    repo = git.Repo(ODIN_FS_ROOT)
    repo = set_repo_creds(repo)
    _stash_pull_pop(repo)
    repo.git.add([filename])
    if repo.is_dirty():
        repo.git.commit(m=message)
        repo.git.push()
    sha = repo.head.object.hexsha
    return sha


@app.get("/app")
def read_main(request: Request):
    repo = git.Repo(ODIN_FS_ROOT)
    repo = set_repo_creds(repo)

    return {
        "pipelines_root": ODIN_FS_ROOT,
        "pipelines_version": str(git.repo.fun.rev_parse(repo, f'origin/{PIPELINES_MAIN}')),
        "pipelines_repo_dirty": bool(repo.is_dirty()),
    }


@app.get("/ping")
def ping():
    return "pong"


@app.post("/auth")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> AuthResponseDefinition:
    user: User = dao.get_user(form_data.username)
    if not user:
        raise Exception("Bad username!")
    if not user.authenticate(form_data.password):
        raise Exception("Bad password!")

    timestamp = time.time()
    payload = {
        "iss": JWT_ISSUER,
        "iat": int(timestamp),
        "exp": int(timestamp + JWT_LIFETIME_SECONDS),
        "sub": str(user.username),
    }
    message = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return AuthResponseDefinition(message=message)


def _user_def(user: User) -> UserDefinition:
    return UserDefinition(username=user.username, firstname=user.firstname, lastname=user.lastname)


def _get_job_files(job_loc):
    configs = []
    job_dir = os.path.dirname(job_loc)
    base = os.path.basename(job_loc)
    for f in os.listdir(job_dir):
        if f == base:
            continue
        if (
            f.endswith(".py")
            or f.endswith(".js")
            or f.endswith("txt")
            or f.endswith(".yml")
            or f.endswith(".sh")
            or f.endswith("yaml")
            or f.endswith("json")
            or f.endswith("config")
            or f.endswith("cfg")
        ):
            id_ = os.path.join(job_dir, f)
            content = _read_file(id_)
            configs.append(ConfigDefinition(id=id_, name=f, content=content))
    return configs


def _job_def(id_):
    try:
        job_loc = _get_job_file(id_, 'main.yml')
        object = read_yaml(job_loc)
        tasks = []
        for t in object['tasks']:
            if 'mounts' not in t:
                t['mounts'] = t.pop('mount')
            name = t['name']
            t['id'] = f'{id_}--{name}'
            task_def = TaskDefinition(**t)
            tasks.append(task_def)
        job_def = JobDefinition(tasks=tasks, location=job_loc, name=id_, id=id_, configs=_get_job_files(job_loc))
        return job_def
    except Exception as e:
        LOGGER.error(e)
        return None


@app.get("/users")
def get_users(q: Optional[str] = None) -> UserResults:
    users = dao.get_users(q)
    user_list = [_user_def(u) for u in users]
    return UserResults(users=user_list)


@app.get("/users/{user_id}")
def get_user(user_id: str) -> UserWrapperDefinition:
    user = dao.get_user(user_id)
    user_def = _user_def(user)
    return UserWrapperDefinition(user=user_def)


@app.post("/users")
def create_user(user_def: UserWrapperDefinition, token: str=Depends(oauth2_scheme)) -> UserWrapperDefinition:
    user = dao.create_user(user_def.user)
    user_def = _user_def(user)
    return UserWrapperDefinition(user=user_def)


@app.put("/users/{user_id}")
def update_user(user_id: str, user_def: UserDefinition, token: str=Depends(oauth2_scheme)) -> UserWrapperDefinition:
    if user_id != user_def.username:
        LOGGER.warning("%s vs %s", user_id, user_def.username)
        user_def.username = user_id
    user = dao.update_user(user_def)
    user_def = _user_def(user)
    return UserWrapperDefinition(user=user_def)


@app.delete("/users/{user_id}")
def update_user(user_id: str, token: str=Depends(oauth2_scheme)) -> UserWrapperDefinition:
    user = dao.delete_user(user_id)
    user_def = _user_def(user)
    return UserWrapperDefinition(user=user_def)


@app.get("/nodes")
def get_node_info() -> str:
    def get_nodes() -> List[str]:
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            config.load_kube_config()

        core_api = client.CoreV1Api()
        return core_api.list_node().items
    results = []
    for node in get_nodes():
        addresses = node.status.addresses
        internal_address = [a.address for a in addresses if a.type == 'InternalIP'][0]
        host = [a.address for a in addresses if a.type == 'Hostname'][0]
        capacity_dict = node.status.capacity
        midgard_url = f'http://{internal_address}:{MIDGARD_PORT}/{MIDGARD_API_VERSION}/gpus'
        gpu_infos = requests.get(midgard_url).json()['gpus']
        capacity_dict['gpus'] = gpu_infos
        capacity_dict['host'] = host
        capacity_dict['internalIP'] = internal_address
        results.append(capacity_dict)

    return {'nodes': results}


@app.get("/pipelines")
async def get_pipelines(q: Optional[str] = None) -> PipelineResults:
    s = await _request_status(get_ws_url(), q)
    return s


@app.post("/pipelines")
async def create_pipeline(pipe_def: PipelineWrapperDefinition, token: str=Depends(oauth2_scheme)) -> PipelineWrapperDefinition:
    job = _convert_to_path(pipe_def.pipeline.job)
    _update_job_repo()
    if _is_template(job):
        job = _substitute_template(job, pipe_def.context or {})
    pipe_id = await _submit_job(get_ws_url(), job)
    p = PipelineDefinition(name=pipe_id, id=pipe_id, job=job)
    return PipelineWrapperDefinition(pipeline=p)


@app.get("/pipelines/{pipe_id}")
async def get_pipeline(pipe_id: str) -> PipelineWrapperDefinition:
    result = await _request_status(get_ws_url(), pipe_id)
    if result:
        return PipelineWrapperDefinition(pipeline=result.pipelines[0])
    raise Exception(f"No such pipeline {pipe_id}")


@app.delete("/pipelines/{pipe_id}")
async def cleanup_pipeline(pipe_id: str, db: bool=False, fs: bool=False, token: str=Depends(oauth2_scheme)) -> PipelineCleanupResults:
    cleanup_info = await _request_cleanup(get_ws_url(), pipe_id, db, fs)
    return cleanup_info


@app.get("/resources/{resource_id}/events")
async def get_events(resource_id) -> EventResults:
    event_info = await _request_events(get_ws_url(), resource_id)
    return event_info


@app.get("/resources/{resource_id}/data")
async def get_data(resource_id):
    data_info = await _request_data(get_ws_url(), resource_id)
    return data_info

@app.get("/resources/{resource_id}/logs")
async def get_data(resource_id):
    data_info = await _request_logs(get_ws_url(), resource_id)
    return data_info


@app.get("/jobs")
def get_jobs(q: Optional[str] = '*') -> JobResults:
    _update_job_repo()
    job_defs = []
    q = _convert_to_path(q)
    file_star = '{}*'.format(q)
    for path_value in glob.glob(os.path.join(ODIN_FS_ROOT, file_star)):
        id_ = os.path.basename(path_value)
        job_loc = os.path.join(path_value, 'main.yml')
        if os.path.exists(job_loc) and os.path.isfile(job_loc):
            job_def = _job_def(id_)
            if job_def:
                job_defs.append(job_def)
    return JobResults(job_defs)


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> JobWrapperDefinition:
    id_ = _convert_to_path(job_id)
    _update_job_repo()
    return JobWrapperDefinition(job=_job_def(id_))


@app.post("/jobs")
def create_job(job_def: JobWrapperDefinition, token: str=Depends(oauth2_scheme)) -> JobWrapperDefinition:
    id_ = _convert_to_path(job_def.job.name)
    new_job_path = _get_job_loc(id_)
    if os.path.exists(new_job_path):
        raise Exception(f"There is already a job at {id}")
    os.makedirs(new_job_path)
    file_to_write = _get_job_file(id_, 'main.yml')
    task_obj = {'tasks': []}
    with open(file_to_write, 'w') as wf:
        yaml.dump(task_obj, wf)
    sha = _add_to_job_repo(file_to_write, "via odin-http create_job")
    LOGGER.info(f'Updated git {sha}')

    updated_job_def = JobDefinition(id=id_,
                                    name=id_,
                                    location=new_job_path,
                                    creation_time=datetime.now())
    return JobWrapperDefinition(job=updated_job_def)


def _to_dict(jid, task):
    """User can put in whatever task name they want, but we will rewrite it"""
    task = task.to_dict()
    task_name = task.get('name')
    task['id'] = f'{jid}--{task_name}'
    return task


@app.put("/jobs/{job_id}")
def update_job(job_id: str, job_def: JobDefinition, token: str=Depends(oauth2_scheme)) -> JobWrapperDefinition:
    id_ = _convert_to_path(job_id)
    tasks = [_to_dict(id_, s) for s in job_def.tasks]
    # compute the id of the tasks if needed

    task_obj = {'tasks': tasks}
    configs = job_def.configs
    for config in configs:
        file_to_write = _get_job_file(id_, config.name)
        with open(file_to_write, 'w') as wf:
            wf.write(config.content)
        _add_to_job_repo(file_to_write, 'via odin-http create_job')

    job_loc = _get_job_loc(id_)
    if os.path.exists(job_loc) is False:
        logging.info('Creating job location {}'.format(job_loc))
        os.makedirs(job_loc)

    file_to_write = _get_job_file(id_, 'main.yml')
    with open(file_to_write, 'w') as wf:
        yaml.dump(task_obj, wf)
    sha = _add_to_job_repo(file_to_write, "via odin-http create_job")
    LOGGER.info(f'Updated git {sha}')
    job_def.tasks = tasks
    return JobWrapperDefinition(job_def)


@app.get("/jobs/{job_id}/files/{filename}")
def download_job_file(job_id: str, filename: str) -> str:
    id_ = _convert_to_path(job_id)
    _update_job_repo()
    return _read_file(_get_job_file(id_, filename))


@app.post("/jobs/{job_id}/files/{filename}")
async def upload_job_file(job_id: str, filename: str, body: Request=Body(..., media_type="application/binary"), token: str=Depends(oauth2_scheme)):
    id_ = _convert_to_path(job_id)
    _validate_filename(filename)
    file_to_write = _get_job_file(id_, filename)

    if os.path.exists(file_to_write):
        logging.warning("Found {}.  Overwriting".format(filename))
    body = await body.body()
    with open(file_to_write, 'wb') as wf:
        wf.write(body)

    sha = _add_to_job_repo(file_to_write, "via odin-http upload_job_file")
    ud = UploadDefinition(location=f'{file_to_write}@{sha}', bytes=os.stat(file_to_write).st_size)
    return ud



