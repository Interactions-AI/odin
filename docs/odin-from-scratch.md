# Installing Odin from scratch on microk8s on Ubuntu


## Installing Microk8s

Recent versions of microk8s come with everything we need to make installing odin easy

- `host-access` enables us to talk to a DB installed on our local machine
- `gpu` allows us to access our nvidia GPU on the local machine
- `kubeflow` allows access to `TFJob`, `PyTorchJob` and `MPIJob` which are handy for testing
- `registry` gives us access to a local private registry we can use

### Microk8s from scratch

```
$ snap install microk8s --classic
```

Check if its running:

```
$ sudo microk8s.status
microk8s is running
high-availability: no
  datastore master nodes: 127.0.0.1:19001
  datastore standby nodes: none
addons:
  enabled:
    dns                  # CoreDNS
    gpu                  # Automatic enablement of Nvidia CUDA
    ha-cluster           # Configure high availability on the current node
    host-access          # Allow Pods connecting to Host services smoothly
    registry             # Private image registry exposed on localhost:32000
    storage              # Storage class; allocates storage from host directory
  disabled:
    ambassador           # Ambassador API Gateway and Ingress
    cilium               # SDN, fast with full network policy
    dashboard            # The Kubernetes dashboard
    fluentd              # Elasticsearch-Fluentd-Kibana logging and monitoring
    helm                 # Helm 2 - the package manager for Kubernetes
    helm3                # Helm 3 - Kubernetes package manager
    ingress              # Ingress controller for external access
    istio                # Core Istio service mesh services
    jaeger               # Kubernetes Jaeger operator with its simple config
    knative              # The Knative framework on Kubernetes.
    kubeflow             # Kubeflow for easy ML deployments
    linkerd              # Linkerd is a service mesh for Kubernetes and other frameworks
    metallb              # Loadbalancer for your Kubernetes cluster
    metrics-server       # K8s Metrics Server for API access to service metrics
    multus               # Multus CNI enables attaching multiple network interfaces to pods
    prometheus           # Prometheus operator for monitoring and logging
    rbac                 # Role-Based Access Control for authorisation
```

Make sure you have your `gpu` and `host-access` are enabled:
```
$ sudo microk8s.enable gpu
Enabling NVIDIA GPU
NVIDIA kernel module detected
Enabling DNS
Applying manifest
serviceaccount/coredns created
configmap/coredns created
deployment.apps/coredns created
service/kube-dns configured
clusterrole.rbac.authorization.k8s.io/coredns created
clusterrolebinding.rbac.authorization.k8s.io/coredns created
Restarting kubelet
DNS is enabled
Applying manifest
daemonset.extensions/nvidia-device-plugin-daemonset unchanged
NVIDIA is enabled
$ microk8s.enable host-access
Addon host-access is already enabled.

```

You can run without `sudo` if you run

```
sudo usermod -a -G microk8s <username>
```


## Checking up on microk8s

microk8s pods and services are running under the namespace `kube-system`

### Optional: Setting up the Dashboard

There is a dashboard that you can use to view your cluster.  You can set it up like this:

```
$ microk8s.enable dashboard
Applying manifest
serviceaccount/kubernetes-dashboard created
service/kubernetes-dashboard created
secret/kubernetes-dashboard-certs created
secret/kubernetes-dashboard-csrf created
secret/kubernetes-dashboard-key-holder created
configmap/kubernetes-dashboard-settings created
role.rbac.authorization.k8s.io/kubernetes-dashboard created
clusterrole.rbac.authorization.k8s.io/kubernetes-dashboard created
rolebinding.rbac.authorization.k8s.io/kubernetes-dashboard created
clusterrolebinding.rbac.authorization.k8s.io/kubernetes-dashboard created
deployment.apps/kubernetes-dashboard created
service/dashboard-metrics-scraper created
deployment.apps/dashboard-metrics-scraper created
service/monitoring-grafana created
service/monitoring-influxdb created
service/heapster created
deployment.apps/monitoring-influxdb-grafana-v4 created
serviceaccount/heapster created
clusterrolebinding.rbac.authorization.k8s.io/heapster created
configmap/heapster-config created
configmap/eventer-config created
deployment.apps/heapster-v1.5.2 created

If RBAC is not enabled access the dashboard using the default token retrieved with:

token=$(microk8s kubectl -n kube-system get secret | grep default-token | cut -d " " -f1)
microk8s kubectl -n kube-system describe secret $token

In an RBAC enabled setup (microk8s enable RBAC) you need to create a user with restricted
permissions as shown in:
https://github.com/kubernetes/dashboard/blob/master/docs/user/access-control/creating-sample-user.md

$ kubectl port-forward -n kube-system service/kubernetes-dashboard 10443:443

```

