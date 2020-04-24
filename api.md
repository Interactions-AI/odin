## Odin REST API

The Odin REST API currently communicates with the odin engine over web sockets.
It mostly acts as a proxy server for processing queries, but it also manages the
configuration of jobs using git. Currently, whenever a processing request is
made or whenever a job is configured, the git repository is updated. Whenever
a job configuration is modified, the git repository is synchronized.

### Authentication and Users

To manage resources, Odin needs the concept of users.  User are managed as part of the API with typical CRUD requests


### Authentication

To do any mutable requests to the server, you must first authenticate.
To get a JWT token, execute the following command:

```
TOKEN=$(curl -s -X POST -H 'Accept: application/json' -H 'Content-Type: application/json' --data '{"username":"{username}","password":"{password}"}' http://localhost:9003/v1/auth | jq -r '.message')
```

This will yield a `$TOKEN` variable that you should pass into the HTTP headers for each `POST`, `PUT` or `DELETE` query.  You can pass this into cURL like this:

```
-H "Authorization: Bearer ${TOKEN}"
```

There is a CLI for authentication yielding a JWT token, though commands support authenticating as-needed.
This command uses the username on the local machine as the default username

```
(raven-nlu) dpressel@dpressel:~/dev/work/raven/ml/src/odin$ odin-auth
odin password: ********                                                                                                                      
eyJ0eX...J9.eyJp..._8
```

#### Get a User definition from the server

**GET /users/{username}**

Give back a user with this username

```
curl http://0.0.0.0:9003/v1/users/dpressel
{
  "user": {
    "firstname": "daniel",
    "lastname": "pressel",
    "username": "dpressel"
  }
}

```

**GET /users?q={pattern}**

```
curl http://0.0.0.0:9003/v1/users?q=dpr
{
  "users": [
    {
      "firstname": "daniel",
      "lastname": "pressel",
      "username": "dpressel"
    }
  ]
}
```

#### Create a new user on the server

To do this, you should already have authenticated with another user

```
curl -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" --request POST --data '{"user": {"username": "{username}", "firstname": "{firstname}", "lastname": "{lastname}", "password": "{password}"}}' http://localhost:9003/v1/users
{
  "user": {
    "firstname": "{firstname}",
    "lastname": "{lastname}",
    "username": "{username}"
  }
}
```

There is a command in the CLI that does this for you:

```
odin-user --username {username} --firstname {firstname} --lastname {lastname} --password {password}
Created new user
{"user": {"firstname": "{firstname}", "username": "{username}", "lastname": "{lastname}"}}
```

If you do not pass in the password, you will be prompted for it (recommended)

#### Updating a user on the server

To do this, you should already have authenticated with a user

```
curl -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" --request PUT --data '{"username": "dpressel", "firstname": "daniel", "lastname": "pressel"}' http://localhost:9003/v1/users/dpressel
{
  "user": {
    "firstname": "daniel",
    "lastname": "pressel",
    "username": "dpressel"
  }
}
```


There is a command in the CLI that does this for you:

```
odin-user --username {username} --firstname {firstname} --lastname {lastname} --password {password}
Created new user
{"user": {"firstname": "{firstname}", "username": "{username}", "lastname": "{lastname}"}}
```

If you do not pass in the password, you will be prompted for it (recommended)


#### Deleting a user on the server

To do this, you should already have authenticated with another user:

```
curl -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" --request DELETE http://localhost:9003/v1/users/{username}
{
  "user": {
    "username": "{username}"
  }
}
```


### Job

A `Job` is a Directed Acyclic Graph (DAG) of compute `Task`s. It is defined on the server by a `main.yml` inside a directory with the same name as the `Job`, along with any auxiliary files that are required for each `Task` of processing. On the filesystem, a pipeline directory might look like this:

```
(tf) dpressel@dpressel:~/dev/work/raven/ml$ ls -l /data/jobs/sst2
total 12
-rw-r--r-- 1 dpressel dpressel 225 Aug  9 15:41 after.yml
-rw-r--r-- 1 dpressel dpressel 978 Jun 18 10:21 main.yml
-rw-r--r-- 1 dpressel dpressel 495 Jun 18 10:21 sst2.yml
(tf) dpressel@dpressel:~/dev/work/raven/ml$

```

