# Odin
## About

Odin, a lightweight framework for automating machine learning workflows with Kubernetes.  The codebase is compact and efficient, designed to orchestrate and run ML workflows,  and support parallel execution of pipeline steps using a simple Git-backed configuration to describe processing pipelines.  Odin provides a simple API for launching and monitoring jobs and resources over a cluster. It is a minimalistic effort, built under the DRY philosophy, and it relies on industrial strength tools such as  Git, PostgreSQL and Kubernetes underneath. It also optionally supports commonly used Kubernetes operators for distributed training including a la carte operators provided by the Kubeflow and PyTorch Elastic projects, to make it easy to train across multiple devices or machines.  It can be run in Google Kubernetes Engine in the cloud, or on local Kubernetes clusters, providing a simple and unified interface for scheduling ML jobs.

We built Odin with simplicity and reproducibility in mind. You define your workflows declaratively in a compact YAML configuration language and submit them to Odin with a single command or HTTP request. Training machine learning models at scale is already challenging, the tooling for running these jobs should be as simple and transparent as possible. Odin is completely written in Python and communicates with Kubernetes using the official API.  It is very hackable too -- the code provides a native Python tier, allowing developers to embed the graph executor directly.  It also provides a thin, lightweight WebSocket tier which allows the development of alternative sub-systems from other programming languages. Finally, it offers a simple HTTP layer that provides full access to user, job and pipeline management, all defined. We also have Python client code for HTTP and WebSockets to make integration straightforward at any level.

## Design

### Odin Core

At the lowest level, the core of Odin provides Python code for embedding a directed acyclic graph (DAG) scheduler in python to orchestrate containers via the Kubernetes API.  There are several supported resources, including Pods and Jobs, as well as operators from KubeFlow such as PyTorch operator and TensorFlow operators.  We also support PyTorch Elastic operators as a resource.  These resources can be orchestrated via a simple YAML file, and each step in the pipeline has access to the Odin Data store, which can be either MongoDB or Postgres-backed.

While the core code is all written in Python, we wanted to provide an agnostic interface for scheduling to higher layers, facilitating polyglot architectures handling the more advanced system services such as user management, resource access, and Restful APIs.  To enable higher level building blocks from the core, we provide a very simple WebSocket service tier in the core, which makes it easy, for example, to write a node.js server that can access the core functionality, while providing higher level management functions.

### Midgard and Odin HTTP

*HTTP API*

The HTTP API for Odin provides a Restful interface to user and resource management with JWT authentication.  This layer extends the base with a Postgres user database and user management functionality, as well as a documented [API](docs/api.md) for scheduling worfklows within Odin.  Additionally, the web service tier is git-backed making it easy to communicate pipeline updates via 3rd party tooling while at the same time ensuring an industrial grade versioning system for pipelines that can connect easily with CI/CD solutions.

*Midgard*

The midgard DaemonSet, provides node level information concerning devices like GPUs as well as system resources to the HTTP API which aggregates this information and makes it available as a central service that can be queried within the cluster.  This information makes it easy to get cluster-level granular information including information that would normally be retrieved on single systems using `nvidia-smi`

## Setup

There are [sample setup configs](https://github.com/Interactions-AI/sample-odin-configs) and a detailed tutorial for
[setting up Odin from scratch on microk8s](https://github.com/Interactions-AI/sample-odin-configs/blob/main/docs/odin-from-scratch.md)