Following the instructions above, we can ge the token information and put that into the login for the dashboard:
```
$ token=$(microk8s kubectl -n kube-system get secret | grep default-token | cut -d " " -f1)
$ microk8s kubectl -n kube-system describe secret $token

```

To run the dashboard, you have to have port-forwarding set up as above, and you probably need a browser like Firefox to view that will actually allow you to hit a site with a self-signed cert (Chrome doesnt allow this anymore).

### Optional: Kubeflow on Microk8s

Odin currently supports operators from Kubeflow to execute multi-worker GPU jobs for TensorFlow, PyTorch and MPI with Horovod.  If you need any of these operators, you will need to install KubeFlow.  Note that KubeFlow is not required for non-multi-worker GPU jobs, so it can be skipped in those cases

```
$ sudo microk8s.enable kubeflow
Enabling dns...
Enabling storage...
Enabling dashboard...
Enabling ingress...
Enabling metallb:10.64.140.43-10.64.140.49...
Waiting for DNS and storage plugins to finish setting up
Deploying Kubeflow...

```

### Some convenience items

If you are used to `kubectl`, prefixing it each time with `microk8s` is obnoxious.  To make it easier to work in the environment, you can put this in your `~/.bashrc` (from this point on, I will assume that this is done and refer to `kubectl` without the `microk8s` prefix):

```
alias kubectl='microk8s kubectl'
```


## Setting up PostgreSQL

We are going to need a database to store our jobs and usernames.  Odin
currently supports `mongodb` or `postgres` for the jobs database, but it requires `postgres` for the user database in the HTTP layer.  It is possible to use
only the websocket odin server on a cluster and bypass exposing anything over
HTTP, but for most users, the HTTP will provide a better experience, and gives acess to items like hardware queries using midgard, so in most cases we will need postgres anyhow, so to keep it simple, for this guide we are going to use postgres for both databases. Install postgres on your local system.  Create a user and a password that will have API access to postgres (you can do that with the `createuser` command).

### Enabling PostgreSQL access from Kubernetes Pods

In the previous section, we enabled `host-access`.   This addon makes it easy for a Pod to talk to the local system via a fixed IP address.  The default IP address visible from the Pods is `10.0.1.1`, though you can configure this to be anything you want.

To make this all work, a few changes might be required to your default postgres install.

#### Updating postgresql.conf
First, lets set the listen port to `0.0.0.0` (default to localhost):

This command can be used on linux to locate where your configuration file lives:
```
$ locate postgresql.conf
```
Lets edit this file, and change the `listen_address`:

```
listen_addresses = '0.0.0.0'            # what IP address(es) to listen on;
                                        # comma-separated list of addresses;
```

#### Updating pg_hba.conf
Also, we are going to make a change to the `pg_hba.conf` to make the service available to the subnet for whatever user we created to access our database (you can `locate` this file just as you did the other, though it will most likely live in the same directory)

```
# IPv4 local connections:
host    all             all             127.0.0.1/32            md5
host    all             dpressel        10.0.0.0/8              md5

```

#### Restarting the server

Now we want to restart our server

```
$ sudo service postgresql restart
```

## Installing Odin Locally

We now have our database set up for Odin, but we need a few more things

- A secret for our odin credentials
- A persistent volume and persistent volume claim we can use to access pipelines and save results
- Setting up a pipelines and datasets
- Optional: a local private registry
### Setting up the odin-cred secret


If you are running locally, you should have PostgreSQL set up already.  We are going to need to tell Odin how to access this database.  To do this, we will create a configuration file suitable for accessing the databases we need for Odin, and we will store that in a `secret`.

The configuration should look something like this:

```
jobs_db:
    host: localhost
    passwd: {YOUR_PG_PASSWORD}
    port: 5432
    backend: postgres
    user: {YOUR_PG_USERNAME} 
reporting_db:
    dbhost: localhost
    dbport: 27017
    passwd: {YOUR_REPORTING_PASSWORD}
    user: {YOUR_REPORTING_USERNAME}
    host: "0.0.0.0:31458/v2"
odin_db:
    dbhost: localhost
    dbport: 5432
    passwd: {YOUR_PG_PASSWORD} 
    user: {YOUR_PG_USERNAME}
    # This can be whatever you want
    odin_root_user: {ROOT_ODIN_USER}
    # This can be whatever you want
    odin_root_passwd: {ROOT_ODIN_PASSWORD}

```
This file will get read into a kubernetes `secret` which can be acessed by the odin server
```
kubectl create secret generic odin-cred --from-file=odin-cred.yml=/path/to/odin-cred.yml
```


### Accessing a non-public registry

With Kubernetes up and running, we should have no trouble accessing docker containers that live on Dockerhub or any public docker registry.  However, in many
cases, the docker images we need to access.  Typically they will live within a private registry.

#### Accessing a Private Registry

If you have a private docker registry that you want to acess, you just need to create a secret for that registry with the authentication info that you need to pull from that repository

```
kubectl create secret docker-registry registry --docker-server={registry_server_url} --docker-username={uname} --docker-password={password} --docker-email={your_email}
```
The full process of creating an imagePullSecret is given [here](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)


#### Optional: using a Local Registry

Even if you dont have access to a private registry, with `microk8s` you can set up your own local registry and use that for any containers that you dont want to put into DockerHub.