#### Creating a Job on the server

To create a Job on the server, send a message with the name

```
$ curl -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" --request POST --data '{"job": {"name": "danisprettyawesome" }}' http://localhost:9003/v1/jobs
{
  "creationTime": "2019-10-14T13:09:23.770979Z",
  "id": "danisprettyawesome",
  "location": "/data/pipelines/danisprettyawesome",
  "name": "danisprettyawesome"
}
```

To create a Job on the server underneath a sub-directory, use the `__` delimiter to delimit the path:

```

curl -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" --request POST --data '{"job": {"name": "dpressel__danisprettyawesome" }}' http://localhost:9003/v1/jobs
{
  "creationTime": "2019-10-14T13:11:38.738876Z",
  "id": "dpressel/danisprettyawesome",
  "location": "/data/pipelines/dpressel/danisprettyawesome",
  "name": "dpressel/danisprettyawesome"
}

```


#### Get a Job definition from the server

**GET /jobs/{id}**

We can query the `Job` with the rest API using the name of that pipeline directly:

```
curl -X GET http://0.0.0.0:9003/v1/jobs/sst2
{
  "job": {
    "configs": [
      {
        "content": "batchsz: 50\nbasedir: sst2\npreproc: \n  mxlen: 100\n  rev: false\n  clean: true\nbackend: tensorflow\ndataset: SST2\nloader: \n  reader_type: default\nunif: 0.25\nmodel: \n  model_type: default\n  filtsz: [3,4,5]\n  cmotsz: 100\n  dropout: 0.5\n\nfeatures:\n  - name: word\n    vectorizer:\n      type: token1d\n      transform: baseline.lowercase\n    embeddings:\n      label: w2v-gn\ntrain: \n  epochs: 2\n  optim: adadelta\n  eta: 1.0\n  early_stopping_metric: acc\n  verbose:\n    console: True\n    file: sst2-cm.csv \n\n",
        "id": "/data/pipelines/sst2/sst2.yml",
        "name": "sst2.yml"
      },
      {
        "content": "chores:\n- name: slack\n  type: slack-message\n  parent_details: ^parent\n  webhook: https://hooks.slack.com/services/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\n  template: \"Pipeline ${label} completed.  Executed ${executed}\"\n",
        "id": "/data/pipelines/sst2/after.yml",
        "name": "after.yml"
      }
    ],
    "id": "sst2",
    "location": "/data/pipelines/sst2/main.yml",
    "name": "sst2",
    "tasks": [
      {
        "args": [
          "--basedir",
          "${RUN_PATH}/${TASK_ID}",
          "--config",
          "${WORK_PATH}/${TASK_NAME}.yml",
          "--datasets",
          "${ROOT_PATH}/datasets.yml",
          "--embeddings",
          "${ROOT_PATH}/embeddings.yml",
          "--logging",
          "${ROOT_PATH}/logging.json",
          "--settings",
          "/data/mead-settings.json",
          "--reporting",
          "xpctl",
          "--xpctl:label",
          "${TASK_ID}"
        ],
        "command": "mead-train",
        "id": "sst2--sst2",
        "image": "meadml/mead2-gpu:latest",
        "mounts": {
          "claim": "data-rw-many",
          "name": "data",
          "path": "/data"
        },
        "name": "sst2",
        "numGpus": 1
      },
      {
        "args": [
          "$WORK_PATH/after.yml",
          "--label",
          "$TASK_ID"
        ],
        "command": "odin-chores",
        "depends": "sst2",
        "id": "sst2--after",
        "image": "interactions/odin-ml:latest",
        "mounts": {
          "claim": "data-rw-many",
          "name": "data",
          "path": "/data"
        },
        "name": "after",
        "pullPolicy": "Always"
      }
    ]
  }
}
```

#### Get multiple Job definitions

**GET /jobs?q={substring}**

We can also access all pipelines that match a substring using the `q=pattern` param for `pipelines`:

