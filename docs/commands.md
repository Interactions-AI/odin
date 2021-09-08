## Odin Commands 

Most Odin commands use the [REST API](api.md) to communicate.  A few use web sockets.


### Authentication and Users

To manage resources, Odin needs the concept of users.  User are managed as part of the API with typical CRUD requests


### Authentication

To do any mutable requests to the server, you must first authenticate.
To get a JWT token, execute the following command:

```
$ odin-auth
odin password: ********                                                                                                                      
eyJ0eX...J9.eyJp..._8
```

The JWT token will be cached on your system and you wont be prompted again until it expires

### Job

A `Job` is a Directed Acyclic Graph (DAG) of compute `Task`s. It is defined on the server by a `main.yml` inside a directory with the same name as the `Job`, along with any auxiliary files that are required for each `Task` of processing. On the filesystem, a pipeline directory might look like this:

```
$ ls -l /data/jobs/sst2
total 12
-rw-r--r-- 1 dpressel dpressel 225 Aug  9 15:41 after.yml
-rw-r--r-- 1 dpressel dpressel 978 Jun 18 10:21 main.yml
-rw-r--r-- 1 dpressel dpressel 495 Jun 18 10:21 sst2.yml
$

```

#### Creating and updating a Job on the server

An easy way to create a job on the server is to use git to push it.  If you already have a job, its also possible to use the API, or `odin-push` to do this:

```
$ odin-push <job-name> <local-file>
```

This will push the local file up to odin workspace for that job.  If you wish to push a new job, pass `-c` to `odin-push` to create the job


#### Get a Job definition from the server

There is not currently a command-line for getting the job definition from the Odin server.  You can either use the [API](api.md) or if this is a git-backed
job, you can look at the files in git.

### Task

A `Task` is one processing task within a `Job`. This might be something like training a deep learning job with `mead-train`, for instance.
Each `Task` in the processing `Job` might have its own set of configuration files within the pipeline directory location. For example,
in the above example, the `sst2.yml` is a mead config that is run by multiple compute tasks in the graph. Here is the relevant fragment of the pipeline definition:

```
tasks:

 - name: sst2
   image: *mead-gpu
   command: mead-train
   args:
    - "--basedir"
    - "/data/${TASK_ID}"
    - "--config"
    - "${WORK_PATH}/${TASK_NAME}.yml"
    - "--datasets"
    - "${ROOT_PATH}/datasets.yml"
    - "--embeddings"
    - "${ROOT_PATH}/embeddings.yml"
    - "--logging"
    - "${ROOT_PATH}/logging.json"
    - "--settings"
    - "/data/mead-settings.json"
    - "--reporting"
    - "xpctl"
    - "--xpctl:label"
    - "${TASK_ID}"
   mount:
      name: data
      path: "/data"
      claim: *claim_name
   num_gpus: 1

```

You can see that Odin has some pre-defined variables that allow it to refer to the pipeline location (`${WORK_PATH}`) and the task name (`${TASK_NAME}`) which, together, reference the `sst2.yml` file. That file looks like this:

```
batchsz: 50
basedir: sst2
preproc:
  mxlen: 100
  rev: false
  clean: true
backend: tensorflow
dataset: SST2
loader:
  reader_type: default
...
```

### Launch an Odin Pipeline

A `Pipeline` in the Odin API is defined as a running instance of a `Job`. Each running pipeline has a unique identifier prefixed by the `Job` name.

We can launch a pipeline using 

```
odin-run <job-name>
```

You need to authenticate in order to hit this endpoint.  If you have a valid JWT token, that will automatically be used, otherwise, you will be prompted for your password in odin.  Note that if your local machine username is different from the username in odin, you may need to pass your `--username`
A handle to the job will be returned if the command completes.  This handle can be used to check status and logs of jobs. 

#### Get the status of a Pipeline

We can see a `Pipeline` that is running by giving the unique `Pipeline` ID

```
odin-status <pipeline-id>
```

When `odin-status` is run, it will print the status of each step in the execution graph.   The subtasks are delimited by a `--`.
To get logs or data for a specific step, use these names, which we will refer to here as `<task-id>`.

#### Get Data for a Task Resource

You can see the data associated with any Odin pipeline or task using `odin-data`.  If you pass a `<pipeline-id>` you will see the meta-data about the actual running pipeline, not the detail for each steps.  If you want to see a specific step, pass the `<task-id>`

```
odin-data <pipeline-id>
odin-data <task-id>
```

#### Get Kubernetes Events for a Task Resource

You can see the Kubernetes events associated with a task using `odin-events`

```
odin-events <task-id>
```

If you have `kubectl` set up on the cluster, you can also use the usual Kubernetes command for this:

```
kubectl describe <resource_type> <task-id>
```

#### Getting Log output for a Task

To see log info for a task, use `odin-logs`

```
odin-logs <task-id>
```

If your resource type is Pod, this is equivalent to

```
kubectl logs <task-id>
```

#### Kill an Odin Pipeline

To kill an Odin Pipeline, run `odin-cleanup`.  If you also would like to remove the workspace (filesystem) for that execution, pass `-f`.

```
odin-cleanup (-f) <pipeline-id>
```

#### Getting GPU info

To see what GPUs are utilized in the cluster:

```
odin-gpus
```