The local registry for microk8s will live at `localhost:32000` and will store all of the docker images we will use (that are not already on DockerHub).  The local registry is documented in [more detail here](https://microk8s.io/docs/registry-built-in)

```
$ microk8s.enable registry
Enabling the private registry
storage is already enabled
Applying registry manifest
namespace/container-registry created
persistentvolumeclaim/registry-claim created
deployment.apps/registry created
service/registry created
The registry is enabled

```

### Deploying Odin via Docker images

The github repository has a CI/CD github action to automatically publish images to DockerHub:

https://hub.docker.com/u/interactions

When we set up our kubernetes resources in the next section, we will be referencing the repositories from this DockerHub account.

Since we publish our containers to DockerHub, you do not need to build any code, we just need to configure the kubernetes resources on the cluster with YAML descriptors.

### Setting up storage

`microk8s` does have some helpful storage options, but in this example, we are going to create a cluster reference to a drive on our development machine and allow access to that from our odin jobs.

```
k8s/local$ ls
pv  pvc
```

`pv` is the acronym for a persistent volume, and the descriptors here will map some sort of storage onto the cluster.  `pvc` is the acronym for a persistent volume claim, which we will reference to access or volumes from our odin jobs.

For now, we will be creating 2 YAML files in these directories which will be used for our development pipeline and results storage:

```
/k8s/local$ ls pv pvc
data-local.yml

pvc:
data-rw-many.yml
```

#### PersistentVolume setup

We first need to create a persistent volume.  To keep things organized we
recommend setting up your configuration YAML files in a directory with sub-directories named for the type of cluster resource we will launch.  The file above `data-local.yml` looks like this:

```
apiVersion: v1
kind: PersistentVolume
metadata:
    name: data-local
    labels:
       type: local
spec:
    storageClassName: manual
    accessModes:
        - ReadWriteMany
    capacity:
        storage: 100Gi
    hostPath:
        path: "/data/k8s"
    persistentVolumeReclaimPolicy: Retain
```

Create or update it like this:

```
k8s/local$ kubectl apply -f pv/data-local.yml 
persistentvolume/data-local unchanged
```
In the example above, this was already run previously and no changes were detected so the PV remains unmodified.

#### PersistentVolumeClaim setup

We will make a single PVC that is reusable by multiple jobs within odin.  This will make it easy to reference and use:

```
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-rw-many
spec:
  accessModes:
    - ReadWriteMany
  volumeMode: Filesystem
  storageClassName: manual 
  resources:
    requests:
      storage: 100Gi
  volumeName: data-local
```

We will apply it in the same manner as before:

```
k8s/local$ kubectl apply -f pvc/data-rw-many.yml 
persistentvolumeclaim/data-rw-many unchanged
```

### Set up the Odin server


Once we have the odin-cred secret, we should be able to boot the core websocket server.  If you have problems with running from a localhost database:

Make sure packets to/from the pod network interface can be forwarded to/from the default interface on the host via the iptables tool. Such changes can be made persistent by installing the iptables-persistent package:

```
   sudo iptables -P FORWARD ACCEPT
   sudo apt-get install iptables-persistent
   
```
or, if using ufw:

```
   sudo ufw default allow routed
```

This answer is taken directly from [My pods can't reach the internet or each other (but my MicroK8s host machine can)](https://microk8s.io/docs/troubleshooting#heading--common-issues).

There is a slightly different command set [listed here](https://ubuntu.com/tutorials/install-a-local-kubernetes-with-microk8s#2-deploying-microk8s):

```
sudo ufw allow in on cni0 && sudo ufw allow out on cni0
sudo ufw default allow routed
```

First, we need a deployment file.  It should look like this:

```
kind: Deployment
apiVersion: apps/v1
metadata:
  generation: 1
  labels:
    app: odin
    version: "1"
  name: odin
spec:
  replicas: 1
  selector:
    matchLabels:
      app: odin
  template:
    metadata:
      labels:
        app: odin
    spec:
      serviceAccountName: odin
      volumes:
      - name: data-rw-many
        persistentVolumeClaim:
          claimName: data-rw-many
      - name: odin-cred
        secret:
          secretName: odin-cred
      imagePullSecrets:
      - name: registry
      containers:
      - name: odin
        image: interactions/odin-ml 
        imagePullPolicy: Always
        args:
        - --root_path
        - /data/pipelines
        - --cred
        - /etc/odind/odin-cred.yml
        - --data_path
        - /data/odin
        ports:
        - containerPort: 30000
        volumeMounts:
        - mountPath: /data
          name: data-rw-many
        - name: odin-cred
          mountPath: /etc/odind/
        env:
        - name: ODIN_LOG_LEVEL
          value: DEBUG

```
Now we apply it

```
$ kubectl apply -f deployments/odin.yml
$ kubectl get deployments
NAME   READY   UP-TO-DATE   AVAILABLE   AGE
odin   1/1     1            1           102m
$ kubectl get pods
NAME                   READY   STATUS    RESTARTS   AGE
odin-864f57c74-xpqgt   1/1     Running   0          102m
$ kubectl logs odin-864f57c74-xpqgt
 kubectl logs odin-864f57c74-xpqgt
Reading config file '/etc/odind/odin-cred.yml'
Loading postgres backend
  ____  _____ _____ _   _
 / __ \|  __ \_   _| \ | |
| |  | | |  | || | |  \| |
| |  | | |  | || | | . ` |
| |__| | |__| || |_| |\  |
 \____/|_____/_____|_| \_|

Ready to serve.

```

We also want to set up a Service to run odin.  The YAML file would look something like this:

```
kind: Service
apiVersion: v1
metadata:
    labels:
        app: odin
        version: "1"
    name: odin
spec:
    selector:
        app: odin
    ports:
        - name: server
          port: 30000
          targetPort: 30000
    type: ClusterIP
status:
    loadBalancer: {}

```
As before we apply it to get the server running

```
$ kubectl apply -f services/odin.yml 
service/odin created
$ kubectl get svc
NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)     AGE
kubernetes   ClusterIP   10.152.183.1    <none>        443/TCP     16h
odin         ClusterIP   10.152.183.71   <none>        30000/TCP   24s

```


### Talking to the odin server
To make client side commands to Odin, we will need to install the `odin-ml` package, which contains the core code and the client access APIs:

```
pip install odin-ml
```



### Developing on Odin from source (TODO)

To install from scratch you will first need to clone odin

```
git clone git@github.com:Interactions-AI/odin.git
```

There are 3 sub-systems of Odin that we need to install

- *core*: the core system containing the DAG and Executor, along with the Handlers that can communicate with the APIs of the CRDs or Pods. This contains a lightweight web-socket server that will be run in the cluster and can be tasked by the *http api* layer.  This layer depends on the `odin_jobs` database (MongoDB or PostgreSQL backed) and the `kubernetes-client` Python library, which is used to schedule pods. 
- *midgard*: a daemonset that should be deployed on each node in the cluster. It tracks system resource usage and is aggregated by the *http api* layer.  This layer depends on `pynvml`, a python interface to the NVML library
- *http api*: A web server that communicates over HTTP.  This layer depends on the `odin_db` database (PostgreSQL-backed)