```
curl -X GET http://0.0.0.0:9003/v1/jobs?q=pj-int
{
  "jobs": [
    {
      "configs": [
        {
          "content": "task: classify\nbasedir: pj-intent\nbackend: tensorflow\ndataset: pj:intent:word\nunif: 0.25\n\nfeatures:\n - name: word\n   vectorizer:\n     type: token1d\n     transform: baseline.lowercase\n     mxlen: 100\n   embeddings:\n     label: w2v-gn\nloader:\n  reader_type: default\n\nmodel:\n  model_type: composite\n  sub: [ConvModel, NBowMaxModel, NBowModel]\n  filtsz: [2,3,4,5,6]\n  cmotsz: 100\n  dropout: 0.5\n\ntrain:\n  batchsz: 50\n  epochs: 60\n  patience: 20\n  decay_type: invtime\n  decay_lr: 0.05\n  optim: adam\n  eta: 0.001\n  early_stopping_metric: acc\n  verbose:\n    console: false\n    file: intents-2-1.csv\n\nexport:\n output_dir: /data/nest/models\n project: pj\n name: intent\n",
          "id": "/data/pipelines/pj-intent/pj-intents-comp-v1.yml",
          "name": "pj-intents-comp-v1.yml"
        },
        {
          "content": "# This is a slightly weird placement because yaml can only use a reference if\n# the anchor comes before it\n\nchores:\n- name: slack\n  type: slack-message\n  parent_details: ^parent\n  webhook: https://hooks.slack.com/services/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\n  template: \"Pipeline ${label} completed.  Executed ${executed}\"\n",
          "id": "/data/pipelines/pj-intent/chores.yml",
          "name": "chores.yml"
        }
      ],
      "id": "pj-intent",
      "location": "/data/pipelines/pj-intent/main.yml",
      "name": "pj-intent",
      "tasks": [
        {
          "args": [
            "--basedir",
            "${RUN_PATH}/${TASK_ID}",
            "--config",
            "${WORK_PATH}/pj-intents-comp-v1.yml",
            "--datasets",
            "${ROOT_PATH}/datasets.yml",
            "--embeddings",
            "${ROOT_PATH}/embeddings.yml",
            "--logging",
            "${ROOT_PATH}/logging.json",
            "--settings",
            "/data/mead-settings.json",
            "--reporting",
            "xpctl",
            "--xpctl:label",
            "${TASK_ID}"
          ],
          "command": "mead-train",
          "id": "intent--train",
          "image": "meadml/mead2-gpu:latest",
          "mounts": {
            "claim": "data-rw-many",
            "name": "data",
            "path": "/data"
          },
          "name": "train",
          "numGpus": 1
        },
        {
          "args": [
            "--config",
            "${WORK_PATH}/intents-comp-v1.yml",
            "--datasets",
            "${ROOT_PATH}/datasets.yml",
            "--logging",
            "${ROOT_PATH}/logging.json",
            "--settings",
            "/data/mead-settings.json",
            "--label",
            "${TASK_ID}",
            "--models",
            "${PIPE_ID}--train",
            "--type",
            "best-of-all",
            "--task",
            "classify",
            "--dataset",
            "pj:intent:word",
            "--data_root",
            "${RUN_PATH}"
          ],
          "command": "odin-export",
          "depends": "train",
          "id": "intent--export",
          "image": "interactions/odin-ml:latest",
          "mounts": {
            "claim": "data-rw-many",
            "name": "data",
            "path": "/data"
          },
          "name": "export",
          "pullPolicy": "Always"
        },
        {
          "args": [
            "$WORK_PATH/chores.yml",
            "--label",
            "$TASK_ID"
          ],
          "command": "odin-chores",
          "depends": "export",
          "id": "pj-intent--chores",
          "image": "interactions/odin-ml:latest",
          "mounts": {
            "claim": "data-rw-many",
            "name": "data",
            "path": "/data"
          },
          "name": "chores"
        }
      ]
    }
  ]
}
```

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

#### Get config files for a Pipeline (Task)

**GET /jobs/{id}/files/{file}**

We can get the auxiliary files directly from the server with a `GET` request.

```
curl -X GET http://0.0.0.0:9003/v1/jobs/sst2/files/after.yml
chores:
- name: slack
  type: slack-message
  parent_details: ^parent
  webhook: https://hooks.slack.com/services/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
  template: "Pipeline ${label} completed.  Executed ${executed}"
```

#### Updating an existing Job


We update a job using a JSON message to the server describing the pipeline.

