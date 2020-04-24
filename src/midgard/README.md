## Midgard Device Monitoring DaemonSet

### Introduction

On a single node, deep learning practitioners rely heavily on `nvidia-smi`, a GPU monitoring tool from NVIDIA.
Odin is software for compute within a Kubernetes cluster, with a heavy emphasis on GPU-based models.

To achieve an `nvidia-smi`-like capability, it makes sense to provide a REST service that can live on each
node within the cluster and respond back to queries from a master service regarding the GPU load on
that individual node.  The master service can then aggregate these results to provide a global view
into cluster resources.

Midgard provides the node-level REST service that exposes GPU load via NVML (its python wrapper) to
a master service (odin-http)

### Details

NVML is used by `nvidia-smi` to render its output and all of the statistics that are available to it
are exposed within NVML's API.  To see a list of the supported operations, see this file:

https://github.com/gpuopenanalytics/pynvml/blob/master/help_query_gpu.txt

### Running with Docker

To run with docker, you *must* use `nvidia-docker`:

```
$ docker build -t midgard_server .
...
$ nvidia-docker run -p 29999:29999 midgard_server
The swagger_ui directory could not be found.
    Please install connexion with extra install: pip install connexion[swagger-ui]
    or provide the path to your local installation by passing swagger_path=<your path>

The swagger_ui directory could not be found.
    Please install connexion with extra install: pip install connexion[swagger-ui]
    or provide the path to your local installation by passing swagger_path=<your path>

 * Serving Flask app "__main__" (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on http://0.0.0.0:29999/ (Press CTRL+C to quit)
```
