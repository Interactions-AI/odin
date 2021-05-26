# Pipelines in Odin

## Pipeline

- `name` (string name of this pipeline)
- `tasks` (list of `Task`s)

A pipeline is described with a YAML file specifying a set of tasks to execute, and is contained in its own directory under the name `main.yml`.

The pipeline will typically list a string name (normally the same as the directory above it) which will be used to prefix all of its tasks.

The tasks are execution steps which may be in executed parallel or serial depending on there list of dependencies.  To specify that a task is dependent on another task, the name of the dependency should be listed in the `depends` field.

This will tell the scheduler to execute the dependency task prior to the dependent task.


## Task descriptor

- `name` - a name for this task (which should be used to refer to it from other dependents).  This is used also to name the executing pod (along with the pipeline `name`)
- `image` - the image name to pull and execute from.  For instance, `meadml/mead2-pytorch-cuda11:latest` refers to the Dockerhub MEAD2 pytorch image
- `command` - the command to call within the container we are executing
- `args` - a list of command line arguments to `command`
- `mounts` - An optional list of volumes to access from the running command
  - `claim` - The PVC name for our mount
  - `name` - A name for this mount
  - `path` - The virtual path we see from inside the container (often set to `/data`)
  - `secrets` - An optional list of secrets if required for this task
  - `config_maps` - An optional list of config_maps if required for this task
  - `num_gpus` - For a single worker image, the number of GPUs required.  This should be ignored for multi-worker jobs, as these use `num_workers`
  - `pull_policy` - A string policy for the container, commonly `IfNotPresent` or `Always`.
  - `node_selector` - An optional dictionary of key-values used to specify on which node we should execute.
  - `resource_type` - The top of resource we wish to execute.  This defaults to `Pod`, but other valid values include `TFJob`, `PyTorchJob`, `ElasticJob`, `MPIJob` and `Job`.  For multi-worker, multi-GPU configurations this is usually one of the `*Job` resources, otherwise `Pod` is most common
  - `inputs` - An optional way to enumerate the inputs expected for this task
  - `outputs` - An otpional way to enumerate the outputs expected for this task

## Processing variables

- `${RUN_PATH}` - when a pipeline launches, a new job is created with its own workspace.  This variable allows the users to reference the job path from within the pipeline `main.yml`
- `${TASK_ID}` - when a task is run from a job, it is given a task identifier.  This varialbe allows the users to reference this id from within the pipeline `main.yml`
- `${ROOT_PATH}` - This variable refers to the pipelines root directory (where all the pipelines are cloned in the server)
- `${WORK_PATH}` - This variable refers to the specific running pipeline's configuration directory

## Git-backed repositories

The typical approach to pipeline management is to use a git repository as the backend.  The `odin-http` server will automatically sync that repository when it runs, so its possible to add a new pipeline simply by adding it to the Git repository (and pushing to the remote).

The `odin_push` command can be used to sync resources to the git repository, or git commands can be used directly

## Task-related resources

Its common that running tasks may require external configuration resources, like files.  These would commonly be stored inside the pipeline directory along with the `main.yml`.  For example, in this pipeline, we have an additional YAML file which is used by the task to run a training job:

https://github.com/dpressel/sample-odin-pipelines/tree/main/bert-ner

The `main.yml` references the PVC where the pipelines exist in the `mount` section, and referencs the config file via the `--config` option:

```
   command: mead-train
   args:
    - "--basedir"
    - "${RUN_PATH}/${TASK_ID}"
    - "--config"
    - "${WORK_PATH}/conll-bert.yml"
    - "--logging"
    - "${ROOT_PATH}/logging.json"
   mount:
      name: data
      path: "/data"
      claim: *claim_name
```

For this particular command, `--basedir` also specifies a place where logs and checkpoints are stored, and here the descriptor uses the processor variables to specify the output workspace location.