```
curl -X PUT http://0.0.0.0:9003/v1/jobs/blahblah -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" -d @/home/dpressel/blahblah.json
{
  "job": {
    "configs": [],
    "tasks": [
      {
        "args": [
          "--basedir",
          "/data/${TASK_ID}",
          "--config",
          "${WORK_PATH}/${TASK_NAME}.yml",
          "--datasets",
          "${ROOT_PATH}/datasets.yml",
          "--embeddings",
          "${ROOT_PATH}/embeddings.yml",
          "--logging",
          "${ROOT_PATH}/logging.json",
          "--settings",
          "/data/mead-settings.json",
          "--reporting",
          "xpctl",
          "--xpctl:label",
          "${TASK_ID}"
        ],
        "command": "mead-train",
        "depends": null,
        "id": "blahblah--sst2",
        "image": "meadml/mead2-gpu:latest",
        "inputs": null,
        "mounts": [
          {
            "claim": "data-rw-many",
            "name": "data",
            "path": "/data"
          }
        ],
        "name": "sst2",
        "node_selector": null,
        "num_gpus": 1,
        "num_workers": null,
        "outputs": null,
        "pull_policy": null,
        "resource_type": null
      }
    ]
  }
}
```

#### Update config files on the server for a Job (Task)

**POST /jobs/{id}/files/{file}**

We can also update the server files by doing a POST

```
curl -x POST http://0.0.0.0:9003/v1/jobs/blahblah/files/after.yml -H "Content-Type: text/plain" -H "Authorization: Bearer ${TOKEN}" --data-binary @dans.yml
{
  "bytes": 225,
  "location": "/data/pipelines/blahblah/after.yml@cf84f00c509b90a993e04bc8b47bd4f8371a2b1b"
}
```

### Pipeline

A `Pipeline` in the Odin API is defined as a running instance of a `Job`. Each running pipeline has a unique identifier prefixed by the `Job` name.

We can launch a pipeline using a `POST` command to the `pipeline/{ID}` endpoint:

#### Launch an Odin Pipeline

**POST /pipeline**

You need to authenticate with JWT in order to hit a POST endpoint

```
curl -H "Content-Type: application/json" -H "Authorization: Bearer ${TOKEN}" --request POST --data '{"pipeline": {"job": "sst2"}}' http://localhost:9003/v1/pipelines
{
  "pipeline": {
    "id": "sst2--tbvvcmrj",
    "job": "sst2",
    "name": "sst2--tbvvcmrj"
  }
}
```

#### Get the status of a Pipeline

**GET /pipelines/{pipeline_id}**

We can see a `Pipeline` that is running by giving the unique `Pipeline` ID

```
curl -X GET http://0.0.0.0:9003/v1/pipelines/sst2-aydom9-wiyj
{
  "pipeline": {
    "id": "sst2-aydom9-wiyj",
    "name": "sst2-aydom9-wiyj",
    "status": "RUNNING",
    "submitTime": "2019-08-08T23:32:50.900000",
    "tasks": [
      {
        "command": "mead-train",
        "id": "sst2-aydom9-wiyj--sst2",
        "image": "meadml/mead2-gpu:latest",
        "name": "sst2",
        "resourceId": "sst2-aydom9-wiyj--sst2",
        "resourceType": "Pod",
        "status": "executing",
        "submitTime": "2019-08-08T23:32:51.244000",
        "task": "sst2-aydom9-wiyj--sst2"
      },
      {
        "command": "odin-chores",
        "id": "sst2-aydom9-wiyj--after",
        "image": "interactions/odin-ml:latest",
        "name": "after",
        "resourceType": "Pod",
        "status": "waiting",
        "task": "sst2-aydom9-wiyj--after"
      }
    ]
  }
}
```

#### Get the status of multiple Pipelines

**GET /pipelines?q={substring}**

We can also query pipelines matching a substring with `/pipelines?q=query`:

```
curl -X GET http://0.0.0.0:9003/v1/pipelines?q=sst2-aydom9
{
  "pipelines": [
    {
      "id": "sst2-aydom9-wiyj",
      "name": "sst2-aydom9-wiyj",
      "status": "RUNNING",
      "submitTime": "2019-08-08T23:32:50.900000",
      "tasks": [
        {
          "command": "mead-train",
          "id": "sst2-aydom9-wiyj--sst2",
          "image": "mead/mead2-gpu:latest",
          "name": "sst2",
          "resourceId": "sst2-aydom9-wiyj--sst2",
          "resourceType": "Pod",
          "status": "executing",
          "submitTime": "2019-08-08T23:32:51.244000",
          "task": "sst2-aydom9-wiyj--sst2"
        },
        {
          "command": "odin-chores",
          "id": "sst2-aydom9-wiyj--after",
          "image": "interactions/odin-ml:latest",
          "name": "after",
          "resourceType": "Pod",
          "status": "waiting",
          "task": "sst2-aydom9-wiyj--after"
        }
      ]
    }
  ]
}
```
#### Get Data for a Task Resource

**GET /resources/{task_id}/data**

This call gives us back the information stored in the jobs database
for a given resource.  The query can be made both on Tasks (the children
of a pipeline), as well as the Pipeline name itself.

Querying the child resource (Task):

```
curl -X GET http://0.0.0.0:9003/v1/resources/sst2-aydom9-wiyj--sst2/data
{
  "jobs": {
    "_id": {
      "$oid": "5d4cb123abea11e8d49f5fcf"
    },
    "args": [
      "--basedir",
      "/data/sst2-aydom9-wiyj--sst2",
      "--config",
      "/data/pipelines/sst2/sst2.yml",
      "--datasets",
      "/data/pipelines/datasets.yml",
      "--embeddings",
      "/data/pipelines/embeddings.yml",
      "--logging",
      "/data/pipelines/logging.json",
      "--settings",
      "/data/mead-settings.json",
      "--reporting",
      "xpctl",
      "--xpctl:label",
      "sst2-aydom9-wiyj--sst2"
    ],
    "command": "mead-train",
    "image": "meadml/mead2-gpu:latest",
    "inputs": null,
    "label": "sst2-aydom9-wiyj--sst2",
    "name": "sst2",
    "node_selector": null,
    "num_gpus": 1,
    "outputs": null,
    "parent": "sst2-aydom9-wiyj",
    "pull_policy": "IfNotPresent",
    "resource_id": "sst2-aydom9-wiyj--sst2",
    "resource_type": "Pod",
    "submit_time": {
      "$date": 1565307171244
    }
  },
  "success": true
}

```

Querying the parent Pipeline:

```
curl -X GET http://0.0.0.0:9003/v1/resources/sst2-aydom9-wiyj/data
{
  "jobs": {
    "_id": {
      "$oid": "5d4cb123abea11e8d49f5fce"
    },
    "completion_time": null,
    "executed": [],
    "executing": [
      "sst2-aydom9-wiyj--sst2"
    ],
    "jobs": [
      "sst2-aydom9-wiyj--sst2",
      "sst2-aydom9-wiyj--after"
    ],
    "label": "sst2-aydom9-wiyj",
    "status": "RUNNING",
    "submit_time": {
      "$date": 1565307170900
    },
    "waiting": [
      "sst2-aydom9-wiyj--after"
    ]
  },
  "success": true
}
```



#### Get Kubernetes Events for a Task Resource

**GET /resources/{task_id}/events**

Sometimes its useful to be able to see granular kubernetes events that occurred within Odin. You can get these by accessing the underlying resource. In the example `Pipeline` above we can see the `resource` identified for a particular task:

```
      "tasks": [
        {
          "command": "mead-train",
          "id": "sst2-aydom9-wiyj--sst2",
          "image": "meadml/mead2-gpu:latest",
          "name": "sst2",
          "resourceId": "sst2-aydom9-wiyj--sst2",
          "resourceType": "Pod",
          "status": "executing",
          "submitTime": "2019-08-08T23:32:51.244000",
     -->  "task": "sst2-aydom9-wiyj--sst2"
```

We can query that resource like this:

```
curl -X GET http://0.0.0.0:9003/v1/resources/sst2-aydom9-wiyj--sst2/events
{
  "events": [
    {
      "eventType": "Normal",
      "id": "evt-sst2-aydom9-wiyj--sst2-0",
      "message": "Back-off pulling image \"meadml/mead2-gpu:latest\"",
      "reason": "BackOff",
      "source": "kubelet,dpressel",
      "timestamp": "2019-08-16T06:24:10+00:00"
    },
    {
      "eventType": "Warning",
      "id": "evt-sst2-aydom9-wiyj--sst2-1",
      "message": "Error: ImagePullBackOff",
      "reason": "Failed",
      "source": "kubelet,dpressel",
      "timestamp": "2019-08-16T06:29:06+00:00"
    }
  ]
}
```

