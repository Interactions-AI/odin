# Odin
## About

Odin, a lightweight framework for automating machine learning workflows with [Kubernetes](https://kubernetes.io/).  The codebase is compact and efficient, and is designed to orchestrate and run ML workflows with a simple Git-backed configuration to describe processing pipelines.  Odin provides a simple API for launching and monitoring jobs and resources over a cluster. It is a minimalistic effort, built under the DRY philosophy, and it relies on industrial strength tools such as  Git, PostgreSQL and Kubernetes underneath. It also optionally supports (but does not require) commonly used Kubernetes operators for distributed training including a la carte operators provided by the [Kubeflow](https://www.kubeflow.org/) and [PyTorch Elastic](https://github.com/pytorch/elastic) projects, to make it easy to train across multiple devices or machines.  It can be run in [Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine/) in the cloud, or on local Kubernetes clusters, providing a simple and unified interface for scheduling ML jobs.

We built Odin with simplicity and reproducibility in mind. You define your workflows declaratively in a compact YAML configuration language and submit them to Odin with a single command or HTTP request. Training machine learning models at scale is already challenging, the tooling for running these jobs should be as simple and transparent as possible. Odin is completely written in Python and communicates with Kubernetes using the official API.  It is very hackable too -- the code provides a native Python tier, allowing developers to embed the graph executor directly.  It also provides a thin, lightweight WebSocket tier which allows the development of alternative sub-systems from other programming languages. Finally, it offers a simple HTTP layer that provides full access to user, job and pipeline management, all defined. We also have Python client code for HTTP and WebSockets to make integration straightforward at any level.

## Design

### Odin Core

At the lowest level, the core of Odin provides Python code for embedding a directed acyclic graph (DAG) scheduler in python to orchestrate containers via the Kubernetes API.  There are several supported resources, and additional [CRDs](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/) can be added by sub-classing.  These resources can be orchestrated via a [simple YAML file](https://github.com/dpressel/sample-odin-pipelines/blob/main/bert-ner/main.yml), and each step in the pipeline has access to the Odin Data store, which can be either [MongoDB](https://www.mongodb.com/) or [PostgreSQL](https://www.postgresql.org/) backed.

While the core code is all written in Python, we wanted to provide an agnostic interface for scheduling to higher layers, facilitating polyglot architectures handling the more advanced system services such as user management, resource access, and Restful APIs.  To enable higher level building blocks from the core, we provide a very simple [WebSocket](https://en.wikipedia.org/wiki/WebSocket) service tier in the core, which makes it easy, for example, to write a node.js server that can access the core functionality, while providing higher level management functions.

### Midgard and Odin HTTP

*HTTP API*

The HTTP API for Odin provides a Restful interface to user and resource management with JWT authentication.  This layer extends the base with a Postgres user database and user management functionality, as well as a documented [API](docs/api.md) for scheduling worfklows within Odin.  Additionally, the web service tier is git-backed making it easy to communicate pipeline updates via 3rd party tooling while at the same time ensuring an industrial grade versioning system for pipelines that can connect easily with CI/CD solutions.

*Midgard*

The midgard [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/), provides node level information concerning devices like GPUs as well as system resources to the HTTP API which aggregates this information and makes it available as a central service that can be queried within the cluster.  This information makes it easy to get cluster-level granular information including information that would normally be retrieved on single systems using `nvidia-smi`

### Integrating with a metrics service

Odin has been used as a framework for both large-scale training jobs within Interactions and autoML where a set of hyper-parameters are explored and logged via a metrics server.  While in theory, any metrics server that can log and retrieve results from experiments for a given run would work, [xpctl](https://github.com/mead-ml/xpctl) is a service that is known to work well within the Odin ecosystem.  It is an extensible, task-level metric service that (like Odin) is Mongo or Postgres-backed, provides a simple HTTP API for logging and retrieving experiments, and is containerized with images on Dockerhub.

We will add more documentation on using a metrics service for continuous deployment and autoML in the near future.

## Setup

There are [sample setup configs](https://github.com/Interactions-AI/sample-odin-configs) and a detailed tutorial for
[setting up Odin from scratch on microk8s](https://github.com/Interactions-AI/sample-odin-configs/blob/main/docs/odin-from-scratch.md)

