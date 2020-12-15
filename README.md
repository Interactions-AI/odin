# Odin
## About

Odin, a lightweight framework for automating machine learning workflows.  The codebase is compact and efficient, designed to orchestrate and run ML workflows,  and support parallel execution of pipeline steps using a simple Git-backed configuration to describe processing pipelines.  Odin provides a simple API for launching and monitoring jobs and resources over a cluster. It is a minimalistic effort, built under the DRY philosophy, and it relies on industrial strength tools such as  Git, PostgreSQL and Kubernetes underneath. It also optionally supports commonly used Kubernetes operators for distributed training including a la carte operators provided by the Kubeflow and PyTorch Elastic projects, to make it easy to train across multiple devices or machines.  It can be run in Google Kubernetes Engine in the cloud, or on local Kubernetes clusters, providing a simple and unified interface for scheduling ML jobs.

We built Odin with simplicity and reproducibility in mind. You define your workflows declaratively in a compact YAML configuration language and submit them to Odin with a single command or HTTP request. Training machine learning models at scale is already challenging, the tooling for running these jobs should be as simple and transparent as possible. Odin is completely written in Python and communicates with Kubernetes using the official API.  It is very hackable too -- the code provides a native Python tier, allowing developers to embed the graph executor directly.  It also provides a thin, lightweight WebSocket tier which allows the development of alternative sub-systems from other programming languages. Finally, it offers a simple HTTP layer that provides full access to user, job and pipeline management, all defined. We also have Python client code for HTTP and WebSockets to make integration straightforward at any level.

## Setup

There are [sample setup configs](https://github.com/Interactions-AI/sample-odin-configs) and a detailed tutorial for
[setting up Odin from scratch on microk8s](https://github.com/Interactions-AI/sample-odin-configs/blob/main/docs/odin-from-scratch.md)