#### Kill an Odin Pipeline

**DELETE /pipeline/{job_id}**

We can kill the job with a `DELETE` to the `/pipeline/{ID}` endpoint:

```
curl -X DELETE http://0.0.0.0:9003/v1/pipeline/sst2-badoz-37xqj
[
  {
    "cleanedFromK8s": "No",
    "purgedFromDb": "No",
    "removedFromFs": "No",
    "taskId": "sst2-badoz-37xqj"
  },
  {
    "cleanedFromK8s": "Yes",
    "purgedFromDb": "No",
    "removedFromFs": "No",
    "taskId": "sst2-badoz-37xqj--sst2"
  }
]
```

We can remove the job from the jobs db or the file system with the approperatie query params (`db` and `fs` respectivly).

```
curl -X DELETE http://0.0.0.0:9003/v1/pipeline/sst2-badoz-37xqj?db=True
[
  {
    "cleanedFromK8s": "No",
    "purgedFromDb": "Yes",
    "removedFromFs": "No",
    "taskId": "sst2-badoz-37xqj"
  },
  {
    "cleanedFromK8s": "Yes",
    "purgedFromDb": "Yes",
    "removedFromFs": "No",
    "taskId": "sst2-badoz-37xqj--sst2"
  }
]
```

```
curl -X DELETE http://0.0.0.0:9003/v1/pipeline/sst2-badoz-37xqj?db=True&fs=True
[
  {
    "cleanedFromK8s": "No",
    "purgedFromDb": "Yes",
    "removedFromFs": "Yes",
    "taskId": "sst2-badoz-37xqj"
  },
  {
    "cleanedFromK8s": "Yes",
    "purgedFromDb": "Yes",
    "removedFromFs": "Yes",
    "taskId": "sst2-badoz-37xqj--sst2"
  }
]
```

#### Getting node info

**GET /nodes**

Get info about a node including its current GPU utilization

```
curl http://localhost:9003/v1/nodes 
{
  "nodes": [
    {
      "cpu": "12",
      "ephemeral-storage": "959863856Ki",
      "gpus": [
        {
          "applicationsClocks": {
            "memClock": "N/A",
            "unit": "MHz"
          },
          "clocks": {
            "memClock": 405,
            "unit": "MHz"
          },
          "computeMode": "Default",
          "eccMode": {
            "currentEcc": "N/A",
            "pendingEcc": "N/A"
          },
          "fbMemoryUsage": {
            "free": 7952.25,
            "total": 7952.3125,
            "unit": "MiB",
            "used": 0.0625
          },
          "id": "0000:01:00.0",
          "maxClocks": {
            "smClock": 2100,
            "unit": "MHz"
          },
          "minorNumber": "0",
          "pci": {
            "pciBusId": "0000:01:00.0"
          },
          "performanceState": "P8",
          "powerReadings": {
            "defaultPowerLimit": "N/A",
            "maxPowerLimit": "N/A",
            "minPowerLimit": "N/A",
            "powerDraw": 3.73,
            "powerLimit": "N/A",
            "powerManagement": "N/A",
            "powerState": "P8",
            "unit": "W"
          },
          "productBrand": "GeForce",
          "productName": "GeForce RTX 2080 with Max-Q Design",
          "serial": "N/A",
          "temperature": {
            "gpuTemp": 49,
            "gpuTempMaxThreshold": 99,
            "gpuTempSlowThreshold": 94,
            "unit": "C"
          },
          "utilization": {
            "gpuUtil": 0,
            "memoryUtil": 0,
            "unit": "%"
          },
          "uuid": "GPU-1b9a3804-64b6-3c05-cbb2-757cc8907437"
        }
      ],
      "host": "dpressel",
      "hugepages-1Gi": "0",
      "hugepages-2Mi": "0",
      "internalIP": "192.168.7.57",
      "memory": "32779324Ki",
      "nvidia.com/gpu": "1",
      "pods": "110"
    }
  ]
}
```
